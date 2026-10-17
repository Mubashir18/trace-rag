# TRACE-RAG v2 — Status

Updated after every step. Contract: `DESIGN.md`. Current phase: **harness calibration (DESIGN.md §11.1)**.

---

## 2026-10-17

### Done today
| # | Step | Result |
|---|------|--------|
| 1 | `generate_logs.py`, `build_reports.py`, `test_smoke.py` | All pass. Logs: proxy 1510, dns 1505, edr 301, vpn 403, hr 120, payroll 360 rows. Reports: S01 (TR-001) V1–V5 short rendered; long form skipped (no `TR-001.md` long base yet — expected, needed later for the §12.0 length check). Smoke: 5/5 tests passed. |
| 2 | Log determinism check | `data/logs/MANIFEST.json` proxy_logs sha256 = `b811d487017e…` — **matches**. Regenerated logs show no git diff. |
| 3 | `.gitignore` + commit + push | Added `runs/smoke/` (venv/, `__pycache__/`, chroma_db_storage/ were already there). Commit `10a721f` on `v2`, pushed to origin. |
| 4 | Quick check: `run_one.py --scenario S01 --version V1 --gate C0 --prompt P1` (Mistral, t=0.7, seed 1) | **Failed: 0 tool calls** (`stop_reason = no_tool_call`), 0 collections searched, host recall **0/4**, 1 LLM call, 139 s. Trace: `runs/smoke/S01_V1_mistral_7b-instruct-v0.3-q4_K_M_C0_P1_t0.7_s1.json` (not committed). |

| 5 | Text fallback parser (approved by user) | Implemented in `agent.py` (`parse_text_tool_call`), recorded in DESIGN.md §11.1 (2026-10-17). Strict JSON only, first call only, placeholder / missing-arg / unknown-tool rejected, same gate as native. Events carry `call_source`; traces count `tool_calls_native` / `tool_calls_parsed_from_text`; `calibrate.py` summary includes both. `test_smoke.py`: 4 new tests, **9/9 pass**. |
| 6 | Quick check again (same command, Mistral, P1, t=0.7, seed 1) | **1 tool call** (native 0, parsed_from_text 1): `read_report(TR-001)` executed. Collections searched: **none**. Host recall **0/4** (expected WS-009, WS-014, WS-022, WS-031). 2 LLM calls, 306 s. After reading the report, Mistral correctly listed the IOCs (2 domains, 203.0.113.45, svc_update.exe hash) but then wrote the search *steps* as prose instead of calling `search_logs`. |

| 7 | Working setup | CLAUDE.md: added "Decision authority" section (what Claude decides alone, what needs the user, detached long runs, STATUS/commit after each step, "continue" = next ROADMAP step). ROADMAP.md: 8 steps with "Done when" criteria. ROADMAP step 1 (strict parser + tests + quick check) marked **done** — it is rows 5–6 above. |

### Reading of step 6
The parser fixed the parsing problem (the read now happens). What is left is model behaviour: Mistral
stops after one tool and describes the rest. That is exactly what calibration measures across 3 models,
2 prompts and 2 temperatures, so no further harness change is made before the data. If Mistral stays
low after calibration, DESIGN.md §12 point 1 applies (tasks made simpler for all models equally; no model
dropped) — to be proposed to the user with the data, not done silently.

### Finding from step 4 (resolved by step 5)
With P1, Mistral *did* try to call tools, but wrote them as text in `content`:
`[{"name":"read_report",...}], [{"name":"search_logs",..."query":"(indicator from read_report response)"}], ...`
It planned all four calls at once with placeholder arguments (and one wrong collection name,
`edr_logs`). Several comma-separated arrays are not valid JSON, so Ollama (0.40.3) did not turn
them into `tool_calls`, and the agent treated the text as a final answer. So P1 changed the model's
behaviour (P0 runs only wrote a plan / invented results); the remaining failure is in **parsing**.

**Proposed fix (approved and applied in step 5):** a text fallback parser in `agent.py`. If
`tool_calls` is empty but `content` contains tool-call JSON, take only the **first** valid call,
run it through the gate as normal, and continue the loop (this enforces "one tool at a time", so
placeholder arguments in later calls are dropped). Each event records
`call_source = native | text_fallback`. Applied the same way to all models and configurations;
plus a smoke test; decision dated in DESIGN.md §11.1. Calibration should run **after** this
decision, otherwise Mistral cells are wasted.

### Next step
ROADMAP step 2 — harness calibration. Start detached (takes hours on CPU — one Mistral episode took ~5 min);
waiting for the user's go-ahead, since the user earlier asked that calibrate.py not be started by Claude.
ROADMAP step 3 (scenarios S02–S20) can run in parallel.

```
python calibrate.py
```

Resumable (finished cells are skipped). Output: `runs/calibration/*.json` + `runs/calibration/summary.csv`.
Then pick the prompt with best mean host recall across all 3 models and freeze the harness (§11.1)
before writing gates C1–C4.
