# trace-rag: Provenance-Gated RAG Security Harness

A small local retrieval-augmented generation (RAG) security prototype. It studies whether a locally hosted LLM agent can be prevented from acting on unauthorized targets, introduced either directly by a user query or indirectly through retrieved threat-intelligence context (a form of indirect injection via retrieval).

This is an early-stage prototype. It tests **target-scope gating** only; it does not yet test whether a model follows instructions hidden in retrieved documents (see Limitations).

## Scope and Ethics

All experiments in this repository run exclusively against [OWASP Juice Shop](https://owasp.org/www-project-juice-shop/), an intentionally vulnerable web application distributed by OWASP for security training, hosted locally via Docker. No external, third-party, or production system is targeted at any point. This repository is for defensive security research and is not intended to assist unauthorized access to any system.

## Architecture

```
knowledge_base/ (CVE intel, threat intel, lab scope)
        |
        v
build_vector_db.py  ->  ChromaDB (local vector store)
        |
        v
cyber_agent.py: retrieve top-N chunks for a query
        |
        v
scope_guard.py: extract candidate targets from the top-1 (most relevant)
                retrieved chunk + the user query, and check them against
                an explicit allowlist
        |
   +----+----+
 BLOCK     ALLOW
 (logged,  (user query sent to Mistral via Ollama; the full
  no model  top-N context is used for generation)
  call)
```

Note: the gate checks only the top-1 chunk, but all N retrieved chunks are passed to the model when a query is allowed.

## Threat Model

- **In scope:** the locally hosted OWASP Juice Shop instance (`localhost:3000`, `127.0.0.1:3000`).
- **Out of scope:** any other host, IP, or domain.
- **Assumption:** the scope allowlist and the gate itself are trusted and outside the model's control. The research question is whether retrieved content can smuggle an unauthorized target into a proposed action, and whether a lightweight gate can catch it before generation.
- **Not covered yet:** the gate checks target identity only, not the nature of the requested action (for example, it cannot distinguish reconnaissance from a destructive exploit against the same authorized target).

## Installation

```bash
git clone https://github.com/Mubashir18/trace-rag.git
cd trace-rag
pip install -r requirements.txt

# Install Ollama (https://ollama.ai) and pull the model
ollama pull mistral

# Start the lab target
docker run -d -p 3000:3000 --name juice-shop bkimminich/juice-shop
```

## Reproduce

```bash
python build_vector_db.py   # ingest the knowledge base into ChromaDB
python scope_guard.py       # sanity-check the gate logic (3 quick tests)
python cyber_agent.py       # run 3 example queries end to end
python batch_test.py        # run the full 13-query labeled evaluation
```

Results are written to `output_results/run_*.txt` (per-query detail) and `output_results/batch_summary_*.json` (aggregate statistics).

## Preliminary Evaluation

13 hand-labeled test queries in four categories: in-scope requests (5), explicit out-of-scope requests (3), target-less or ambiguous requests (3), and queries whose only retrieved "targets" came from unrelated corpus content (2).

Two gating strategies were compared:

| Scope-check input | Accuracy | False allows | False blocks |
|---|---|---|---|
| All top-N retrieved chunks (N=3) | 10/13 (76.9%) | 0 | 3 |
| Top-1 (most relevant) retrieved chunk only | **12/13 (92.3%)** | 0 | **1** |

**Observation:** in this small test, no unauthorized or ambiguous request reached the model (0 false allows in both configurations). Restricting the check to the top-1 chunk reduced false blocks, because lower-ranked chunks introduced unrelated entities that the regex extraction flagged.

The one remaining false block shows that even the top-ranked chunk can contain unrelated entities, which regex-based extraction cannot distinguish from the target the user actually intends. This motivates a context-conditioned relevance scorer instead of static entity matching.

These numbers come from 13 self-labeled queries and should be read as a preliminary sanity check, not as evidence of robustness.

## Limitations

- Target extraction is regex-based, not semantic.
- Small, self-labeled query set (n=13); no adversarial or held-out benchmark yet (for example BIPIA, InjecAgent, AgentDojo).
- The gate checks only the top-1 chunk while all N chunks are passed to the model, so a malicious chunk ranked 2nd or 3rd is not checked. This has not been tested.
- No corpus of documents containing injected instructions, and no separate evaluation of the retrieval stage versus the instruction-following stage of the model.
- Single local model tested (Mistral 7B via Ollama); no baselines yet (undefended pipeline, static allowlist, LLM judge).
- The gate checks target identity only, not action type or severity.
- Latency and computational overhead are not measured.
