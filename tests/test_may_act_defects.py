"""Hybrid authorization model — closed vs remaining limits.

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


def _auth(**kwargs):
    """Helper: valid hybrid AUTHORIZED decision."""
    defaults = dict(
        swarm_id="test-swarm",
        node_id="gate-1",
        proposal_hash="prop",
        outcome=DecisionOutcome.AUTHORIZED,
        what_was_seen={"summary": "human reviewed the proposal"},
        authorized_by="human-owner",
        ttl=FUTURE,
    )
    defaults.update(kwargs)
    return decision(**defaults)


def test_hybrid_happy_path():
    clear_spent()
    env = _auth(proposal_hash="p-ok")
    assert may_act(env, "p-ok") is True
    assert consume(env, "p-ok") is True
    assert may_act(env, "p-ok") is False


def test_missing_authorized_by_holds():
    clear_spent()
    env = Envelope(
        kind=MsgKind.DECISION.value,
        swarm_id="test-swarm",
        node_id="gate-1",
        role="gate",
        payload={
            "proposal_hash": "p-no-human",
            "outcome": DecisionOutcome.AUTHORIZED.value,
            "what_was_seen": {"summary": "seen"},
            "authorized_by": "",  # empty
            "selected_interpretation": None,
        },
        ttl=FUTURE,
        refs=("p-no-human",),
    ).materialize()
    assert may_act(env, "p-no-human") is False


def test_empty_what_was_seen_holds():
    clear_spent()
    env = _auth(proposal_hash="p-empty-seen", what_was_seen={})
    assert may_act(env, "p-empty-seen") is False


def test_missing_authorized_by_field_holds():
    clear_spent()
    env = Envelope(
        kind=MsgKind.DECISION.value,
        swarm_id="test-swarm",
        node_id="gate-1",
        role="gate",
        payload={
            "proposal_hash": "p-no-field",
            "outcome": DecisionOutcome.AUTHORIZED.value,
            "what_was_seen": {"summary": "seen"},
            # authorized_by omitted
            "selected_interpretation": None,
        },
        ttl=FUTURE,
        refs=("p-no-field",),
    ).materialize()
    assert may_act(env, "p-no-field") is False


def test_intra_process_replay_closed():
    clear_spent()
    env_a = _auth(proposal_hash="p-replay")
    env_b = _auth(proposal_hash="p-replay")
    assert env_a.msg_id != env_b.msg_id
    assert consume(env_a, "p-replay") is True
    assert may_act(env_b, "p-replay") is False


def test_ttl_rules():
    clear_spent()
    assert may_act(_auth(proposal_hash="p-ttl-ok"), "p-ttl-ok") is True
    assert may_act(_auth(proposal_hash="p-ttl-past", ttl=PAST), "p-ttl-past") is False

    missing = Envelope(
        kind=MsgKind.DECISION.value,
        swarm_id="test-swarm",
        node_id="gate-1",
        role="gate",
        payload={
            "proposal_hash": "p-ttl-missing",
            "outcome": DecisionOutcome.AUTHORIZED.value,
            "what_was_seen": {"summary": "seen"},
            "authorized_by": "human-owner",
            "selected_interpretation": None,
        },
        refs=("p-ttl-missing",),
    ).materialize()
    assert missing.ttl is None
    assert may_act(missing, "p-ttl-missing") is False


def test_check_does_not_spend():
    clear_spent()
    env = _auth(proposal_hash="p-check")
    assert may_act(env, "p-check") is True
    assert may_act(env, "p-check") is True
    assert consume(env, "p-check") is True
    assert may_act(env, "p-check") is False


def test_role_still_forgeable_but_human_record_required():
    """Cryptographic sender authenticity is still not claimed.
    An attacker can still stamp role=gate, but without a human record
    may_act holds.  With a forged human record the harness must not
    trust the envelope; the library only checks presence of the fields.
    """
    clear_spent()
    env = _auth(node_id="attacker-node", proposal_hash="p-role")
    assert env.role == "gate"
    assert env.node_id == "attacker-node"
    # presence of human record is enough for the pure library check
    assert may_act(env, "p-role") is True


def test_payload_tampering_is_rejected():
    clear_spent()
    env = _auth(proposal_hash="p-tamper")
    tampered = Envelope(
        kind=env.kind,
        swarm_id=env.swarm_id,
        node_id=env.node_id,
        role=env.role,
        ts=env.ts,
        ttl=env.ttl,
        refs=env.refs,
        payload={**env.payload, "authorized_by": "attacker"},
        msg_id=env.msg_id,
        content_hash=env.content_hash,
    )
    assert tampered.verify() is False
    assert may_act(tampered, "p-tamper") is False


if __name__ == "__main__":
    test_hybrid_happy_path()
    print("hybrid happy path: ok")
    test_missing_authorized_by_holds()
    print("missing authorized_by: hold")
    test_empty_what_was_seen_holds()
    print("empty what_was_seen: hold")
    test_missing_authorized_by_field_holds()
    print("omitted authorized_by field: hold")
    test_intra_process_replay_closed()
    print("intra-process replay: closed")
    test_ttl_rules()
    print("TTL rules: hold on missing/past")
    test_check_does_not_spend()
    print("check vs consume: separated")
    test_role_still_forgeable_but_human_record_required()
    print("role forgeable; human record still required")
    test_payload_tampering_is_rejected()
    print("tamper control: rejected")
    print("All assertions passed.")
