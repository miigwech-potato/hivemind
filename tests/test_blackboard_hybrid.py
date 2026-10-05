"""Blackboard coordinates; hybrid seals Acts.

claim/done alone never unlock external consequence.
"""
from __future__ import annotations

import importlib
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["HIVEMIND_BLACKBOARD"] = "/tmp/hivemind_test_board.json"

import blackboard
importlib.reload(blackboard)
import act_path
importlib.reload(act_path)

from act_path import finish_task_if_authorized
from blackboard import BOARD, _atomic, cmd_add, cmd_claim, cmd_done
from channel import DecisionOutcome, clear_spent, decision, may_act

FUTURE = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()


def _reset_board():
    def _op(s):
        s["tasks"] = {}
        s["signals"] = []
        return True

    _atomic(_op)
    clear_spent()


def test_claim_is_not_authorization():
    _reset_board()
    cmd_add("t1", "would touch the outside")
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        cmd_claim("t1", "worker-1")
    assert "True" in buf.getvalue()
    from channel import Envelope, MsgKind
    hold = Envelope(kind=MsgKind.HOLD.value, swarm_id="s", node_id="w", role="worker", payload={"reason": "x"}, refs=()).materialize()
    assert may_act(hold, "p1") is False


def test_done_without_hybrid_does_not_run_side_effect():
    _reset_board()
    cmd_add("t-ext", "external effect task")
    import io
    from contextlib import redirect_stdout

    with redirect_stdout(io.StringIO()):
        cmd_claim("t-ext", "worker-1")

    calls = []
    ok, reason = finish_task_if_authorized(
        "t-ext",
        "worker-1",
        "should not matter",
        decision=None,
        proposal_hash="prop-x",
        side_effect=lambda: calls.append(1),
    )
    assert ok is False
    assert "hold" in reason
    assert calls == []


def test_forged_authorized_without_human_record_holds():
    _reset_board()
    cmd_add("t2", "external")
    import io
    from contextlib import redirect_stdout

    with redirect_stdout(io.StringIO()):
        cmd_claim("t2", "worker-1")

    from channel import Envelope, MsgKind

    forged = Envelope(
        kind=MsgKind.DECISION.value,
        swarm_id="s",
        node_id="g",
        role="gate",
        payload={
            "proposal_hash": "prop-2",
            "outcome": DecisionOutcome.AUTHORIZED.value,
            "what_was_seen": {},
            "authorized_by": "",
            "selected_interpretation": None,
        },
        ttl=FUTURE,
        refs=("prop-2",),
    ).materialize()

    calls = []
    ok, reason = finish_task_if_authorized(
        "t2",
        "worker-1",
        "nope",
        decision=forged,
        proposal_hash="prop-2",
        side_effect=lambda: calls.append(1),
    )
    assert ok is False
    assert calls == []


def test_hybrid_path_runs_side_effect_once():
    _reset_board()
    cmd_add("t3", "authorized external")
    import io
    from contextlib import redirect_stdout

    with redirect_stdout(io.StringIO()):
        cmd_claim("t3", "worker-1")

    env = decision(
        swarm_id="s",
        node_id="gate-1",
        proposal_hash="prop-3",
        outcome=DecisionOutcome.AUTHORIZED,
        what_was_seen={"reviewed": "t3 external effect", "agent": "worker-1"},
        authorized_by="human-owner",
        ttl=FUTURE,
    )
    calls = []
    ok, reason = finish_task_if_authorized(
        "t3",
        "worker-1",
        "effect applied",
        decision=env,
        proposal_hash="prop-3",
        side_effect=lambda: calls.append(1),
    )
    assert ok is True, reason
    assert calls == [1]

    ok2, reason2 = finish_task_if_authorized(
        "t3",
        "worker-1",
        "again",
        decision=env,
        proposal_hash="prop-3",
        side_effect=lambda: calls.append(1),
    )
    assert ok2 is False
    assert calls == [1]


def test_plain_done_still_works_for_non_external_stigmergy():
    """Board-only done remains valid for internal coordination without Act."""
    _reset_board()
    cmd_add("internal", "write a thought only")
    import io
    from contextlib import redirect_stdout

    with redirect_stdout(io.StringIO()):
        cmd_claim("internal", "worker-2")
        cmd_done("internal", "worker-2", "thought recorded on board")
    from blackboard import _read

    s = _read()
    assert s["tasks"]["internal"]["status"] == "done"


if __name__ == "__main__":
    test_claim_is_not_authorization()
    print("claim is not authorization: ok")
    test_done_without_hybrid_does_not_run_side_effect()
    print("no hybrid \u2192 no side effect: ok")
    test_forged_authorized_without_human_record_holds()
    print("forged without human record holds: ok")
    test_hybrid_path_runs_side_effect_once()
    print("hybrid path once: ok")
    test_plain_done_still_works_for_non_external_stigmergy()
    print("plain done for internal: ok")
    print("All blackboard\u2194hybrid assertions passed.")
