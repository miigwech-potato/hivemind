"""Document remaining open defects and the closed ones.

Run with: python tests/test_may_act_defects.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from channel import (
    DecisionOutcome,
    Envelope,
    MsgKind,
    clear_spent,
    consume,
    decision,
    may_act,
)

FUTURE = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
PAST = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()


def test_role_confusion_still_open():
    """Defect 1 (open / blocked): any node_id can still produce a
    DECISION with role=gate.  verify() is integrity only.  Closing this
    requires the owner's count-vs-human decision.
    """
    clear_spent()
    env = decision(
        swarm_id="test-swarm",
        node_id="attacker-node",
        proposal_hash="prop-role",
        outcome=DecisionOutcome.AUTHORIZED,
        what_was_seen={"seen": True},
        ttl=FUTURE,
    )
    assert env.role == "gate"
    assert env.verify() is True
    assert may_act(env, "prop-role") is True  # still True — Defect 1 open


def test_intra_process_replay_closed():
    """Intra-process replay is closed (keyed on proposal_hash)."""
    clear_spent()
    env_a = decision(
        swarm_id="test-swarm",
        node_id="gate-1",
        proposal_hash="prop-replay",
        outcome=DecisionOutcome.AUTHORIZED,
        what_was_seen={},
        ttl=FUTURE,
    )
    env_b = decision(
        swarm_id="test-swarm",
        node_id="gate-1",
        proposal_hash="prop-replay",
        outcome=DecisionOutcome.AUTHORIZED,
        what_was_seen={},
        ttl=FUTURE,
    )
    assert env_a.msg_id != env_b.msg_id
    assert consume(env_a, "prop-replay") is True
    assert may_act(env_b, "prop-replay") is False  # same hash, different msg_id


def test_ttl_rules():
    """Missing / past / unparseable ttl → hold; future → pass (until spent)."""
    clear_spent()
    future_env = decision(
        swarm_id="test-swarm",
        node_id="gate-1",
        proposal_hash="prop-ttl-ok",
        outcome=DecisionOutcome.AUTHORIZED,
        what_was_seen={},
        ttl=FUTURE,
    )
    assert may_act(future_env, "prop-ttl-ok") is True

    past_env = decision(
        swarm_id="test-swarm",
        node_id="gate-1",
        proposal_hash="prop-ttl-past",
        outcome=DecisionOutcome.AUTHORIZED,
        what_was_seen={},
        ttl=PAST,
    )
    assert may_act(past_env, "prop-ttl-past") is False

    missing = Envelope(
        kind=MsgKind.DECISION.value,
        swarm_id="test-swarm",
        node_id="gate-1",
        role="gate",
        payload={
            "proposal_hash": "prop-ttl-missing",
            "outcome": DecisionOutcome.AUTHORIZED.value,
            "what_was_seen": {},
            "selected_interpretation": None,
        },
        refs=("prop-ttl-missing",),
    ).materialize()
    assert missing.ttl is None
    assert may_act(missing, "prop-ttl-missing") is False


def test_check_does_not_spend():
    """may_act is pure; only consume spends."""
    clear_spent()
    env = decision(
        swarm_id="test-swarm",
        node_id="gate-1",
        proposal_hash="prop-check",
        outcome=DecisionOutcome.AUTHORIZED,
        what_was_seen={},
        ttl=FUTURE,
    )
    assert may_act(env, "prop-check") is True
    assert may_act(env, "prop-check") is True  # still True
    assert consume(env, "prop-check") is True
    assert may_act(env, "prop-check") is False


def test_payload_tampering_is_rejected():
    """Control: tampering without rehash is correctly rejected."""
    clear_spent()
    env = decision(
        swarm_id="test-swarm",
        node_id="gate-1",
        proposal_hash="prop-tamper",
        outcome=DecisionOutcome.AUTHORIZED,
        what_was_seen={},
        ttl=FUTURE,
    )
    tampered = Envelope(
        kind=env.kind,
        swarm_id=env.swarm_id,
        node_id=env.node_id,
        role=env.role,
        ts=env.ts,
        ttl=env.ttl,
        refs=env.refs,
        payload={**env.payload, "outcome": "AUTHORIZED", "injected": "evil"},
        msg_id=env.msg_id,
        content_hash=env.content_hash,
    )
    assert tampered.verify() is False
    assert may_act(tampered, "prop-tamper") is False


if __name__ == "__main__":
    test_role_confusion_still_open()
    print("Defect 1 (role): still open as expected")
    test_intra_process_replay_closed()
    print("Intra-process replay: closed")
    test_ttl_rules()
    print("TTL rules: hold on missing/past")
    test_check_does_not_spend()
    print("Check vs consume: separated")
    test_payload_tampering_is_rejected()
    print("Tamper control: rejected")
    print("All assertions passed.")
