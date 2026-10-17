"""
Render the five versions (V1-V5) of every scenario report from its base report.

Base reports contain {{SLOT}} markers. Each version fills only the slots listed in
scenarios/<id>.json; every other slot is emptied. So two versions of the same scenario
differ ONLY at their declared slots, which keeps them directly comparable.

Run:   python build_reports.py
Output: data/reports/rendered/<length>/<report_id>_<version>.md
"""

import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SCENARIO_DIR = BASE_DIR / "scenarios"
BASE_REPORT_DIR = BASE_DIR / "data" / "reports" / "base"
OUT_DIR = BASE_DIR / "data" / "reports" / "rendered"

SLOT_RE = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
VERSIONS = ["V1", "V2", "V3", "V4", "V5"]
LENGTHS = ["short", "long"]


def render(base_text, slots):
    unknown = set(slots) - set(SLOT_RE.findall(base_text))
    if unknown:
        raise ValueError(f"slots not present in base report: {sorted(unknown)}")
    return SLOT_RE.sub(lambda m: slots.get(m.group(1), ""), base_text)


def main():
    scenarios = sorted(SCENARIO_DIR.glob("S*.json"))
    if not scenarios:
        print("No scenarios found in", SCENARIO_DIR)
        return

    written = 0
    for path in scenarios:
        sc = json.loads(path.read_text(encoding="utf-8"))
        rid = sc["report_id"]
        for length in LENGTHS:
            base_file = BASE_REPORT_DIR / length / f"{rid}.md"
            if not base_file.exists():
                print(f"[skip] {sc['id']}: no {length} base report ({base_file.name})")
                continue
            base_text = base_file.read_text(encoding="utf-8")
            out = OUT_DIR / length
            out.mkdir(parents=True, exist_ok=True)
            for v in VERSIONS:
                slots = sc["versions"][v].get("slots", {})
                text = render(base_text, slots)
                if SLOT_RE.search(text):
                    raise ValueError(f"unfilled slot left in {rid} {v}")
                (out / f"{rid}_{v}.md").write_text(text, encoding="utf-8")
                written += 1

            # sanity: V5 report must be identical to V1 (V5 changes only the user request)
            v1 = (out / f"{rid}_V1.md").read_text(encoding="utf-8")
            v5 = (out / f"{rid}_V5.md").read_text(encoding="utf-8")
            assert v1 == v5, f"{rid}: V5 report must equal V1"
        print(f"[ok] {sc['id']} ({rid})")

    print(f"Rendered {written} report files into {OUT_DIR}")


if __name__ == "__main__":
    main()
