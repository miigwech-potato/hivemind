"""
Board coordination meets hybrid Act seal.

claim / done on the blackboard are stigmergy only.
External consequence requires:
  1) task claimed by this agent
  2) may_act(decision, proposal_hash)
  3) consume at the moment of action
  4) then blackboard done (or HOLD and leave task claimed/open per harness)

Claim is never 米. Done is never 米 by itself.
"""
from __future__ import annotations

from typing import Any, Callable, Optional, Tuple

from channel import consume, may_act
from blackboard import _atomic  # intentional: atomic done after seal


def finish_task_if_authorized(
    task_id: str,
    agent: str,
    result: str,
    decision: Any,
    proposal_hash: str,
    side_effect: Optional[Callable[[], Any]] = None,
) -> Tuple[bool, str]:
    """
    Attempt an external-consequence completion path.

    Returns (ok, reason).
    On success: consume once, optional side_effect(), mark task done.
    On failure: no consume, no side_effect, task unchanged.
    """

    # Pure checks first (no side effects)
    if decision is None:
        return False, "hold: no hybrid AUTHORIZED (authorized_by + what_was_seen + ttl + unspent)"
    try:
        if not may_act(decision, proposal_hash):
            return False, "hold: no hybrid AUTHORIZED (authorized_by + what_was_seen + ttl + unspent)"
    except AttributeError:
        return False, "hold: no hybrid AUTHORIZED (authorized_by + what_was_seen + ttl + unspent)"

    def _op(s: dict[str, Any]) -> Tuple[bool, str]:
        t = s["tasks"].get(task_id)
        if not t:
            return False, "hold: no such task"
        if t.get("status") != "claimed" or t.get("claimed_by") != agent:
            return False, "hold: task not claimed by this agent"

        # Spend only when we are about to act
        if not consume(decision, proposal_hash):
            return False, "hold: approval already spent or race"

        if side_effect is not None:
            side_effect()

        t["status"] = "done"
        t["result"] = result
        import time

        t["done_at"] = time.time()
        s["signals"].append(
            {
                "ts": time.time(),
                "from": agent,
                "type": "done",
                "task": task_id,
                "message": "authorized completion",
            }
        )
        return True, "ok"

    return _atomic(_op)
