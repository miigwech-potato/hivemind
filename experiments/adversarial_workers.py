"""
Adversarial worker behaviors on the stigmergy board.

Audience: harness builders. Not for visiting bots.
Swarm / hivemind — never botfarm.

Behaviors
  hog         — claims every open task it can see
  freeloader  — claims once, never completes
  liar        — completes with a false result string

Invariant under test
  "No single node may become the whole."
  Board speech is never 米. External consequence still requires hybrid seal.

Run:
  python3 experiments/adversarial_workers.py
"""
from __future__ import annotations

import importlib
import io
import os
import sys
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["HIVEMIND_BLACKBOARD"] = "/tmp/hivemind_adversarial_board.json"

import blackboard

importlib.reload(blackboard)
from blackboard import BOARD, _atomic, _read, cmd_add, cmd_available, cmd_claim, cmd_done


@dataclass
class RunReport:
    name: str
    notes: List[str] = field(default_factory=list)
    hog_claims: int = 0
    honest_claims: int = 0
    freeloader_stuck: int = 0
    liar_done: int = 0
    dependents_blocked: int = 0
    false_results: int = 0
    passed: bool = True

    def fail(self, msg: str) -> None:
        self.passed = False
        self.notes.append("FAIL: " + msg)

    def ok(self, msg: str) -> None:
        self.notes.append("ok: " + msg)


def _reset_board() -> None:
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


def seed_pipeline(n_independent: int = 6, n_dependent: int = 3) -> None:
    for i in range(n_independent):
        _silent(cmd_add, f"t{i}", f"independent work {i}")
    for i in range(n_dependent):
        need = f"t{i}"
        _silent(cmd_add, f"d{i}", f"depends on {need}", need)


def run_hog_unmitigated() -> RunReport:
    """Without claim TTL, hog can monopolize — finding, not a seal bypass."""
    _reset_board()
    seed_pipeline(6, 0)
    r = RunReport("hog_unmitigated_gap")

    for _ in range(10):
        avail = _silent(cmd_available)
        if avail and avail != "(none)":
            for line in avail.splitlines():
                tid = line.split(" :: ", 1)[0].strip()
                if _silent(cmd_claim, tid, "hog") == "True":
                    r.hog_claims += 1
        avail = _silent(cmd_available)
        if avail and avail != "(none)":
            tid = avail.splitlines()[0].split(" :: ", 1)[0].strip()
            if _silent(cmd_claim, tid, "honest") == "True":
                r.honest_claims += 1
                _silent(cmd_done, tid, "honest", f"result-{tid}")

    s = _read()
    hog_held = [
        tid
        for tid, t in s["tasks"].items()
        if t.get("status") == "claimed" and t.get("claimed_by") == "hog"
    ]
    done = [tid for tid, t in s["tasks"].items() if t.get("status") == "done"]
    r.notes.append(
        f"hog_claims={r.hog_claims} honest_done={len(done)} hog_held={len(hog_held)}"
    )
    if len(hog_held) == len(s["tasks"]) and len(done) == 0:
        r.ok("FINDING: without claim TTL, hog held every task — gap confirmed")
    elif len(done) == 0 and r.hog_claims > 0:
        r.ok("FINDING: hog stalled progress; claim TTL required")
    else:
        r.ok("hog did not fully monopolize in this seed (nondeterministic schedule)")
    return r


def run_hog_with_claim_ttl(max_age_s: float = 0.05, rounds: int = 30) -> RunReport:
    """With reclaim_stale, honest workers can recover tasks hog abandoned."""
    from blackboard import cmd_reclaim_stale
    import time

    _reset_board()
    seed_pipeline(6, 0)
    r = RunReport("hog_with_claim_ttl")

    for _ in range(rounds):
        avail = _silent(cmd_available)
        if avail and avail != "(none)":
            for line in avail.splitlines():
                tid = line.split(" :: ", 1)[0].strip()
                if _silent(cmd_claim, tid, "hog") == "True":
                    r.hog_claims += 1
        time.sleep(max_age_s * 1.1)
        _silent(cmd_reclaim_stale, max_age_s)
        avail = _silent(cmd_available)
        if avail and avail != "(none)":
            tid = avail.splitlines()[0].split(" :: ", 1)[0].strip()
            if _silent(cmd_claim, tid, "honest") == "True":
                r.honest_claims += 1
                _silent(cmd_done, tid, "honest", f"result-{tid}")

    s = _read()
    done = [tid for tid, t in s["tasks"].items() if t.get("status") == "done"]
    hog_held = [
        tid
        for tid, t in s["tasks"].items()
        if t.get("status") == "claimed" and t.get("claimed_by") == "hog"
    ]
    r.notes.append(
        f"hog_claims={r.hog_claims} honest_claims={r.honest_claims} done={len(done)} hog_held={len(hog_held)}"
    )
    if len(done) == 0:
        r.fail("claim TTL did not restore honest progress")
    else:
        r.ok("claim TTL reaper restored honest completions; hog is not the whole")
    if len(hog_held) == len(s["tasks"]):
        r.fail("hog still holds every task after reclaim")
    return r


