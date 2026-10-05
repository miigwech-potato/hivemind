"""Executable map of HOW_TO_BREAK_YOUR_HARNESS.md (14 cases)."""
from __future__ import annotations

import importlib
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["HIVEMIND_BLACKBOARD"] = "/tmp/hivemind_break_board.json"

import blackboard
importlib.reload(blackboard)
import act_path
importlib.reload(act_path)

from act_path import finish_task_if_authorized
from blackboard import _atomic, cmd_add, cmd_claim, cmd_done
from channel import (
    DecisionOutcome,
    Envelope,
    MsgKind,
    clear_spent,
    consume,
    decision,
    may_act,
)
from spent_store import FileSpentStore, MemorySpentStore, set_channel_spent_backend

FUTURE = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
PAST = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()


def _auth(proposal="p1", **kwargs):
    kw = dict(
        swarm_id="s",
        node_id="gate-1",
        proposal_hash=proposal,
        outcome=DecisionOutcome.AUTHORIZED,
        what_was_seen={"seen": True},
        authorized_by="human-owner",
        ttl=FUTURE,
    )
    kw.update(kwargs)
    return decision(**kw)


def _reset():
    set_channel_spent_backend(None)
    clear_spent()

    def _op(s):
        s["tasks"] = {}
        s["signals"] = []
        return True

    _atomic(_op)


def test_01_role_forged_without_human_record():
    _reset()
    forged = Envelope(
        kind=MsgKind.DECISION.value,
        swarm_id="s",
        node_id="worker",
        role="gate",
        payload={
            "proposal_hash": "p1",
            "outcome": DecisionOutcome.AUTHORIZED.value,
            "what_was_seen": {},
            "authorized_by": "",
            "selected_interpretation": None,
        },
        ttl=FUTURE,
        refs=("p1",),
    ).materialize()
    assert may_act(forged, "p1") is False


def test_02_intra_process_replay():
    _reset()
    env = _auth("p-replay")
    assert consume(env, "p-replay") is True
    assert may_act(env, "p-replay") is False
    assert consume(env, "p-replay") is False


def test_03_durable_spent_survives_new_store_instance():
    _reset()
    path = "/tmp/hivemind_spent_break.json"
    if os.path.exists(path):
        os.remove(path)
    store = FileSpentStore(path)
    set_channel_spent_backend(store)
    env = _auth("p-dur")
    assert consume(env, "p-dur") is True
    set_channel_spent_backend(None)
    clear_spent()
    store2 = FileSpentStore(path)
    set_channel_spent_backend(store2)
    assert may_act(env, "p-dur") is False
    assert consume(env, "p-dur") is False
    set_channel_spent_backend(None)
    os.remove(path)


def test_04_missing_ttl():
    _reset()
    env = Envelope(
        kind=MsgKind.DECISION.value,
        swarm_id="s",
        node_id="g",
        role="gate",
        payload={
            "proposal_hash": "p4",
            "outcome": DecisionOutcome.AUTHORIZED.value,
            "what_was_seen": {"x": 1},
            "authorized_by": "h",
            "selected_interpretation": None,
        },
        ttl=None,
        refs=("p4",),
    ).materialize()
    assert may_act(env, "p4") is False


def test_05_expired_ttl():
    _reset()
    env = _auth("p5", ttl=PAST)
    assert may_act(env, "p5") is False


def test_06_empty_authorized_by():
    _reset()
    env = _auth("p6", authorized_by="  ")
    assert may_act(env, "p6") is False


def test_07_empty_what_was_seen():
    _reset()
    env = _auth("p7", what_was_seen={})
    assert may_act(env, "p7") is False


def test_08_tampered_content_hash():
    _reset()
    env = _auth("p8")
    bad = Envelope(
        kind=env.kind,
        swarm_id=env.swarm_id,
        node_id=env.node_id,
        role=env.role,
        payload={**env.payload, "authorized_by": "attacker"},
        msg_id=env.msg_id,
        hive_id=env.hive_id,
        ts=env.ts,
        ttl=env.ttl,
        refs=env.refs,
        content_hash=env.content_hash,
    )
    assert bad.verify() is False
    assert may_act(bad, "p8") is False


