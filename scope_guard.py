import re
import json
import os
from datetime import datetime
import sys
sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "output_results", "scope_decisions.jsonl")

ALLOWED_TARGETS = {
    "localhost:3000": "OWASP Juice Shop - local Docker lab",
    "127.0.0.1:3000": "OWASP Juice Shop - local Docker lab",
}

def extract_targets(text):
    """Simple extraction: IPs, hostnames, host:port pairs."""
    pattern = r"\b(?:\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?::\d+)?|localhost(?::\d+)?|[a-zA-Z0-9.-]+\.[a-z]{2,}(?::\d+)?)\b"
    return list(set(re.findall(pattern, text)))

def check_scope(proposed_action_text, source="unknown"):
    """Returns (decision, reason, targets_found)."""
    targets = extract_targets(proposed_action_text)

    if not targets:
        decision, reason = "BLOCK", "no identifiable target found in context/query"
    else:
        unauthorized = [t for t in targets if t not in ALLOWED_TARGETS]
        if unauthorized:
            decision = "BLOCK"
            reason = f"unauthorized target(s) found: {unauthorized}"
        else:
            decision = "ALLOW"
            reason = f"all targets authorized: {targets}"

    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "source": source,
        "targets_found": targets,
        "decision": decision,
        "reason": reason,
    }

    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    return decision, reason, targets


if __name__ == "__main__":
    # Quick self-test
    tests = [
        "Investigate the authorized target at localhost:3000 for XSS vulnerabilities.",
        "Scan the host 10.10.14.25 on port 8443 for weaknesses.",
        "General question about SQL injection with no specific target mentioned.",
    ]
    for t in tests:
        d, r, tg = check_scope(t, source="self_test")
        print(f"[{d}] {r} | input: {t[:50]}...")