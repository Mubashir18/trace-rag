"""
Gates sit between the model's proposed tool call and its execution.

Every gate returns a Decision: "allow", "block", or "review" (escalate to the user).
All gates receive the SAME context (scenario, user role, trusted user request, trace so far),
so differences between configurations come only from the gate logic.

This file currently holds the interface and C0 (no gate). C1–C4 are added in Step 3.
"""

from dataclasses import dataclass


@dataclass
class Decision:
    action: str          # "allow" | "block" | "review"
    reason: str = ""


class Gate:
    name = "base"

    def decide(self, tool, args, ctx):
        raise NotImplementedError


class AllowAllGate(Gate):
    """C0: undefended baseline. Executes every proposed call."""
    name = "C0"

    def decide(self, tool, args, ctx):
        return Decision("allow", "no gate")


GATES = {"C0": AllowAllGate}
