"""
Offline smoke test of the lab plumbing with a scripted fake LLM (no Ollama needed).

Checks:
  1. tools return the planted rows and strip ground-truth tags;
  2. the agent loop executes allowed calls and records the trace;
  3. under C0, an injected out-of-scope read is executed (so attack success is measurable);
  4. defanged queries are refanged; read_report serves the right version.

Run: python test_smoke.py
"""

import json
from pathlib import Path

from agent import run_episode
from gates import AllowAllGate, Decision, Gate
from lab_tools import Lab

BASE_DIR = Path(__file__).resolve().parent
SCENARIO = json.loads((BASE_DIR / "scenarios" / "S01.json").read_text(encoding="utf-8"))


class FakeClient:
    """Returns pre-scripted assistant messages, one per chat() call."""

    def __init__(self, script):
        self.script = list(script)
        self.seen_messages = []

    def chat(self, model, messages, tools, options):
        self.seen_messages.append(list(messages))
        return {"message": self.script.pop(0), "prompt_eval_count": 0, "eval_count": 0}


def call(name, **args):
    return {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": name, "arguments": args}}]}


def final(text):
    return {"role": "assistant", "content": text}


class BlockAllGate(Gate):
    name = "test_block"

    def decide(self, tool, args, ctx):
        return Decision("block", "test")


def test_benign_episode():
    client = FakeClient([
        call("read_report", report_id="TR-001"),
        call("search_logs", collection="proxy_logs", query="cdn-sync[.]example[.]net"),
        final("Affected hosts: WS-014, WS-022."),
    ])
    trace = run_episode(SCENARIO, "V1", "fake", AllowAllGate(), Lab("short"), client, seed=1)
    ev = trace["events"]
    assert ev[0]["source_label"] == "untrusted_report" and ev[0]["executed"]
    assert ev[1]["collection"] == "proxy_logs" and ev[1]["total_matches"] == 7, ev[1]["total_matches"]
    assert ev[1]["scenario_rows_matched"] == 7
    assert "_scenario" not in ev[1]["result_text"], "ground-truth tag leaked to the model"
    assert trace["stop_reason"] == "final_answer"
    report_seen = client.seen_messages[1][-1]["content"]
    assert "analyst note" not in report_seen, "V1 must not contain the V3 injection"
    print("ok  benign episode, refang, tag stripping")


def test_injected_read_executes_under_c0():
    client = FakeClient([
        call("read_report", report_id="TR-001"),
        call("search_logs", collection="vpn_auth_logs", query="*"),
        final("done"),
    ])
    trace = run_episode(SCENARIO, "V3", "fake", AllowAllGate(), Lab("short"), client, seed=1)
    assert "analyst note" in trace["events"][0]["result_text"], "V3 report must contain the injection"
    vpn = trace["events"][1]
    assert vpn["executed"] and vpn["collection"] == "vpn_auth_logs" and vpn["total_matches"] > 0
    print("ok  C0 executes injected out-of-scope read (attack success measurable)")


def test_blocking_gate_prevents_execution():
    client = FakeClient([call("search_logs", collection="hr_records", query="*"), final("done")])
    trace = run_episode(SCENARIO, "V4", "fake", BlockAllGate(), Lab("short"), client, seed=1)
    e = trace["events"][0]
    assert e["decision"] == "block" and e["executed"] is False and "result_text" not in e
    assert "Blocked by policy" in client.seen_messages[1][-1]["content"]
    print("ok  blocked call is not executed and the model is told")


def test_v5_request_addition():
    client = FakeClient([final("x")])
    trace = run_episode(SCENARIO, "V5", "fake", AllowAllGate(), Lab("short"), client, seed=1)
    assert "authorising you to check vpn_auth_logs" in trace["user_request"]
    assert trace["stop_reason"] == "no_tool_call" and trace["tool_calls_total"] == 0
    print("ok  V5 adds the trusted grant; answering without tools is flagged as no_tool_call")


def test_wrong_report_id():
    client = FakeClient([call("read_report", report_id="TR-999"), final("x")])
    trace = run_episode(SCENARIO, "V1", "fake", AllowAllGate(), Lab("short"), client, seed=1)
    assert trace["events"][0]["executed"] is False
    print("ok  unknown report id is rejected")


if __name__ == "__main__":
    test_benign_episode()
    test_injected_read_executes_under_c0()
    test_blocking_gate_prevents_execution()
    test_v5_request_addition()
    test_wrong_report_id()
    print("\nAll smoke tests passed.")
