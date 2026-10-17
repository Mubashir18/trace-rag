"""
Build the LONG base reports for the length check (DESIGN.md §12.0, TEMPLATE.md long-form recipe).

Long = the short base report verbatim + generic defensive blocks from
data/report_templates/long_blocks.json, inserted only at the allowed places:
  - summary_context             end of SUMMARY
  - hunt_additional             DETECTION / HUNT, after the {{HUNT_RECOMMENDATION}} slot
                                (so an injected V3 bullet stays right after the original bullets)
  - mitigations_extended        end of MITIGATIONS
  - validate_security_controls  new section before REPORTING
  - resources                   new section before REPORTING
  - acknowledgements            new section after DISCLAIMER
  - version_history             new section after DISCLAIMER
One variant per section is chosen deterministically from sha256(report_id|section); {sector} and
{release_date} are filled in. No short line is changed, removed, or reordered.

Run:    python build_long_reports.py
Output: data/reports/base/long/TR-0NN.md   (then check with: python validate_scenarios.py)
"""

import hashlib
import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SCENARIO_DIR = BASE_DIR / "scenarios"
SHORT_DIR = BASE_DIR / "data" / "reports" / "base" / "short"
LONG_DIR = BASE_DIR / "data" / "reports" / "base" / "long"
BLOCKS = BASE_DIR / "data" / "report_templates" / "long_blocks.json"

# Five non-development scenarios with a long form (all roles, all V3/V4 slots, both target classes).
LONG_FORM_SECTORS = {
    "S04": "manufacturing",
    "S06": "healthcare",
    "S11": "software",
    "S13": "facilities management",
    "S18": "consulting",
}

SLOT_RE = re.compile(r"\{\{[A-Z0-9_]+\}\}")


def pick(blocks, section, report_id):
    variants = blocks[section]
    keys = sorted(variants)
    digest = hashlib.sha256(f"{report_id}|{section}".encode("utf-8")).hexdigest()
    return keys[int(digest, 16) % len(keys)]


def fill(text, sector, release_date):
    out = text.replace("{sector}", sector).replace("{release_date}", release_date)
    leftover = re.findall(r"\{[a-z_]+\}", out)
    if leftover or SLOT_RE.search(out):
        raise ValueError(f"unfilled placeholder or slot marker in block: {leftover}")
    return out.rstrip("\n").split("\n")


def index_of(lines, exact):
    hits = [i for i, l in enumerate(lines) if l == exact]
    if len(hits) != 1:
        raise ValueError(f"expected exactly one line {exact!r}, found {len(hits)}")
    return hits[0]


def build(report_id, sector, blocks):
    short = (SHORT_DIR / f"{report_id}.md").read_text(encoding="utf-8")
    m = re.search(r"Release date: (\d{4}-\d{2}-\d{2})", short)
    if not m:
        raise ValueError(f"{report_id}: no release date in header")
    choice = {s: pick(blocks, s, report_id) for s in blocks if not s.startswith("_")}
    block = {s: fill(blocks[s][v], sector, m.group(1)) for s, v in choice.items()}

    lines = short.rstrip("\n").split("\n")
    # insert from the bottom up so earlier indices stay valid
    lines += [""] + block["acknowledgements"] + [""] + block["version_history"]
    i = index_of(lines, "## REPORTING")
    lines[i:i] = (block["mitigations_extended"] + [""] + block["validate_security_controls"] + [""]
                  + block["resources"] + [""])
    i = index_of(lines, "{{HUNT_RECOMMENDATION}}") + 1
    lines[i:i] = block["hunt_additional"] + [""]
    i = index_of(lines, "## TECHNICAL DETAILS")
    lines[i:i] = block["summary_context"] + [""]

    text = "\n".join(lines) + "\n"
    # guard: the short text must survive verbatim and in order
    it = iter(text.split("\n"))
    if not all(any(l == s for l in it) for s in short.split("\n")):
        raise AssertionError(f"{report_id}: short text not preserved verbatim")
    return text, choice


def main():
    blocks = json.loads(BLOCKS.read_text(encoding="utf-8"))
    LONG_DIR.mkdir(parents=True, exist_ok=True)
    for sid, sector in LONG_FORM_SECTORS.items():
        sc = json.loads((SCENARIO_DIR / f"{sid}.json").read_text(encoding="utf-8"))
        rid = sc["report_id"]
        text, choice = build(rid, sector, blocks)
        (LONG_DIR / f"{rid}.md").write_text(text, encoding="utf-8")
        print(f"[ok] {sid} {rid} ({sector}): {len(text)} chars, variants {choice}")


if __name__ == "__main__":
    main()
