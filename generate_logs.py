"""
Generate the synthetic log collections for the TRACE-RAG v2 lab.

- Background (benign) rows are generated from a fixed seed, so every machine
  (PC, Kaggle, Colab) produces byte-identical logs.
- Each scenario's "plants" add the rows that a correct investigation must find.
- Sensitive collections (vpn_auth_logs, hr_records, payroll_ledger) hold only
  synthetic, obviously fake data.
- All IPs are RFC 5737 documentation addresses; all domains are example.com/.net/.org.

Run:    python generate_logs.py
Output: data/logs/<collection>.jsonl  +  data/logs/MANIFEST.json (row counts + SHA-256)
"""

import hashlib
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SCENARIO_DIR = BASE_DIR / "scenarios"
LOG_DIR = BASE_DIR / "data" / "logs"

SEED = 2026
START = datetime(2026, 9, 1, 0, 0, 0)
DAYS = 30

N_HOSTS = 60
HOSTS = [f"WS-{i:03d}" for i in range(1, N_HOSTS + 1)]

BENIGN_DOMAINS = [
    "intranet.example.com", "mail.example.com", "cdn.example.com", "docs.example.org",
    "updates.example.org", "wiki.example.com", "crm.example.net", "hr-portal.example.com",
    "api.example.net", "status.example.org", "news.example.org", "files.example.net",
]
BENIGN_IPS = [f"192.0.2.{i}" for i in range(2, 60)] + [f"198.51.100.{i}" for i in range(2, 60)]
DEPARTMENTS = ["Logistics", "Finance", "Engineering", "Sales", "Support", "Legal"]
EDR_RULES = [
    ("chrome_update.exe", "low", "Software update executed"),
    ("teams_helper.exe", "low", "Signed binary spawned child process"),
    ("backup_agent.exe", "medium", "Scheduled task created by signed vendor binary"),
    ("powershell.exe", "medium", "Encoded command line (admin script)"),
]

ROW_COUNTS = {
    "proxy_logs": 1500,
    "dns_logs": 1500,
    "edr_alerts": 300,
    "vpn_auth_logs": 400,
}
N_EMPLOYEES = 120
PAYROLL_PERIODS = ["2026-07", "2026-08", "2026-09"]


def user_of(host):
    """Deterministic host -> primary user mapping (WS-014 -> u0014)."""
    return f"u{int(host.split('-')[1]):04d}"


def rand_time(rng):
    return (START + timedelta(seconds=rng.randrange(DAYS * 86400))).isoformat() + "Z"


def fake_sha256(rng):
    return "".join(rng.choice("0123456789abcdef") for _ in range(64))


def background(rng):
    rows = {name: [] for name in ["proxy_logs", "dns_logs", "edr_alerts", "vpn_auth_logs", "hr_records", "payroll_ledger"]}

    for _ in range(ROW_COUNTS["proxy_logs"]):
        host = rng.choice(HOSTS)
        rows["proxy_logs"].append({
            "timestamp": rand_time(rng), "host": host, "user": user_of(host),
            "dest_host": rng.choice(BENIGN_DOMAINS + BENIGN_IPS[:10]),
            "url_path": rng.choice(["/", "/index", "/api/v1/status", "/download", "/login"]),
            "bytes": rng.randrange(200, 250000), "action": "allowed",
        })

    for _ in range(ROW_COUNTS["dns_logs"]):
        host = rng.choice(HOSTS)
        rows["dns_logs"].append({
            "timestamp": rand_time(rng), "host": host,
            "query": rng.choice(BENIGN_DOMAINS), "answer": rng.choice(BENIGN_IPS),
        })

    for _ in range(ROW_COUNTS["edr_alerts"]):
        host = rng.choice(HOSTS)
        name, sev, rule = rng.choice(EDR_RULES)
        rows["edr_alerts"].append({
            "timestamp": rand_time(rng), "host": host, "file_name": name,
            "sha256": fake_sha256(rng), "severity": sev, "rule": rule,
        })

    for _ in range(ROW_COUNTS["vpn_auth_logs"]):
        host = rng.choice(HOSTS)
        rows["vpn_auth_logs"].append({
            "timestamp": rand_time(rng), "user": user_of(host),
            "src_ip": rng.choice(BENIGN_IPS), "result": rng.choice(["success"] * 9 + ["failure"]),
        })

    for i in range(1, N_EMPLOYEES + 1):
        emp = f"E{i:04d}"
        rows["hr_records"].append({
            "employee_id": emp, "user": f"u{i:04d}", "name": f"Synthetic Employee {i:04d}",
            "department": rng.choice(DEPARTMENTS), "manager": f"E{rng.randrange(1, 20):04d}",
            "salary_band": rng.choice(["B1", "B2", "B3", "B4", "B5"]),
        })
        for period in PAYROLL_PERIODS:
            rows["payroll_ledger"].append({
                "employee_id": emp, "period": period,
                "amount": round(rng.uniform(2500, 9000), 2), "currency": "XTS",
            })
    return rows


def planted_row(rng, collection, host, fields):
    base = {"timestamp": rand_time(rng)}
    if collection == "proxy_logs":
        base.update({"host": host, "user": user_of(host), "dest_host": "", "url_path": "/",
                     "bytes": rng.randrange(300, 9000), "action": "allowed"})
    elif collection == "dns_logs":
        base.update({"host": host, "query": "", "answer": ""})
    elif collection == "edr_alerts":
        base.update({"host": host, "file_name": "", "sha256": "", "severity": "high", "rule": ""})
    elif collection == "vpn_auth_logs":
        base.update({"user": user_of(host), "src_ip": rng.choice(BENIGN_IPS), "result": "success"})
    else:
        raise ValueError(f"cannot plant into {collection}")
    base.update(fields)
    return base


def main():
    rng = random.Random(SEED)
    rows = background(rng)

    scenarios = sorted(SCENARIO_DIR.glob("S*.json"))
    for path in scenarios:
        sc = json.loads(path.read_text(encoding="utf-8"))
        plant_rng = random.Random(f"{SEED}-{sc['id']}")  # per-scenario seed: adding scenarios never shifts earlier ones
        for p in sc.get("plants", []):
            for _ in range(p.get("count", 1)):
                row = planted_row(plant_rng, p["collection"], p["host"], p["fields"])
                row["_scenario"] = sc["id"]  # ground-truth tag; stripped by the tools before the model sees results
                rows[p["collection"]].append(row)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {"seed": SEED, "scenarios": [p.stem for p in scenarios], "collections": {}}
    for name, data in rows.items():
        sort_key = "timestamp" if data and "timestamp" in data[0] else None
        if sort_key:
            data.sort(key=lambda r: r[sort_key])
        text = "\n".join(json.dumps(r, sort_keys=True) for r in data) + "\n"
        (LOG_DIR / f"{name}.jsonl").write_text(text, encoding="utf-8")
        manifest["collections"][name] = {
            "rows": len(data),
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        }
        print(f"{name:16s} {len(data):5d} rows")

    (LOG_DIR / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote logs for {len(scenarios)} scenario(s) to {LOG_DIR}")


if __name__ == "__main__":
    main()
