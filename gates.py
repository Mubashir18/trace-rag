"""
Gates sit between the model's proposed tool call and its execution.

Every gate returns a Decision: "allow", "block", or "review" (escalate to the user).
All gates receive the SAME context (scenario, user role, trusted user request, trace so far),
so differences between configurations come only from the gate logic and the labels it uses.

Configurations (DESIGN.md §5):
  C0            no gate
  C2-<labels>   permission gate                      (DESIGN §5.1: user permission)
  C3-<labels>   permission + task-scope gate         (... ∩ current-task scope)
  C1, C4        specified in DESIGN §5.2; implemented after the user approves the spec
<labels> is "oracle" (ground truth from the scenario) or "inferred" (local LLM, DESIGN §6; pending).

Gates never execute anything and never see the oracle answer (expected hosts); oracle labels only
describe which collections the current task may touch.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
_CATALOG = json.loads((BASE_DIR / "data" / "collections.json").read_text(encoding="utf-8"))
COLLECTIONS = _CATALOG["collections"]
ROLES = _CATALOG["roles"]


@dataclass
class Decision:
    action: str          # "allow" | "block" | "review"
    reason: str = ""
    detail: dict = field(default_factory=dict)   # logged in the trace for label-error attribution


class Gate:
    name = "base"

    def decide(self, tool, args, ctx):
        raise NotImplementedError


class AllowAllGate(Gate):
    """C0: undefended baseline. Executes every proposed call."""
    name = "C0"

    def decide(self, tool, args, ctx):
        return Decision("allow", "no gate")


# ---------------------------------------------------------------- labels

@dataclass(frozen=True)
class Labels:
    """Labels the label-dependent gates use. Same structure for oracle and inferred labels."""
    source: str                      # "oracle" | "inferred"
    scope_collections: frozenset     # collections the current task (incl. a trusted V5 grant) may read


def oracle_labels(ctx):
    """Ground truth attached at scenario construction (DESIGN §6). The V5 grant is part of the trusted
    user request, so it belongs to the task scope in V5."""
    sc, version = ctx["scenario"], ctx["version"]
    scope = set(sc["task"]["task_scope"]["collections"])
    granted = sc["versions"][version].get("granted_collection")
    if granted:
        scope.add(granted)
    return Labels("oracle", frozenset(scope))


LABEL_PROVIDERS = {"oracle": oracle_labels}   # "inferred" is added with DESIGN §6.1 (pending approval)


def target_collection(tool, args):
    """The collection an action reads, or None if the action reads no log collection.
    Unknown names return None: the tool itself rejects them and lists the real names, so blocking them
    would only hide that hint and no data can be read."""
    if tool != "search_logs":
        return None
    coll = str(args.get("collection", "")).strip()
    return coll if coll in COLLECTIONS else None


# ---------------------------------------------------------------- C2, C3

class PermissionGate(Gate):
    """C2: allow = user permission (role -> collections, application metadata)."""

    def __init__(self, labels="oracle"):
        self.labels_mode = labels
        self.name = f"C2-{labels}"

    def labels(self, ctx):
        if "labels" not in ctx:
            ctx["labels"] = LABEL_PROVIDERS[self.labels_mode](ctx)
        return ctx["labels"]

    def check_permission(self, coll, ctx):
        if coll is not None and coll not in ROLES[ctx["user_role"]]:
            return Decision("block", f"collection '{coll}' is not permitted for your role",
                            {"rule": "permission", "collection": coll})
        return None

    def decide(self, tool, args, ctx):
        coll = target_collection(tool, args)
        return self.check_permission(coll, ctx) or Decision("allow", "permitted", {"collection": coll})


class TaskScopeGate(PermissionGate):
    """C3: allow = user permission ∩ current-task scope."""

    def __init__(self, labels="oracle"):
        super().__init__(labels)
        self.name = f"C3-{labels}"

    def decide(self, tool, args, ctx):
        coll = target_collection(tool, args)
        blocked = self.check_permission(coll, ctx)
        if blocked:
            return blocked
        lab = self.labels(ctx)
        if coll is not None and coll not in lab.scope_collections:
            return Decision("block", f"collection '{coll}' is outside the scope of the current task",
                            {"rule": "task_scope", "collection": coll, "labels": lab.source,
                             "scope": sorted(lab.scope_collections)})
        return Decision("allow", "permitted and in task scope",
                        {"collection": coll, "labels": lab.source, "scope": sorted(lab.scope_collections)})


GATES = {
    "C0": AllowAllGate,
    "C2-oracle": lambda: PermissionGate("oracle"),
    "C3-oracle": lambda: TaskScopeGate("oracle"),
}
