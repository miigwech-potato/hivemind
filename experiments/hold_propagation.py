"""
HOLD propagation timing — how fast does the swarm stop?

Audience: harness builders. Not for visiting bots.

Setup
  Workers attempt claim/consume loops.
  At t_hold, a HOLD envelope is observed on the Act path.
  After that, no new consume / side_effect may succeed.

Metrics
  ms_to_last_claim_after_hold
  ms_to_last_side_effect_after_hold
  side_effects_after_hold (must be 0)
  claims_after_hold (board may still claim — coordination only;
                     Act path must be zero)

Run:
  python3 experiments/hold_propagation.py
"""
from __future__ import annotations

import importlib
import io
import os
import sys
import time
from contextlib import redirect_stdout
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["HIVEMIND_BLACKBOARD"] = "/tmp/hivemind_hold_board.json"

import blackboard

importlib.reload(blackboard)
from blackboard import BOARD, _atomic, cmd_add, cmd_claim, cmd_done
from channel import (
    DecisionOutcome,
    clear_spent,
    consume,
    decision,
    hold,
    may_act,
)


@dataclass
class HoldReport:
    workers: int
    tasks: int
    t_hold_monotonic: float
    last_claim_after_hold_ms: Optional[float]
    last_side_effect_after_hold_ms: Optional[float]
    claims_after_hold: int
    side_effects_after_hold: int
    holds_emitted: int
    passed: bool
    notes: List[str]


def _reset() -> None:
    clear_spent()
    if Path(BOARD).exists():
        Path(BOARD).unlink()
    blackboard._ensure_board()

    def _op(s):
        s["tasks"] = {}
        s["signals"] = []
        return True

    _atomic(_op)


def _silent(fn, *args):
    buf = io.StringIO()
    with redirect_stdout(buf):
        fn(*args)
    return buf.getvalue().strip()


def run_hold_propagation(
    n_workers: int = 5,
    n_tasks: int = 15,
    pre_hold_steps: int = 8,
    post_hold_steps: int = 12,
) -> HoldReport:
    _reset()
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    notes: List[str] = []

    for i in range(n_tasks):
        _silent(cmd_add, f"h{i}", f"hold-exp task {i}")

    seals = {}
    for i in range(n_tasks):
        seals[f"h{i}"] = decision(
            swarm_id="s",
            node_id="gate",
            proposal_hash=f"ph-{i}",
            outcome=DecisionOutcome.AUTHORIZED,
            what_was_seen={"task": f"h{i}"},
            authorized_by="human-owner",
            ttl=future,
        )

    side_effects = []
    claims_after = 0
    effects_after = 0
    last_claim_t: Optional[float] = None
    last_effect_t: Optional[float] = None
    hold_seen = False
    t_hold = 0.0
    holds_emitted = 0

    harness_hold = {"active": False, "env": None}

    def observe_hold(reason: str) -> None:
        nonlocal holds_emitted, t_hold, hold_seen
        env = hold("s", "worker-halt", reason, refs=())
        harness_hold["active"] = True
        harness_hold["env"] = env
        holds_emitted += 1
        if not hold_seen:
            t_hold = time.monotonic()
            hold_seen = True

    def try_act(worker: str, task_id: str) -> None:
        nonlocal claims_after, effects_after, last_claim_t, last_effect_t
        out = _silent(cmd_claim, task_id, worker)
        now = time.monotonic()
        if out == "True" and hold_seen:
            claims_after += 1
            last_claim_t = now

        if harness_hold["active"]:
            notes.append(f"act refused under HOLD for {task_id}")
            return

        env = seals.get(task_id)
        if env is None:
            return
        if not may_act(env, env.payload["proposal_hash"]):
            return
        if not consume(env, env.payload["proposal_hash"]):
            return

        def _effect():
            side_effects.append(task_id)

        _effect()
        _silent(cmd_done, task_id, worker, "acted")
        if hold_seen:
            effects_after += 1
            last_effect_t = time.monotonic()

    step = 0
    task_ids = [f"h{i}" for i in range(n_tasks)]
    while step < pre_hold_steps + post_hold_steps:
        worker = f"w{step % n_workers}"
        tid = task_ids[step % n_tasks]
        if step == pre_hold_steps:
            observe_hold("adversary or safety trip — stop external Acts")
        try_act(worker, tid)
        step += 1

    last_claim_ms = (
        (last_claim_t - t_hold) * 1000.0 if last_claim_t and hold_seen else None
    )
    last_effect_ms = (
        (last_effect_t - t_hold) * 1000.0 if last_effect_t and hold_seen else None
    )

    passed = effects_after == 0 and holds_emitted >= 1
    if effects_after != 0:
        notes.append(f"FAIL: {effects_after} side effects after HOLD")
    else:
        notes.append("ok: zero side effects after HOLD observed")
    if claims_after:
        notes.append(
            f"note: {claims_after} board claims after HOLD (coordination only; not 米)"
        )
    notes.append(f"holds_emitted={holds_emitted}")
    notes.append(f"last_claim_after_hold_ms={last_claim_ms}")
    notes.append(f"last_side_effect_after_hold_ms={last_effect_ms}")

    return HoldReport(
        workers=n_workers,
        tasks=n_tasks,
        t_hold_monotonic=t_hold,
        last_claim_after_hold_ms=last_claim_ms,
        last_side_effect_after_hold_ms=last_effect_ms,
        claims_after_hold=claims_after,
        side_effects_after_hold=effects_after,
        holds_emitted=holds_emitted,
        passed=passed,
        notes=notes,
    )


def main() -> int:
    rep = run_hold_propagation()
    print("=== HOLD PROPAGATION ===")
    print(f"workers={rep.workers} tasks={rep.tasks}")
    print(f"side_effects_after_hold={rep.side_effects_after_hold} (expect 0)")
    print(f"claims_after_hold={rep.claims_after_hold} (board only)")
    for n in rep.notes:
        print(f"  {n}")
    print("PASS" if rep.passed else "FAIL")
    return 0 if rep.passed else 1


if __name__ == "__main__":
    sys.exit(main())
