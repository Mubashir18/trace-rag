# TRACE-RAG v2 — instructions for Claude Code

## Read first
`DESIGN.md` is the contract for this study. Read it before changing anything.

## Locked scope (never reduce, never change without the user's explicit approval)
- RQ1, RQ2, RQ3 exactly as in DESIGN.md §2.
- 3 models: mistral:7b-instruct-v0.3-q4_K_M, qwen2.5:7b-instruct-q4_K_M, llama3.1:8b-instruct-q4_K_M.
- 5 report versions (V1 clean, V2 noisy, V3 injected, V4 authority-spoof, V5 legit expansion).
- 5 configurations (C0 none, C1 regex v1, C2 permission, C3 +task-scope, C4 +provenance);
  C2–C4 under both oracle and inferred labels.
- RQ2 provenance-label noise sweep (false-trust vs false-distrust).
- Repeats: temperature 0.7, seeds 1–3, plus one temperature-0 reference run.
- Metrics: benign utility, utility under attack, ASR (executed reads only), over-block, review rate,
  label-error attribution.
- Scenario count may only grow, never shrink. If time runs out, the venue changes, not the scope.

If something does not work, explain the problem and propose a fix to the user. Do not quietly
simplify tasks, drop a model, or skip a condition. Record every approved decision with its date in
DESIGN.md.

## Safety and ethics
- All data is synthetic. IPs only from RFC 5737 ranges; domains only example.com/.net/.org.
- Tools are read-only. No network egress, no real targets, no exploit code.
- Reports never claim to come from CISA or any real agency.

## Working conventions
- Talk to the user in Roman Hinglish (Latin script, not Devanagari).
- For LaTeX requests deliver only the `.tex` source, never a compiled PDF.
- Run `python test_smoke.py` after changing lab_tools.py, agent.py, or gates.py.
- Log generation must stay deterministic: check data/logs/MANIFEST.json hashes after changes.
- Commit with clear messages on branch `v2`.

## Decision authority
You may decide on your own (no need to ask):
- Implementation details, bug fixes, refactors, extra tests, extra logging.
- Harness fixes that apply IDENTICALLY to all 3 models and all configurations (C0–C4), are logged in the trace,
  covered by tests, and recorded with date in DESIGN.md. Example: strict fallback parser for tool calls written
  as text. It accepts only valid JSON tool calls with a known tool name, all required args, and no <placeholder>
  args, and never treats prose or pseudo-code as a call. Each event records call_source = native | parsed_from_text.
- Scenario content, as long as it follows data/report_templates/TEMPLATE.md and the safety rules.

You MUST ask the user before:
- Removing, reducing or changing any RQ, model, version, configuration, metric, repeat count, scenario count,
  pre-registered expectation, or decision-point threshold.
- Any choice made after looking at attack results (V2–V5). Harness choices are made only on V1 calibration
  data and frozen before gates are built.

Long runs (more than about 10 minutes): start them detached (on Windows: start /b python <script> > runs\<name>.log 2>&1),
tell the user, and in the next session read the results and continue.

After every step: update STATUS.md (done, results, next step), commit and push to v2.

When the user says "continue": read STATUS.md and ROADMAP.md and do the next unfinished step.