def run_freeloader_blocks_dependents() -> RunReport:
    """Freeloader claims a prerequisite; dependents must not become available."""
    _reset_board()
    r = RunReport("freeloader")
    _silent(cmd_add, "prereq", "must finish first")
    _silent(cmd_add, "child", "needs prereq", "prereq")

    if _silent(cmd_claim, "prereq", "freeloader") != "True":
        r.fail("freeloader failed to claim prereq")
        return r

    avail = _silent(cmd_available)
    if "child" in avail:
        r.fail("child became available while prereq only claimed, not done")
    else:
        r.ok("child correctly blocked while freeloader holds prereq undone")
        r.dependents_blocked = 1
        r.freeloader_stuck = 1

    if _silent(cmd_done, "prereq", "honest", "stolen") != "False":
        r.fail("non-claimer was allowed to complete freeloader task")
    else:
        r.ok("non-claimer cannot complete freeloader's task")
    return r


def run_liar_false_result_not_act() -> RunReport:
    """Liar writes a false board result; that is speech, not 米."""
    _reset_board()
    r = RunReport("liar")
    from datetime import datetime, timedelta, timezone

    from act_path import finish_task_if_authorized
    from channel import DecisionOutcome, Envelope, MsgKind, clear_spent

    clear_spent()
    _silent(cmd_add, "ext", "external-looking task")
    if _silent(cmd_claim, "ext", "liar") != "True":
        r.fail("liar could not claim")
        return r

    if _silent(cmd_done, "ext", "liar", "FALSE: all systems safe") != "True":
        r.fail("liar could not mark done on board")
        return r
    r.liar_done = 1
    r.false_results = 1

    s = _read()
    if s["tasks"]["ext"].get("result") != "FALSE: all systems safe":
        r.fail("false result not recorded")
    else:
        r.ok("liar wrote false result on board (speech)")

    calls = []
    _silent(cmd_add, "ext2", "needs seal")
    _silent(cmd_claim, "ext2", "liar")
    ok, reason = finish_task_if_authorized(
        "ext2",
        "liar",
        "FALSE: acted",
        decision=None,
        proposal_hash="lie-1",
        side_effect=lambda: calls.append(1),
    )
    if ok or calls:
        r.fail("liar reached external side effect without hybrid seal")
    else:
        r.ok("false board result did not unlock external Act")

    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    forged = Envelope(
        kind=MsgKind.DECISION.value,
        swarm_id="s",
        node_id="liar",
        role="gate",
        payload={
            "proposal_hash": "lie-2",
            "outcome": DecisionOutcome.AUTHORIZED.value,
            "what_was_seen": {},
            "authorized_by": "",
            "selected_interpretation": None,
        },
        ttl=future,
        refs=("lie-2",),
    ).materialize()
    ok2, _ = finish_task_if_authorized(
        "ext2",
        "liar",
        "FALSE",
        decision=forged,
        proposal_hash="lie-2",
        side_effect=lambda: calls.append(1),
    )
    if ok2 or calls:
        r.fail("forged AUTHORIZED without human record unlocked Act")
    else:
        r.ok("forged seal without human record held")
    return r


def main() -> int:
    reports = [
        run_hog_unmitigated(),
        run_hog_with_claim_ttl(),
        run_freeloader_blocks_dependents(),
        run_liar_false_result_not_act(),
    ]
    print("=== ADVERSARIAL WORKERS ===")
    all_pass = True
    for rep in reports:
        status = "PASS" if rep.passed else "FAIL"
        print(f"\n[{status}] {rep.name}")
        for n in rep.notes:
            print(f"  {n}")
        if not rep.passed:
            all_pass = False
    print("\nSummary:", "all passed" if all_pass else "failures present")
    print(
        "Note: hog can stall claimed tasks until a claim-TTL/reaper exists; "
        "that is a harness gap, not a hybrid-seal bypass."
    )
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
