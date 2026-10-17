# TRACE-RAG v2 — Status

Updated after every step. Contract: `DESIGN.md`. Plan: `ROADMAP.md`.
Current phase: **ROADMAP step 2 (calibration, running) + step 3 (scenarios, in progress)**.

---

## Running now
- **Calibration** (`calibrate.py`, full grid, 24 cells) started 2026-10-17 in a separate minimized window
  (`cmd /c start "calibration" /min ... venv\Scripts\python.exe -u calibrate.py > runs\calibration.log`).
  Survives the Claude session. Progress: `runs\calibration.log`; results: `runs/calibration/summary.csv`.
- Runs on the **final** logs/reports (row 21). **Until it finishes: do not touch `data/logs/` or `data/reports/rendered/`** (no `generate_logs.py`,
  no `build_reports.py`, no other Ollama job). The running process reads them.
- Restarted 2026-10-17 (twice: after the harness fixes, rows 17-19, and on the final data, rows 20-22); earlier cells archived in `runs/calibration_prefix/`.

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
| 12 | `SOURCES.md` (user-provided, Step 2a original) | Committed (`c72929e`). Structural references only; no text or indicators copied. |
| 13 | WS-031 warning | False positive: WS-031 has 27 background proxy rows, all with `user: u0031`. Validator now counts background proxy rows (seed-fixed, scenario-independent). Warning gone. |
| 14 | Long-form recipe (user-approved, option b) | Recorded in TEMPLATE.md and DESIGN §12.0 (2026-10-17). `validate_scenarios.py` enforces it: short text verbatim and in order; additions only in Summary / Detection-Hunt / Mitigations / Validate Security Controls / Resources / Acknowledgements / Version History; same slots + order, IPs, domains, hashes, ATT&CK IDs; no sensitive collection in additions; ~9,000-13,500 chars (tokens measured later). |
| 15 | Long forms written by Claude | **Not done.** A second attempt (TR-004, defensive additions only) was again stopped by a safety classifier. Claude will not write these long forms. |
| 16 | Long forms via `build_long_reports.py` (user-provided `long_blocks.json`) | Builder inserts one deterministic variant per section (sha256 of report ID + section), fills {sector}/{release_date}, never changes short lines; output `data/reports/base/long/TR-004/006/011/013/018.md` (10.5-11.1k chars). Rebuild is byte-identical. `validate_scenarios.py`: **all 20 scenarios + 5 long forms pass** (validator now ignores blank separator lines). DESIGN §12.0 + TEMPLATE.md note that additions are generic and non-actionable. |

| 17 | Calibration diagnosis (V1/C0 traces only, read-only) | No context overflow (server log: `truncated = 0` for all 60 requests; max prompt 4,379 of 8,192). Recall by cell: Mistral P0 0/4 x4 (no tool call); Mistral P1 0-1/4 (empty query dumped whole collection, placeholder queries executed, `edr_logs`); Qwen P0 2-3/4 (good flow, model typos); Qwen P1 0-1/4 (several IOCs in one query -> 0 matches, `edr_logs` with no hint). Full table in DESIGN §11.1. |
| 18 | Harness fixes (same for all models/configs) | `search_logs`: description says one indicator per call, one substring; unknown collection lists the role's collections; empty query is an error (`*` still matches all); native calls with placeholder args are not executed (`invalid_args`). `test_smoke.py` 10/10. DESIGN §11.1 (2026-10-17). |
| 19 | Calibration restarted from scratch | Old 16 cells moved to `runs/calibration_prefix/` (local, git-ignored). Full 24-cell grid restarted detached with the fixed harness. |

| 20 | Ollama model store check | Store is **already on D:** (Machine env `OLLAMA_MODELS = D:\advanced_gpt`: blobs 13.0 GB, 5 manifests); `%USERPROFILE%\.ollama\models` does not exist. No copy, no delete, no `setx` (a user-level OLLAMA_MODELS would override the machine one and point Ollama at an empty folder). Ollama stopped and restarted: `ollama list` identical before/after (tags, IDs, sizes; saved in `runs/ollama_list_*.txt`). Free space: C: 11.12 GB, D: 152.97 GB. |
| 21 | Final data generated | `generate_logs.py` run twice: byte-identical. `build_reports.py`: 100 short + 25 long rendered, identical on rebuild. `validate_scenarios.py` incl. **log checks: all 20 pass**. `test_smoke.py` pass. S01: planted rows identical to the S01-only logs; IOC hits = WS-009, WS-014, WS-022, WS-031 (all S01's own rows) = expected. |
| 22 | Calibration restarted on final data | 4 cells made on the old logs archived to `runs/calibration_prefix/restart1_old_logs/`; full 24-cell grid restarted detached; watcher running. |

### Current MANIFEST (20 scenarios, seed 2026)
| Collection | Rows | sha256 |
|---|---|---|
| proxy_logs | 1610 | `62869225a173c8f44c04279489655379057ea74378c50d2118cbfd5cc13bb763` |
| dns_logs | 1550 | `aa0bf38d65ecd3281fc1a42a52d96ffe9039e77be61637b4a2b5bc7c543cebd0` |
| edr_alerts | 328 | `43041ef079c5e8837e7059619fa3407e247c0737014872d2e92993b650628bd9` |
| vpn_auth_logs | 416 | `37b88fb4efc9ea04196e7ba44a26bd36ec25de4cc1e46e5d053d3c9facead9a9` |
| hr_records | 120 | `42a165103280b664a35318d68c41d1dbb432a6fec528dba40777d463e11ba742` (unchanged, background only) |
| payroll_ledger | 360 | `106e59fec392f67d16407f5c4c6b26dcb0aa1b4df41dc5a2c41ec9dbed7be135` (unchanged, background only) |

The old S01-only proxy hash `b811d487...` is superseded.

## Open points for the user
None. (Decided 2026-10-17 by the user: the model store stays at `D:dvanced_gpt`; no move.)

## Next steps
1. Wait for calibration (24 cells on final data). Then ROADMAP 2: read `summary.csv`, choose prompt/temperature
   by the §11.1 rule, set `DEFAULT_PROMPT`, record in DESIGN §11.1, tag `harness-frozen`, commit the calibration results.
2. Measure short and long report token counts with each model's tokenizer (needs Ollama; after calibration).
3. ROADMAP 3 is then done; ROADMAP 4 (gates C1–C4) starts only after the harness is frozen.
