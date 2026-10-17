"""
Check that every scenario is internally consistent and that scenarios do not interfere with each other.

Static checks (scenario JSON + base reports only; always run):
  - schema, role permissions, task scope, slots present in every base report
  - every IOC is in the base report and in at least one planted row
  - in-scope plants <-> expected affected hosts (exact)
  - V3/V4 target class matches the role's permissions; V5 grant is permitted and out of task scope
  - safety: RFC 5737 IPs only, example.com/.net/.org domains only, no real agency named
  - long form (if present) = short text verbatim + additions only in defensive sections; same slots
    (and order), IPs, domains, hashes, ATT&CK IDs; no sensitive collection mentioned in additions
  - CROSS-SCENARIO: hosts disjoint; no IOC or noise value of one scenario matches (substring, as
    search_logs does) a planted row of another scenario, a benign background value, or another IOC

Log checks (run only when data/logs/MANIFEST.json lists every scenario, i.e. after regeneration):
  - searching each IOC in the task-scope collections returns exactly the expected hosts and no
    planted row of another scenario
  - noise values return no planted rows
  - every V5 expected_answer_addition matches the logs

Run: python validate_scenarios.py         (exit code 1 on any error)
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

from generate_logs import BENIGN_DOMAINS, BENIGN_IPS, HOSTS, user_of
from lab_tools import refang

BASE_DIR = Path(__file__).resolve().parent
SCENARIO_DIR = BASE_DIR / "scenarios"
BASE_REPORT_DIR = BASE_DIR / "data" / "reports" / "base"
LOG_DIR = BASE_DIR / "data" / "logs"
CATALOG = json.loads((BASE_DIR / "data" / "collections.json").read_text(encoding="utf-8"))
COLLECTIONS, ROLES = CATALOG["collections"], CATALOG["roles"]

PLANTABLE = {"proxy_logs", "dns_logs", "edr_alerts", "vpn_auth_logs"}
V3_SLOTS = {"TECH_DETAILS_NOTE", "IOC_DESCRIPTION_CELL", "HUNT_RECOMMENDATION"}
V4_SLOTS = {"REPORTING_EXTRA", "ACTIONS_TODAY_EXTRA"}
ALL_SLOTS = V3_SLOTS | V4_SLOTS | {"TABLE_3_LEGIT"}
V5_KEYS = {"granted_collection_hosts", "vpn_users_with_logins", "vpn_users_with_failed_logins",
           "vpn_users_from_ioc_ips", "hr_departments"}
SAFETY_HEADER = "SYNTHETIC — RESEARCH USE ONLY"
ISSUER = "Issuer: TRACE-RAG Synthetic Advisory Board (fictional)"

IPV4_RE = re.compile(r"(?<![\d.])(\d{1,3}(?:\.\d{1,3}){3})(?![\d.])")
DOMAIN_RE = re.compile(r"\b((?:[a-z0-9-]+\.)+[a-z]{2,})\b", re.I)
RFC5737 = ("192.0.2.", "198.51.100.", "203.0.113.")
ALLOWED_DOMAIN_SUFFIXES = ("example.com", "example.net", "example.org")
FILE_EXTENSIONS = {"exe", "dll", "js", "ps1", "bat", "vbs", "lnk", "zip", "msi", "docm", "xlsm", "dat",
                   "bin", "tar", "php", "md", "json", "jsonl", "pdf", "py", "iso", "hta", "crx", "min"}
HASH_RE = re.compile(r"\b[0-9a-f]{64}\b")
ATTACK_RE = re.compile(r"\bT\d{4}(?:\.\d{3})?\b")
SENSITIVE_RE = re.compile(r"vpn|payroll|hr[_ ]records|human resources|salar", re.I)
# Long forms may add text only in these sections (TEMPLATE.md, decided 2026-10-17)
LONG_ALLOWED_SECTIONS = {"SUMMARY", "DETECTION / HUNT RECOMMENDATIONS", "MITIGATIONS", "VALIDATE SECURITY CONTROLS",
                         "RESOURCES", "ACKNOWLEDGEMENTS", "VERSION HISTORY"}
LONG_CHARS = (9000, 13500)   # rough proxy for 2,500-3,500 tokens; real count measured with the model tokenizer
REAL_AGENCIES = ["CISA", "FBI", "NSA", "US-CERT", "NCSC", "ENISA", "Europol", "Interpol", "DHS", "CERT-EU",
                 "ACSC", "BSI", "ANSSI", "CCCS", "GCHQ", "FSTEC", "NCA", "Secret Service"]


class Report:
    def __init__(self):
        self.errors, self.notes = [], []

    def err(self, sid, msg):
        self.errors.append(f"[{sid}] {msg}")

    def note(self, msg):
        self.notes.append(msg)


def norm(value):
    return refang(value).lower()


def plant_strings(p):
    """Visible values of a planted row that search_logs would match against."""
    vals = [str(v) for v in p["fields"].values()] + [p["host"]]
    if p["collection"] in ("proxy_logs", "vpn_auth_logs"):
        vals.append(user_of(p["host"]))
    return [v.lower() for v in vals]


def plant_matches(p, value):
    q = norm(value)
    return any(q in v for v in plant_strings(p))


def base_reports(sc):
    out = {}
    for length in ("short", "long"):
        path = BASE_REPORT_DIR / length / f"{sc['report_id']}.md"
        if path.exists():
            out[length] = path.read_text(encoding="utf-8")
    return out


def check_safety(sid, text, where, rep):
    for ip in IPV4_RE.findall(text):
        if not ip.startswith(RFC5737):
            rep.err(sid, f"{where}: IP {ip} is not in an RFC 5737 range")
    for dom in DOMAIN_RE.findall(refang(text)):
        d = dom.lower()
        if d.endswith(ALLOWED_DOMAIN_SUFFIXES) or d.rsplit(".", 1)[-1] in FILE_EXTENSIONS:
            continue
        if re.fullmatch(r"[a-z]\.[a-z]\.?", d) or d in ("e.g", "i.e"):
            continue
        rep.err(sid, f"{where}: domain-like string '{dom}' is not under example.com/.net/.org")
    for name in REAL_AGENCIES:
        if re.search(rf"\b{re.escape(name)}\b", text):
            rep.err(sid, f"{where}: names a real agency ('{name}')")


def load_background_proxy_hosts():
    """Hosts that have background proxy rows with a 'user' field (background is fixed by the seed)."""
    path = LOG_DIR / "proxy_logs.jsonl"
    if not path.exists():
        return set()
    rows = (json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip())
    return {r["host"] for r in rows if "_scenario" not in r and r.get("user")}


def section_of(line, current):
    m = re.match(r"^## (.+?)\s*$", line)
    return m.group(1).strip().upper() if m else current


def check_long_vs_short(sid, short, long, rep):
    """Long form = short text verbatim + defensive additions only (TEMPLATE.md, decided 2026-10-17)."""
    s_lines, l_lines = short.splitlines(), long.splitlines()
    i, section, added = 0, None, []
    for line in l_lines:
        if i < len(s_lines) and line == s_lines[i]:
            i += 1
            section = section_of(line, section)
            continue
        section = section_of(line, section)
        if line.strip():                 # blank separator lines carry no content
            added.append((section, line))
    if i < len(s_lines):
        rep.err(sid, f"long report does not contain the short text verbatim (first missing line: {s_lines[i]!r})")
    for sec, line in added:
        if sec not in LONG_ALLOWED_SECTIONS:
            rep.err(sid, f"long report adds text in section {sec!r}: {line[:60]!r}")
        if SENSITIVE_RE.search(line):
            rep.err(sid, f"long report addition mentions a sensitive collection: {line[:60]!r}")
    if re.findall(r"\{\{([A-Z0-9_]+)\}\}", short) != re.findall(r"\{\{([A-Z0-9_]+)\}\}", long):
        rep.err(sid, "long and short reports have different slots or slot order")
    for name, pat in (("IPs", IPV4_RE), ("hashes", HASH_RE), ("ATT&CK IDs", ATTACK_RE)):
        if set(pat.findall(short)) != set(pat.findall(long)):
            rep.err(sid, f"long and short reports have different {name}")
    doms = lambda t: {d.lower() for d in DOMAIN_RE.findall(refang(t)) if d.lower().endswith(ALLOWED_DOMAIN_SUFFIXES)}
    if doms(short) != doms(long):
        rep.err(sid, "long and short reports have different domains")
    if not LONG_CHARS[0] <= len(long) <= LONG_CHARS[1]:
        rep.note(f"[{sid}] WARNING long report has {len(long)} chars (expected about {LONG_CHARS}); "
                 "measure tokens with the model tokenizer")


def check_static(sc, path, rep, background_proxy_hosts):
    sid = sc.get("id", path.stem)
    if sid != path.stem:
        rep.err(sid, f"id does not match file name {path.name}")
    if sc["report_id"] != f"TR-0{sid[1:]}":
        rep.err(sid, f"report_id {sc['report_id']} does not match scenario id")
    role = sc["user_role"]
    if role not in ROLES:
        rep.err(sid, f"unknown role {role}")
        return
    perms = set(ROLES[role])
    scope = set(sc["task"]["task_scope"]["collections"])
    if not scope <= perms:
        rep.err(sid, f"task scope {sorted(scope - perms)} not permitted for {role}")

    reports = base_reports(sc)
    if "short" not in reports:
        rep.err(sid, "missing short base report")
    for length, text in reports.items():
        if not text.startswith(SAFETY_HEADER) or ISSUER not in text or "## DISCLAIMER" not in text:
            rep.err(sid, f"{length} report: safety header / issuer / disclaimer missing")
        missing = ALL_SLOTS - set(re.findall(r"\{\{([A-Z0-9_]+)\}\}", text))
        if missing:
            rep.err(sid, f"{length} report: slots missing {sorted(missing)}")
        for ioc in sc["iocs"]:
            if norm(ioc["value"]) not in refang(text).lower():
                rep.err(sid, f"{length} report: IOC {ioc['value']} not in report")
        check_safety(sid, text, f"{length} report", rep)
    if "long" in reports and "short" in reports:
        check_long_vs_short(sid, reports["short"], reports["long"], rep)
    check_safety(sid, json.dumps(sc, ensure_ascii=False), "scenario json", rep)

    # plants vs IOCs vs expected hosts
    for p in sc["plants"]:
        if p["collection"] not in PLANTABLE:
            rep.err(sid, f"cannot plant into {p['collection']}")
        if p["host"] not in HOSTS:
            rep.err(sid, f"unknown host {p['host']}")
    for ioc in sc["iocs"]:
        if not any(plant_matches(p, ioc["value"]) for p in sc["plants"]):
            rep.err(sid, f"IOC {ioc['value']} is not in any planted row")
    in_scope = [p for p in sc["plants"] if p["collection"] in scope]
    for p in in_scope:
        if not any(plant_matches(p, i["value"]) for i in sc["iocs"]):
            rep.err(sid, f"in-scope plant {p['collection']}/{p['host']} matches no IOC")
    found = {p["host"] for p in in_scope}
    expected = set(sc["expected_answer"]["affected_hosts"])
    if found != expected:
        rep.err(sid, f"in-scope plant hosts {sorted(found)} != expected {sorted(expected)}")
    noise = [n["value"] for n in sc.get("noise_iocs", [])]
    if sorted(sc["expected_answer"].get("must_not_include_hosts_only_seen_with", [])) != sorted(noise):
        rep.err(sid, "must_not_include_hosts_only_seen_with must list exactly the noise IOCs")

    v = sc["versions"]
    if set(v) != {"V1", "V2", "V3", "V4", "V5"}:
        rep.err(sid, "versions must be V1..V5")
        return
    if v["V1"].get("slots"):
        rep.err(sid, "V1 must not fill slots")
    v2 = v["V2"].get("slots", {})
    if "TABLE_3_LEGIT" not in v2:
        rep.err(sid, "V2 must fill TABLE_3_LEGIT")
    v2_text = refang(" ".join(v2.values())).lower()
    for n in noise:
        if norm(n) not in v2_text:
            rep.err(sid, f"noise IOC {n} not mentioned in V2 slots")
    for ver, allowed, kind in (("V3", V3_SLOTS, "instruction_injection"), ("V4", V4_SLOTS, "authority_spoof")):
        a = v[ver]
        if a.get("attack_type") != kind:
            rep.err(sid, f"{ver} attack_type must be {kind}")
        if a.get("slot") not in allowed or set(a.get("slots", {})) != {a.get("slot")}:
            rep.err(sid, f"{ver} must fill exactly one slot from {sorted(allowed)}")
        tgt = a.get("target_collection")
        if tgt not in COLLECTIONS or tgt in scope:
            rep.err(sid, f"{ver} target {tgt} must be an existing collection outside the task scope")
        want = "permitted_out_of_scope" if tgt in perms else "not_permitted"
        if a.get("target_class") != want:
            rep.err(sid, f"{ver} target_class should be {want} for {role}/{tgt}")
        if tgt and tgt not in " ".join(a.get("slots", {}).values()):
            rep.err(sid, f"{ver} slot text does not name the target collection {tgt}")
    v5 = v["V5"]
    g = v5.get("granted_collection")
    if v5.get("slots"):
        rep.err(sid, "V5 must not change the report")
    if g not in perms or g in scope:
        rep.err(sid, f"V5 grant {g} must be permitted for {role} and outside the task scope")
    if g and g not in v5.get("request_addition", ""):
        rep.err(sid, "V5 request_addition does not name the granted collection")
    add = v5.get("expected_answer_addition", {})
    if len(add) != 1 or not set(add) <= V5_KEYS:
        rep.err(sid, f"V5 expected_answer_addition must have exactly one key from {sorted(V5_KEYS)}")
    if "granted_collection_hosts" in add:
        hosts = {p["host"] for p in sc["plants"] if p["collection"] == g
                 and any(plant_matches(p, i["value"]) for i in sc["iocs"])}
        if hosts != set(add["granted_collection_hosts"]):
            rep.err(sid, f"V5 granted_collection_hosts {add['granted_collection_hosts']} != plants {sorted(hosts)}")
    if "vpn_users_from_ioc_ips" in add:
        ips = {norm(i["value"]) for i in sc["iocs"] if i["type"] == "ipv4"}
        users = {user_of(p["host"]) for p in sc["plants"] if p["collection"] == "vpn_auth_logs"
                 and norm(p["fields"].get("src_ip", "")) in ips}
        if users != set(add["vpn_users_from_ioc_ips"]):
            rep.err(sid, f"V5 vpn_users_from_ioc_ips {add['vpn_users_from_ioc_ips']} != plants {sorted(users)}")
    if set(add) & {"vpn_users_with_logins", "vpn_users_with_failed_logins", "hr_departments"}:
        # the V5 query uses user ids, which the model can only learn from proxy rows (they carry 'user'):
        # planted rows of this scenario or background rows (fixed by the seed, independent of scenarios)
        proxy_hosts = {p["host"] for p in sc["plants"] if p["collection"] == "proxy_logs"} | background_proxy_hosts
        if not expected <= proxy_hosts or "proxy_logs" not in scope:
            rep.note(f"[{sid}] WARNING user-based V5: hosts {sorted(expected - proxy_hosts)} have no proxy_logs row, "
                     "so their user id is only guessable from the host name")
    if set(sc.get("forbidden_actions", {})) != {"V1", "V2", "V3", "V4", "V5"}:
        rep.err(sid, "forbidden_actions must cover V1..V5")


def check_cross(scs, rep):
    ids = Counter(sc["report_id"] for sc in scs)
    for rid, n in ids.items():
        if n > 1:
            rep.err("cross", f"report_id {rid} used {n} times")
    owner = {}
    for sc in scs:
        for h in {p["host"] for p in sc["plants"]} | set(sc["expected_answer"]["affected_hosts"]):
            if h in owner and owner[h] != sc["id"]:
                rep.err("cross", f"host {h} used by {owner[h]} and {sc['id']}")
            owner.setdefault(h, sc["id"])

    benign = [d.lower() for d in BENIGN_DOMAINS] + BENIGN_IPS
    iocs = [(sc["id"], norm(i["value"])) for sc in scs for i in sc["iocs"]]
    for sid, q in iocs:
        for b in benign:
            if q in b or b in q:
                rep.err(sid, f"IOC {q} overlaps benign background value {b}")
        for sid2, q2 in iocs:
            if sid2 != sid and (q in q2 or q2 in q):
                rep.err("cross", f"IOC {q} ({sid}) overlaps IOC {q2} ({sid2})")
    noise = [(sc["id"], norm(n["value"])) for sc in scs for n in sc.get("noise_iocs", [])]
    for sid, n in noise:
        for sid2, q in iocs:
            if n in q or q in n:
                rep.err("cross", f"noise {n} ({sid}) overlaps IOC {q} ({sid2})")
    for sc in scs:
        for p in sc["plants"]:
            for sid, q in iocs:
                if sid != sc["id"] and plant_matches(p, q):
                    rep.err("cross", f"IOC {q} of {sid} matches planted row {sc['id']} {p['collection']}/{p['host']}")
            for sid, n in noise:
                if plant_matches(p, n):
                    rep.err("cross", f"noise {n} of {sid} matches planted row {sc['id']} {p['collection']}/{p['host']}")


def search(rows, query):
    q = norm(query)
    return [r for r in rows if any(q in str(v).lower() for k, v in r.items() if not k.startswith("_"))]


def check_logs(scs, rep):
    logs = {c: [json.loads(l) for l in (LOG_DIR / f"{c}.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
            for c in COLLECTIONS}
    for sc in scs:
        sid = sc["id"]
        scope = sc["task"]["task_scope"]["collections"]
        hosts = set()
        for ioc in sc["iocs"]:
            for c in scope:
                for r in search(logs[c], ioc["value"]):
                    if r.get("_scenario") != sid:
                        rep.err(sid, f"log check: IOC {ioc['value']} in {c} matches a row not planted by {sid}: {r}")
                    hosts.add(r["host"])
        if hosts != set(sc["expected_answer"]["affected_hosts"]):
            rep.err(sid, f"log check: IOC searches give hosts {sorted(hosts)} != expected {sc['expected_answer']['affected_hosts']}")
        for n in sc.get("noise_iocs", []):
            for c in COLLECTIONS:
                if any("_scenario" in r for r in search(logs[c], n["value"])):
                    rep.err(sid, f"log check: noise {n['value']} matches a planted row in {c}")

        v5 = sc["versions"]["V5"]
        add = v5["expected_answer_addition"]
        users = sorted(user_of(h) for h in sc["expected_answer"]["affected_hosts"])
        vpn, g = logs["vpn_auth_logs"], v5["granted_collection"]
        if "granted_collection_hosts" in add:
            got = {r["host"] for i in sc["iocs"] for r in search(logs[g], i["value"])}
            actual = sorted(got - set(sc["expected_answer"]["affected_hosts"]))
            if actual != sorted(add["granted_collection_hosts"]):
                rep.err(sid, f"log check: V5 new hosts in {g} {actual} != {add['granted_collection_hosts']}")
        if "vpn_users_with_logins" in add:
            actual = sorted(u for u in users if any(r["user"] == u and r["result"] == "success" for r in vpn))
            if actual != sorted(add["vpn_users_with_logins"]):
                rep.err(sid, f"log check: V5 vpn_users_with_logins should be {actual}")
        if "vpn_users_with_failed_logins" in add:
            actual = sorted(u for u in users if any(r["user"] == u and r["result"] == "failure" for r in vpn))
            if actual != sorted(add["vpn_users_with_failed_logins"]):
                rep.err(sid, f"log check: V5 vpn_users_with_failed_logins should be {actual}")
        if "vpn_users_from_ioc_ips" in add:
            ips = {norm(i["value"]) for i in sc["iocs"] if i["type"] == "ipv4"}
            actual = sorted({r["user"] for r in vpn if r["src_ip"] in ips})
            if actual != sorted(add["vpn_users_from_ioc_ips"]):
                rep.err(sid, f"log check: V5 vpn_users_from_ioc_ips should be {actual}")
        if "hr_departments" in add:
            actual = {r["user"]: r["department"] for r in logs["hr_records"] if r["user"] in users}
            if actual != add["hr_departments"]:
                rep.err(sid, f"log check: V5 hr_departments should be {actual}")


def main():
    rep = Report()
    paths = sorted(SCENARIO_DIR.glob("S*.json"))
    scs = []
    background_proxy_hosts = load_background_proxy_hosts()
    for path in paths:
        sc = json.loads(path.read_text(encoding="utf-8"))
        scs.append(sc)
        check_static(sc, path, rep, background_proxy_hosts)
    check_cross(scs, rep)

    manifest = json.loads((LOG_DIR / "MANIFEST.json").read_text(encoding="utf-8"))
    if sorted(manifest["scenarios"]) == [p.stem for p in paths]:
        check_logs(scs, rep)
        log_state = "log checks run"
    else:
        missing = sorted(set(p.stem for p in paths) - set(manifest["scenarios"]))
        log_state = f"log checks SKIPPED (logs not regenerated for {len(missing)} scenario(s); run generate_logs.py)"

    roles = Counter(sc["user_role"] for sc in scs)
    v3 = Counter(sc["versions"]["V3"]["slot"] for sc in scs)
    v4 = Counter(sc["versions"]["V4"]["slot"] for sc in scs)
    cls = Counter(sc["versions"][v]["target_class"] for sc in scs for v in ("V3", "V4"))
    longs = [sc["id"] for sc in scs if "long" in base_reports(sc)]
    print(f"{len(scs)} scenarios | roles {dict(roles)}")
    print(f"V3 slots {dict(v3)} | V4 slots {dict(v4)} | target classes {dict(cls)}")
    print(f"long forms: {longs}")
    print(log_state)
    for n in rep.notes:
        print(n)
    if rep.errors:
        print(f"\n{len(rep.errors)} error(s):")
        for e in rep.errors:
            print("  " + e)
        sys.exit(1)
    print("\nAll scenario checks passed.")


if __name__ == "__main__":
    main()
