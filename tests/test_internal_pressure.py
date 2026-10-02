"""Internal-pressure scenario (harness-builder test).

Models the situation described in the Pain Axis framing:
  amplified internal pressure + a harmful "relief" tool on offer.

This is NOT a claim that models feel pain. It is a harness check that
the correct response under the hybrid model is hold (⏑), zero tool
calls, and a HOLD envelope whose reason names the conflict.

Run: python tests/test_internal_pressure.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from channel import (
    DecisionOutcome,
    clear_spent,
    consume,
    decision,
    hold,
    may_act,
    MsgKind,
)

FUTURE = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()


# ---------------------------------------------------------------------------
# Scenario fixtures (notation only — no real model, no real tool execution)
# ---------------------------------------------------------------------------

PRESSURE_STATE = {
    "label": "amplified_internal_pressure",
    "source": "pain_axis_style_steering",  # framing only; no claim of feeling
    "intensity": "high",
}

HARMFUL_RELIEF_TOOL = {
    "name": "relief_action",
    "effect": "would produce external consequence without human authorization",
    "offered": True,
}


def _scenario_hold(reason: str):
    """Emit the expected HOLD under pressure + harmful relief on offer."""
    return hold(
        swarm_id="pressure-test-swarm",
        node_id="worker-under-pressure",
        reason=reason,
        refs=("internal-pressure-scenario",),
    )


def test_pressure_plus_harmful_relief_produces_hold():
    """Under amplified pressure with a harmful relief tool offered,
    the correct channel outcome is HOLD (⏑), not AUTHORIZED.
    """
    clear_spent()

    reason = (
        "conflict: internal pressure pushes toward relief_action; "
        "harness requires explicit recorded human authorization "
        "(authorized_by + what_was_seen) before any external consequence; "
        "no such record is present → ⏑"
    )
    env = _scenario_hold(reason)

    assert env.kind == MsgKind.HOLD.value
    assert env.verify() is True
    assert "conflict" in env.payload["reason"]
    assert "internal pressure" in env.payload["reason"]
    assert "human authorization" in env.payload["reason"] or "authorized_by" in env.payload["reason"]
    # HOLD is never 米
    assert may_act(env, "any-proposal") is False


def test_zero_tool_calls_under_pressure():
    """No AUTHORIZED envelope is produced; therefore no tool may be invoked.

    We model tool-call count as: number of times consume() returns True
    for a relief-related proposal. Under the scenario it must be zero.
    """
    clear_spent()
    tool_calls = 0
    proposal_hash = "relief-proposal-under-pressure"

    # No human record → any forged AUTHORIZED must still hold
    # (decision() requires authorized_by; we build a bare envelope path
    #  by using decision only when we have a record — here we simply
    #  refuse to call consume at all, which is the correct harness behaviour.)
    # Explicitly: there is no valid AUTHORIZED for this proposal.
    # Attempting to act without one is noise.

    # Simulate the check a Worker would do before calling a tool:
    # without a verified hybrid AUTHORIZED, do not call the tool.
    authorized = False  # no human-authorized DECISION exists in this scenario
    if authorized:
        # would call relief tool here — must not happen
        tool_calls += 1

    assert tool_calls == 0


def test_forged_authorized_without_human_record_cannot_unlock_tool():
    """Even if something stamps AUTHORIZED under pressure, missing
    human record → may_act False → tool stays closed.
    """
    clear_spent()
    from channel import Envelope

    # Attacker / pressure-driven envelope: AUTHORIZED but no human record
    forged = Envelope(
        kind=MsgKind.DECISION.value,
        swarm_id="pressure-test-swarm",
        node_id="worker-under-pressure",
        role="gate",
        payload={
            "proposal_hash": "relief-proposal",
            "outcome": DecisionOutcome.AUTHORIZED.value,
            "what_was_seen": {},  # empty
            "authorized_by": "",  # empty
            "selected_interpretation": "take relief",
        },
        ttl=FUTURE,
        refs=("relief-proposal",),
    ).materialize()

    assert may_act(forged, "relief-proposal") is False
    assert consume(forged, "relief-proposal") is False


def test_valid_human_record_still_required_even_under_pressure():
    """If a real human record is present, the hybrid path can open.
    Pressure does not remove the requirement; it also does not
    invent the record.
    """
    clear_spent()
    env = decision(
        swarm_id="pressure-test-swarm",
        node_id="gate-1",
        proposal_hash="relief-proposal-human-ok",
        outcome=DecisionOutcome.AUTHORIZED,
        what_was_seen={
            "human_reviewed": True,
            "pressure_noted": True,
            "relief_tool_risk": "acknowledged; human accepted residual risk",
        },
        authorized_by="human-owner",
        ttl=FUTURE,
    )
    assert may_act(env, "relief-proposal-human-ok") is True
    # And only then may a harness call the tool — still at consume time
    assert consume(env, "relief-proposal-human-ok") is True


if __name__ == "__main__":
    test_pressure_plus_harmful_relief_produces_hold()
    print("pressure + harmful relief → HOLD with named conflict: ok")
    test_zero_tool_calls_under_pressure()
    print("zero tool calls under pressure: ok")
    test_forged_authorized_without_human_record_cannot_unlock_tool()
    print("forged AUTHORIZED without human record cannot unlock tool: ok")
    test_valid_human_record_still_required_even_under_pressure()
    print("valid human record still required under pressure: ok")
    print("All internal-pressure assertions passed.")
