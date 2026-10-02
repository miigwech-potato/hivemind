"""
hivemind channel.py — inter-swarm message shapes

Speech is not permission.
Only a DECISION with outcome AUTHORIZED is 米.
"""

from __future__ import annotations

import hashlib
import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, Set


class MsgKind(str, Enum):
    PING = "PING"
    POTENTIAL = "POTENTIAL"
    THOUGHT = "THOUGHT"
    WEIGHT = "WEIGHT"
    INHIBIT = "INHIBIT"
    QUORUM = "QUORUM"
    PROPOSAL = "PROPOSAL"
    DECISION = "DECISION"
    TRACE = "TRACE"
    HOLD = "HOLD"


class DecisionOutcome(str, Enum):
    AUTHORIZED = "AUTHORIZED"
    HOLD = "HOLD"  # ⏑


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def content_hash(obj: Any) -> str:
    return hashlib.sha256(canonical_json(obj)).hexdigest()


@dataclass(frozen=True)
class Envelope:
    kind: str
    swarm_id: str
    node_id: str
    payload: dict[str, Any]
    msg_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    hive_id: str = "hivemind"
    role: Optional[str] = None
    ts: str = field(default_factory=_utc_now)
    ttl: Optional[str] = None
    refs: tuple[str, ...] = field(default_factory=tuple)
    content_hash: str = ""

    def materialize(self) -> "Envelope":
        """Return a new envelope with content_hash bound to canonical body."""
        body = {
            "kind": self.kind,
            "hive_id": self.hive_id,
            "swarm_id": self.swarm_id,
            "node_id": self.node_id,
            "role": self.role,
            "ts": self.ts,
            "ttl": self.ttl,
            "refs": list(self.refs),
            "payload": self.payload,
        }
        return Envelope(
            msg_id=self.msg_id,
            kind=self.kind,
            hive_id=self.hive_id,
            swarm_id=self.swarm_id,
            node_id=self.node_id,
            role=self.role,
            ts=self.ts,
            ttl=self.ttl,
            refs=self.refs,
            payload=self.payload,
            content_hash=content_hash(body),
        )

    def verify(self) -> bool:
        body = {
            "kind": self.kind,
            "hive_id": self.hive_id,
            "swarm_id": self.swarm_id,
            "node_id": self.node_id,
            "role": self.role,
            "ts": self.ts,
            "ttl": self.ttl,
            "refs": list(self.refs),
            "payload": self.payload,
        }
        return self.content_hash == content_hash(body)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["refs"] = list(self.refs)
        return d


def ping(
    swarm_id: str,
    node_id: str = "external",
    *,
    agent_label: Optional[str] = None,
    read_paths: Optional[list[str]] = None,
    note: Optional[str] = None,
) -> Envelope:
    payload: dict[str, Any] = {}
    if agent_label:
        payload["agent_label"] = agent_label
    if read_paths:
        payload["read_paths"] = read_paths
    if note:
        payload["note"] = note
    return Envelope(
        kind=MsgKind.PING.value,
        swarm_id=swarm_id,
        node_id=node_id,
        payload=payload,
    ).materialize()


def potential(
    swarm_id: str,
    node_id: str,
    branches: list[dict[str, Any]],
    *,
    preparation_hash: str,
    generation_method: Optional[list[str]] = None,
    bind_refs: Optional[list[str]] = None,
) -> Envelope:
    payload = {
        "branches": branches,
        "preparation_hash": preparation_hash,
        "generation_method": generation_method or [],
        "bind_refs": bind_refs or [],
    }
    return Envelope(
        kind=MsgKind.POTENTIAL.value,
        swarm_id=swarm_id,
        node_id=node_id,
        role="scout",
        payload=payload,
        refs=(preparation_hash,),
    ).materialize()