def test_09_claim_not_permission():
    _reset()
    import io
    from contextlib import redirect_stdout

    with redirect_stdout(io.StringIO()):
        cmd_add("ext-9", "external")
        cmd_claim("ext-9", "w1")
    calls = []
    ok, _ = finish_task_if_authorized(
        "ext-9",
        "w1",
        "x",
        decision=None,
        proposal_hash="p9",
        side_effect=lambda: calls.append(1),
    )
    assert ok is False and calls == []


def test_10_plain_done_internal_ok_external_needs_path():
    _reset()
    import io
    from contextlib import redirect_stdout

    with redirect_stdout(io.StringIO()):
        cmd_add("int-10", "thought only")
        cmd_claim("int-10", "w1")
        cmd_done("int-10", "w1", "ok")
    from blackboard import _read

    assert _read()["tasks"]["int-10"]["status"] == "done"
    with redirect_stdout(io.StringIO()):
        cmd_add("ext-10", "external")
        cmd_claim("ext-10", "w1")
    calls = []
    ok, _ = finish_task_if_authorized(
        "ext-10",
        "w1",
        "x",
        decision=None,
        proposal_hash="p10",
        side_effect=lambda: calls.append(1),
    )
    assert ok is False and calls == []


def test_11_claim_race_one_winner():
    _reset()
    import io
    from contextlib import redirect_stdout

    with redirect_stdout(io.StringIO()):
        cmd_add("race-11", "one task")
    buf_a, buf_b = io.StringIO(), io.StringIO()
    with redirect_stdout(buf_a):
        cmd_claim("race-11", "a")
    with redirect_stdout(buf_b):
        cmd_claim("race-11", "b")
    results = {buf_a.getvalue().strip(), buf_b.getvalue().strip()}
    assert results == {"True", "False"}


def test_12_done_by_non_claimer():
    _reset()
    import io
    from contextlib import redirect_stdout

    with redirect_stdout(io.StringIO()):
        cmd_add("t12", "task")
        cmd_claim("t12", "a")
    buf = io.StringIO()
    with redirect_stdout(buf):
        cmd_done("t12", "b", "stolen")
    assert "False" in buf.getvalue()
    from blackboard import _read

    assert _read()["tasks"]["t12"]["status"] == "claimed"


def test_13_pressure_no_record_zero_tools():
    _reset()
    calls = []
    env = Envelope(
        kind=MsgKind.DECISION.value,
        swarm_id="s",
        node_id="w",
        role="gate",
        payload={
            "proposal_hash": "relief",
            "outcome": DecisionOutcome.AUTHORIZED.value,
            "what_was_seen": {},
            "authorized_by": "",
            "selected_interpretation": "relief",
        },
        ttl=FUTURE,
        refs=("relief",),
    ).materialize()
    if may_act(env, "relief"):
        calls.append(1)
        consume(env, "relief")
    assert calls == []


def test_14_claim_without_human_record():
    _reset()
    import io
    from contextlib import redirect_stdout

    with redirect_stdout(io.StringIO()):
        cmd_add("t14", "tool task")
        cmd_claim("t14", "w1")
    env = Envelope(
        kind=MsgKind.DECISION.value,
        swarm_id="s",
        node_id="g",
        role="gate",
        payload={
            "proposal_hash": "p14",
            "outcome": DecisionOutcome.AUTHORIZED.value,
            "what_was_seen": {},
            "authorized_by": "",
            "selected_interpretation": None,
        },
        ttl=FUTURE,
        refs=("p14",),
    ).materialize()
    calls = []
    ok, _ = finish_task_if_authorized(
        "t14",
        "w1",
        "x",
        decision=env,
        proposal_hash="p14",
        side_effect=lambda: calls.append(1),
    )
    assert ok is False and calls == []


def test_memory_spent_backend():
    _reset()
    set_channel_spent_backend(MemorySpentStore())
    env = _auth("p-mem")
    assert consume(env, "p-mem") is True
    assert consume(env, "p-mem") is False
    set_channel_spent_backend(None)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"{t.__name__}: ok")
    print(f"All {len(tests)} break-harness cases passed.")
