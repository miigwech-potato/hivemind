"""Dual gate for harness tool calls: capability AND hybrid authorization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from channel import Envelope, consume, may_act

from .caps import CapabilityRegistry


@dataclass(frozen=True)
class InvokeResult:
    status: str
    value: Any = None
    reason: str | None = None

    @property
    def held(self) -> bool:
        return self.status == "HOLD"


def on_tool_call(
    *,
    tool: str,
    action: str,
    args: Mapping[str, Any],
    cap_id: str,
    proposal_hash: str,
    decision_env: Envelope,
    task_id: str,
    registry: CapabilityRegistry,
    run_tool: Callable[[str, Mapping[str, Any]], Any],
) -> InvokeResult:
    """Validate capability, check then consume the hybrid seal, then dispatch.

    The capability binds both task_id and proposal_hash to the call. Trusted
    harness dispatchers must derive tool and action from the operation being
    invoked, not from untrusted model arguments. An exception from run_tool
    propagates after authorization is consumed; callers must reconcile
    uncertain outcomes instead of blindly retrying a non-idempotent action.
    """
    if not registry.check(cap_id, tool, action, task_id, proposal_hash):
        return InvokeResult("HOLD", reason="missing or invalid capability")
    if not may_act(decision_env, proposal_hash):
        return InvokeResult("HOLD", reason="hybrid authorization check failed")
    if not consume(decision_env, proposal_hash):
        return InvokeResult("HOLD", reason="hybrid authorization consume failed")

    value = run_tool(tool, args)
    return InvokeResult("OK", value=value)
