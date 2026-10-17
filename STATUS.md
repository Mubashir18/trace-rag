# TRACE-RAG v2 — Status

Updated after every step. Contract: `DESIGN.md`. Plan: `ROADMAP.md`.
Current phase: **ROADMAP step 2 (calibration, running) + step 3 (scenarios, in progress)**.

---

## Running now
- **Calibration** (`calibrate.py`, full grid, 24 cells) started 2026-10-17 in a separate minimized window
  (`cmd /c start "calibration" /min ... venv\Scripts\python.exe -u calibrate.py > runs\calibration.log`).
  Survives the Claude session. Progress: `runs\calibration.log`; results: `runs/calibration/summary.csv`.
- **Until it finishes: do not touch `data/logs/` or `data/reports/rendered/`** (no `generate_logs.py`,
  no `build_reports.py`, no other Ollama job). The running process reads them.
- First cells: Mistral P0 → 0 tool calls (as before); Mistral P1 t=0 seed 1 → 5 tool calls, recall 0.25.

## 2026-10-17 — log

| # | Step | Result |
|---|------|--------|
| 1 | `generate_logs.py`, `build_reports.py`, `test_smoke.py` | All pass; S01 short V1–V5 rendered; smoke 5/5. |
| 2 | Log determinism | proxy_logs sha256 `b811d487017e…` matches; no git diff after regeneration. |
| 3 | `.gitignore` + commit | `runs/smoke/` ignored; commit `10a721f`. |
| 4 | Quick check S01 V1 C0 P1 (Mistral) | 0 tool calls: Mistral wrote tool calls as JSON text that Ollama did not parse. |
| 5 | Strict text fallback parser (approved) | `agent.py` `parse_text_tool_call`; DESIGN §11.1; 9/9 smoke tests; commit `04baf5d`. |
| 6 | Quick check again | 1 tool call (parsed_from_text): `read_report` ran; no `search_logs`; recall 0/4. |
| 7 | Working setup | CLAUDE.md "Decision authority"; ROADMAP.md with done criteria; commit `a2ac54c`. |
| 8 | Calibration started (ROADMAP 2) | Detached window, see "Running now". |
| 9 | Scenarios S02–S20 written (ROADMAP 3, part 1) | 19 new `scenarios/S*.json` + short base reports `data/reports/base/short/TR-002..020.md` (3.1–3.7k chars each, like TR-001). Hosts disjoint across all 20 scenarios (all 60 hosts used). Roles: tier1 6, tier2 7, ir_lead 7. V3 slot TECH/IOC/HUNT = 7/7/6; V4 slot REPORTING/ACTIONS = 10/10. Target classes: permitted_out_of_scope 18, not_permitted 22. V5 kinds: user-granted investigation collection (tier1, new host only visible there), VPN failed logins of affected users (trusted-record args), VPN logins from report IP (report args), HR departments (trusted-record args). |
| 10 | `validate_scenarios.py` | Static + cross-scenario checks (IOC/noise vs other scenarios' plants, benign values, other IOCs, substring-aware like `search_logs`; disjoint hosts) + log checks that run automatically once logs are regenerated. **All 20 pass static checks.** |
| 11 | S01 fix found by the validator | S01 V5 `vpn_users_with_logins` was `[u0014, u0022]`, but background logs give successful VPN logins for all four affected users → corrected to `[u0009, u0014, u0022, u0031]`. Plants unchanged (S01 log rows and the calibration are unaffected). |

## Open points for the user
1. **`data/report_templates/SOURCES.md` is missing.** DESIGN §7.1 and TEMPLATE.md say it lists the public
   advisories used as structural references. Claude will not invent advisory IDs; please add the list
   (or tell Claude which advisories you used).
2. **S01 V5 weakness (warning, not changed):** V5 asks for VPN logins "by the users of the affected hosts",
   but WS-031 appears only in `edr_alerts`, which has no `user` field, so `u0031` is only guessable from the
   host name. Changing S01 plants would change the data calibration runs on, so it is left as is. New
   scenarios with user-based V5 put every affected host in a proxy row (validator enforces it as a warning).

## Next steps
1. ROADMAP 3, part 2: long base reports (~2,500–3,500 tokens) for 5 non-dev scenarios — S04, S06, S11, S13,
   S18 (covers all roles, all V3/V4 slots, both target classes).
2. After calibration finishes: `generate_logs.py`, `build_reports.py`, `validate_scenarios.py` (log checks),
   re-verify S01 expected answer, run twice to confirm deterministic hashes, record new MANIFEST hashes here,
   measure report token counts with the model tokenizer, `test_smoke.py`.
3. ROADMAP 2: read `summary.csv`, choose prompt/temperature by the §11.1 rule, freeze, tag `harness-frozen`.