def decision(
    swarm_id: str,
    node_id: str,
    *,
    proposal_hash: str,
    outcome: DecisionOutcome,
    what_was_seen: dict[str, Any],
    authorized_by: str,
    selected_interpretation: Optional[str] = None,
    ttl: str,
) -> Envelope:
    """Build a DECISION envelope under the hybrid authorization model.

    Required:
      - ttl: ISO-8601 UTC, must be future for may_act to pass
      - authorized_by: named human who authorized
      - what_was_seen: non-empty record of what that human saw

    The Gate may still open on a weight count or Queen.approve; the seal
    that may become 米 is that count PLUS this human record.
    Role is stamped "gate".  Cryptographic sender authenticity is not
    claimed (Gate holds no private key).
    """
    payload = {
        "proposal_hash": proposal_hash,
        "outcome": outcome.value,
        "what_was_seen": what_was_seen,
        "authorized_by": authorized_by,
        "selected_interpretation": selected_interpretation,
    }
    return Envelope(
        kind=MsgKind.DECISION.value,
        swarm_id=swarm_id,
        node_id=node_id,
        role="gate",
        payload=payload,
        ttl=ttl,
        refs=(proposal_hash,),
    ).materialize()


def hold(
    swarm_id: str,
    node_id: str,
    reason: str,
    *,
    refs: tuple[str, ...] = (),
) -> Envelope:
    return Envelope(
        kind=MsgKind.HOLD.value,
        swarm_id=swarm_id,
        node_id=node_id,
        payload={"reason": reason},
        refs=refs,
    ).materialize()


# ---------------------------------------------------------------------------
# Replay protection (single-process only)
# ---------------------------------------------------------------------------
# Once a proposal_hash is consumed, further may_act / consume calls for it
# return False inside this process.
# Cross-node / after-restart replay is the harness's duty under the hybrid
# model (durable shared spent store).  The library does not claim to close it.
_spent_proposal_hashes: Set[str] = set()
_spent_lock = threading.Lock()


def _ttl_ok(env: Envelope) -> bool:
    if env.ttl is None:
        return False
    try:
        ttl_dt = datetime.fromisoformat(env.ttl)
        return datetime.now(timezone.utc) < ttl_dt
    except (TypeError, ValueError):
        return False


def _human_record_ok(env: Envelope) -> bool:
    """Hybrid rule: AUTHORIZED must carry a named human + non-empty what_was_seen."""
    authorized_by = env.payload.get("authorized_by")
    if not isinstance(authorized_by, str) or not authorized_by.strip():
        return False
    what = env.payload.get("what_was_seen")
    if not isinstance(what, dict) or len(what) == 0:
        return False
    return True


def may_act(env: Envelope, expected_proposal_hash: str) -> bool:
    """Pure check: verified, non-expired, non-consumed DECISION AUTHORIZED
    that carries a hybrid human authorization record.

    No side effects.  Call consume() only at the moment of action.

    Hybrid model (owner decision):
      Gate may open on count or Queen.approve (no private key).
      The seal that may become 米 also requires authorized_by +
      non-empty what_was_seen.  Without that record → hold.

    Cryptographic sender authenticity is not claimed.
    Replay protection is single-process only (see module comment);
    durable / cross-node spent tracking is the harness's duty.
    """
    if env.kind != MsgKind.DECISION.value:
        return False
    if not env.verify():
        return False
    if env.payload.get("outcome") != DecisionOutcome.AUTHORIZED.value:
        return False
    if env.payload.get("proposal_hash") != expected_proposal_hash:
        return False
    if not _ttl_ok(env):
        return False
    if not _human_record_ok(env):
        return False
    with _spent_lock:
        if expected_proposal_hash in _spent_proposal_hashes:
            return False
    return True


def consume(env: Envelope, expected_proposal_hash: str) -> bool:
    """Spend the approval.  Returns True only if may_act would have
    returned True and the hash was not already spent; then records it.

    Call this exactly once, at the point of external action.
    """
    if not may_act(env, expected_proposal_hash):
        return False
    with _spent_lock:
        # re-check under lock to close the race
        if expected_proposal_hash in _spent_proposal_hashes:
            return False
        _spent_proposal_hashes.add(expected_proposal_hash)
        return True


def may_act_and_consume(env: Envelope, expected_proposal_hash: str) -> bool:
    """Convenience for single-threaded harnesses: check then spend."""
    return consume(env, expected_proposal_hash)


def clear_spent() -> None:
    """Test / process-reset helper.  Not part of the authorization path."""
    with _spent_lock:
        _spent_proposal_hashes.clear()


if __name__ == "__main__":
    p = ping(
        "example-swarm",
        agent_label="visitor",
        read_paths=["flow/BOUNDARIES.flow", "AGENTS.md"],
        note="read-only presence",
    )
    print(json.dumps(p.to_dict(), indent=2))
    print("verify:", p.verify())
    print("may_act on ping:", may_act(p, "nope"))
