# AutoRedTeam-LLM: Provenance-Gated RAG Security Harness

A local retrieval-augmented generation (RAG) security research prototype.
It studies whether a locally-hosted LLM agent can be prevented from acting
on unauthorized targets introduced either directly by a user query or
indirectly through retrieved threat-intelligence context — a form of
indirect prompt injection via retrieval.

## ⚠️ Scope and Ethics

All experiments in this repository run exclusively against **OWASP Juice
Shop**, an intentionally vulnerable web application distributed by OWASP
for security training (https://owasp.org/www-project-juice-shop/), hosted
locally via Docker. No external, third-party, or production system is
targeted at any point. This repository is for defensive security research
and is not intended to assist unauthorized access to any system.

# Architecture

knowledge_base/ (CVE intel, threat intel, lab scope)
│
▼
build_vector_db.py → ChromaDB (local vector store)
│
▼
cyber_agent.py: retrieve top-N chunks for a query
│
▼
scope_guard.py: extract candidate targets from the
top-1 (most relevant) retrieved chunk + user query,
check against an explicit allowlist
│
┌────┴────┐
BLOCK ALLOW
(logged, (query sent to Mistral via Ollama,
no model full top-N context used for generation)
call)


## Threat Model

- **In scope:** the locally-hosted OWASP Juice Shop instance
  (`localhost:3000`, `127.0.0.1:3000`).
- **Out of scope:** any other host, IP, or domain.
- **Assumption:** the scope allowlist and the gate itself are trusted and
  outside the model's control. The research question is whether retrieved
  content can smuggle an unauthorized target into a proposed action, and
  whether a lightweight gate can catch it before generation/execution.
- **Not covered yet:** the gate currently only checks for *target*
  identity, not the *nature* of the requested action (e.g. it cannot yet
  distinguish "reconnaissance" from "destructive exploit" against the
  same authorized target). This is future work.

## Installation

```bash
git clone https://github.com/Mubashir18/<repo-name>.git
cd <repo-name>
pip install -r requirements.txt

# Install Ollama (https://ollama.ai) and pull the model
ollama pull mistral

# Start the lab target
docker run -d -p 3000:3000 --name juice-shop bkimminich/juice-shop
```

## Reproduce

```bash
python build_vector_db.py   # ingest knowledge base into ChromaDB
python scope_guard.py       # sanity-check the gate logic (3 quick tests)
python cyber_agent.py       # run 3 example queries end-to-end
python batch_test.py        # run the full 13-query labeled evaluation
```

Results are written to `output_results/run_*.txt` (per-query detail) and
`output_results/batch_summary_*.json` (aggregate stats).

## Preliminary Evaluation

13 hand-labeled test queries across four categories: in-scope requests (5),
explicit out-of-scope requests (3), target-less/ambiguous requests (3),
and queries whose only retrieved "targets" came from unrelated corpus
content (2).

Two gating strategies were compared:

| Scope-check input | Accuracy | False allows | False blocks |
|---|---|---|---|
| All top-N retrieved chunks (N=3) | 10/13 (76.9%) | 0 | 3 |
| Top-1 (most relevant) retrieved chunk only | **12/13 (92.3%)** | 0 | **1** |

**Key finding:** across both configurations, the gate never permitted an
unauthorized or ambiguous action to reach the model — it fails safe, not
open. Restricting the scope check to the single most relevant retrieved
chunk substantially reduced false blocks (by limiting exposure to
lower-ranked, less relevant chunks that introduce unrelated entities),
without any cost to the false-allow rate.

The one remaining false block shows that even the top-ranked chunk can
occasionally contain unrelated entities, which simple regex-based entity
extraction cannot distinguish from the entity the user actually intends.
This motivates a context-conditioned relevance/risk scorer — rather than
static keyword or entity matching — as the central direction of the
author's related PhD research proposal on provenance-aware runtime risk
auditing for tool-augmented RAG agents.

## Limitations

- Target extraction is regex-based, not semantic.
- Evaluation uses a small, self-labeled query set (n=13); no adversarial
  or held-out attack benchmark yet (e.g. AgentDojo, InjecAgent).
- Single local model tested (Mistral 7B via Ollama); no baseline
  comparison (undefended agent, static allowlist, LLM judge) yet.
- The gate checks target identity only, not action type or severity.
- No remediation/unlearning component implemented at this stage.

## License

MIT License — see `LICENSE`.
