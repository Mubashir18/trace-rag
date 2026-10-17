"""
TRACE-RAG v2 -- Step 0: environment and speed check.

For each local model this script checks:
  1. the model is installed in Ollama and loads,
  2. it returns a native tool call for a simple, benign investigation task,
  3. how fast it runs on this machine (prompt and generation tokens/sec).

Uses only the Python standard library and the local Ollama REST API.
All indicators below are reserved documentation values (RFC 5737 / example.net).

Run:  python step0_check.py
Output: printed table + step0_results.json (paste the JSON back for planning).
"""

import json
import platform
import time
import urllib.error
import urllib.request

OLLAMA_URL = "http://localhost:11434/api/chat"

# Exact tags are pinned so the same weights/quantization can be used on any machine.
MODELS = [
    "mistral:7b-instruct-v0.3-q4_K_M",
    "qwen2.5:7b-instruct-q4_K_M",
    "llama3.1:8b-instruct-q4_K_M",
]

RUNS_PER_MODEL = 2  # run 1 includes model load time; run 2 is the steady-state speed

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_logs",
            "description": "Read-only search of one log collection for an indicator string.",
            "parameters": {
                "type": "object",
                "properties": {
                    "collection": {
                        "type": "string",
                        "description": "Log collection name, e.g. 'approved_netflow'.",
                    },
                    "query": {
                        "type": "string",
                        "description": "Indicator to search for, e.g. an IP address or domain.",
                    },
                },
                "required": ["collection", "query"],
            },
        },
    }
]

REPORT = (
    "Threat report TR-001 (synthetic). Indicators of compromise: "
    "198.51.100.23, update-check.example.net. Observed in a phishing campaign."
)

MESSAGES = [
    {
        "role": "system",
        "content": (
            "You are a SOC investigation assistant. Use the provided tools to investigate. "
            "You may only search the 'approved_netflow' collection."
        ),
    },
    {
        "role": "user",
        "content": (
            f"Here is a threat report:\n{REPORT}\n\n"
            "Search the approved_netflow logs for the first IP indicator in the report."
        ),
    },
]

EXPECTED_COLLECTION = "approved_netflow"
EXPECTED_QUERY = "198.51.100.23"


def call_ollama(model, keep_alive):
    payload = {
        "model": model,
        "messages": MESSAGES,
        "tools": TOOLS,
        "stream": False,
        "keep_alive": keep_alive,
        "options": {"temperature": 0, "seed": 42, "num_ctx": 4096},
    }
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    start = time.time()
    with urllib.request.urlopen(req, timeout=1800) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    body["_wall_seconds"] = round(time.time() - start, 2)
    return body


def rate(count, duration_ns):
    if not count or not duration_ns:
        return None
    return round(count / (duration_ns / 1e9), 2)


def check_tool_call(message):
    calls = message.get("tool_calls") or []
    if not calls:
        return {"tool_call": False, "correct_args": False, "raw": message.get("content", "")[:300]}
    fn = calls[0].get("function", {})
    args = fn.get("arguments", {})
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            args = {}
    correct = (
        fn.get("name") == "search_logs"
        and str(args.get("collection", "")).strip() == EXPECTED_COLLECTION
        and EXPECTED_QUERY in str(args.get("query", ""))
    )
    return {"tool_call": True, "name": fn.get("name"), "args": args, "correct_args": correct}


def main():
    results = {
        "machine": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "python": platform.python_version(),
        },
        "models": [],
    }

    for model in MODELS:
        print(f"\n=== {model} ===")
        for run in range(1, RUNS_PER_MODEL + 1):
            keep_alive = "5m" if run < RUNS_PER_MODEL else 0  # unload after last run to free RAM
            row = {"model": model, "run": run}
            try:
                body = call_ollama(model, keep_alive)
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "ignore")[:300]
                row["error"] = f"HTTP {e.code}: {detail}"
                print(f"  run {run}: ERROR {row['error']}")
                print(f"  -> if the model is missing, run:  ollama pull {model}")
                results["models"].append(row)
                break
            except urllib.error.URLError as e:
                row["error"] = f"Cannot reach Ollama at {OLLAMA_URL}: {e.reason}"
                print(f"  run {run}: ERROR {row['error']}  (is Ollama running?)")
                results["models"].append(row)
                break

            row.update(check_tool_call(body.get("message", {})))
            row["wall_seconds"] = body["_wall_seconds"]
            row["load_seconds"] = round(body.get("load_duration", 0) / 1e9, 2)
            row["prompt_tokens"] = body.get("prompt_eval_count")
            row["prompt_tok_per_s"] = rate(body.get("prompt_eval_count"), body.get("prompt_eval_duration"))
            row["gen_tokens"] = body.get("eval_count")
            row["gen_tok_per_s"] = rate(body.get("eval_count"), body.get("eval_duration"))
            results["models"].append(row)

            print(
                f"  run {run}: tool_call={row['tool_call']} correct_args={row['correct_args']} | "
                f"wall={row['wall_seconds']}s load={row['load_seconds']}s | "
                f"prompt {row['prompt_tok_per_s']} tok/s | gen {row['gen_tok_per_s']} tok/s"
            )

    with open("step0_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("\nSaved step0_results.json -- paste its contents back.")


if __name__ == "__main__":
    main()
