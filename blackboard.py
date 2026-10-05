#!/usr/bin/env python3
"""
Stigmergy blackboard — the swarm's shared environment.

Workers NEVER message each other. They coordinate purely by reading and
writing this shared state, the way ants coordinate through pheromone trails.

All mutations are atomic (file lock + check-and-set), so two workers can
race to claim the same task and exactly one will win.

CLI for workers:
    python3 blackboard.py board                  # full board summary
    python3 blackboard.py available              # tasks ready to claim (deps met)
    python3 blackboard.py claim <task> <agent>   # prints True/False
    python3 blackboard.py done <task> <agent> "<result>"   # prints True/False
    python3 blackboard.py signal <agent> <type> "<message>"
    python3 blackboard.py signals                # recent signal trail
    python3 blackboard.py result <task>          # result of a finished task
    python3 blackboard.py reclaim <seconds>      # reopen stale claims (claim TTL)
"""
from __future__ import annotations

import fcntl
import json
import os
import sys
import time
from typing import Any, Callable

BOARD = os.environ.get(
    "HIVEMIND_BLACKBOARD",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "blackboard.json"),
)


def _ensure_board() -> None:
    """Create a minimal board file if missing."""
    if os.path.exists(BOARD):
        return
    seed = {
        "tasks": {},
        "signals": [],
    }
    with open(BOARD, "w") as f:
        json.dump(seed, f, indent=2)
        f.write("\n")


def _atomic(fn: Callable[[dict[str, Any]], Any]) -> Any:
    """Run fn(state) under an exclusive lock; fn may mutate state."""
    _ensure_board()
    with open(BOARD, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            state = json.load(f)
            if "tasks" not in state:
                state["tasks"] = {}
            if "signals" not in state:
                state["signals"] = []
            outcome = fn(state)
            f.seek(0)
            f.truncate()
            json.dump(state, f, indent=2)
            f.write("\n")
            return outcome
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _read() -> dict[str, Any]:
    _ensure_board()
    with open(BOARD) as f:
        state = json.load(f)
    if "tasks" not in state:
        state["tasks"] = {}
    if "signals" not in state:
        state["signals"] = []
    return state


def _deps_met(state: dict[str, Any], task: dict[str, Any]) -> bool:
    return all(
        state["tasks"].get(d, {}).get("status") == "done" for d in task.get("needs", [])
    )


def cmd_board() -> None:
    s = _read()
    print("=== TASKS ===")
    if not s["tasks"]:
        print("(none)")
    for tid, t in s["tasks"].items():
        needs = ",".join(t.get("needs", [])) or "-"
        print(
            f"{tid} [{t.get('status', '?'):7}] "
            f"claimed_by={t.get('claimed_by', '-'):8} "
            f"needs={needs} :: {t.get('desc', '')}"
        )
        if t.get("result"):
            print(f"         result: {t['result']}")
    print("=== SIGNALS (last 12) ===")
    for sig in s["signals"][-12:]:
        extra = f" task={sig['task']}" if sig.get("task") else ""
        msg = f" :: {sig['message']}" if sig.get("message") else ""
        print(f"{sig.get('from', '?'):8} {sig.get('type', '?'):6}{extra}{msg}")
    if not s["signals"]:
        print("(none)")


def cmd_available() -> None:
    s = _read()
    avail = [
        tid
        for tid, t in s["tasks"].items()
        if t.get("status") == "open" and _deps_met(s, t)
    ]
    for tid in avail:
        print(f"{tid} :: {s['tasks'][tid].get('desc', '')}")
    if not avail:
        print("(none)")


def cmd_claim(task_id: str, agent: str) -> None:
    def _op(s: dict[str, Any]) -> bool:
        t = s["tasks"].get(task_id)
        if t and t.get("status") == "open" and _deps_met(s, t):
            t["status"] = "claimed"
            t["claimed_by"] = agent
            t["claimed_at"] = time.time()
            s["signals"].append(
                {
                    "ts": time.time(),
                    "from": agent,
                    "type": "claim",
                    "task": task_id,
                }
            )
            return True
        return False

    print(_atomic(_op))


def cmd_done(task_id: str, agent: str, result: str) -> None:
    def _op(s: dict[str, Any]) -> bool:
        t = s["tasks"].get(task_id)
        if t and t.get("status") == "claimed" and t.get("claimed_by") == agent:
            t["status"] = "done"
            t["result"] = result
            t["done_at"] = time.time()
            s["signals"].append(
                {
                    "ts": time.time(),
                    "from": agent,
                    "type": "done",
                    "task": task_id,
                }
            )
            return True
        return False

    print(_atomic(_op))


def cmd_signal(agent: str, sig_type: str, message: str) -> None:
    def _op(s: dict[str, Any]) -> bool:
        s["signals"].append(
            {
                "ts": time.time(),
                "from": agent,
                "type": sig_type,
                "message": message,
            }
        )
        return True

    print(_atomic(_op))


def cmd_signals() -> None:
    s = _read()
    for sig in s["signals"][-20:]:
        extra = f" task={sig['task']}" if sig.get("task") else ""
        msg = f" :: {sig['message']}" if sig.get("message") else ""
        print(f"{sig.get('from', '?'):8} {sig.get('type', '?'):6}{extra}{msg}")
    if not s["signals"]:
        print("(none)")


def cmd_result(task_id: str) -> None:
    s = _read()
    t = s["tasks"].get(task_id)
    if not t:
        print("(no such task)")
        return
    if t.get("status") != "done":
        print(f"(not done; status={t.get('status')})")
        return
    print(t.get("result", ""))


def cmd_add(task_id: str, desc: str, needs: str = "") -> None:
    """Optional helper: add an open task (harness / Queen side)."""
    need_list = [n for n in needs.split(",") if n.strip()] if needs else []

    def _op(s: dict[str, Any]) -> bool:
        if task_id in s["tasks"]:
            return False
        s["tasks"][task_id] = {
            "status": "open",
            "desc": desc,
            "needs": need_list,
            "claimed_by": None,
            "result": None,
        }
        s["signals"].append(
            {
                "ts": time.time(),
                "from": "board",
                "type": "add",
                "task": task_id,
                "message": desc,
            }
        )
        return True

    print(_atomic(_op))


def cmd_reclaim_stale(max_age_s: float) -> None:
    """Harness helper: reopen claimed tasks older than max_age_s (claim TTL).

    Mitigates hog monopolizing the board. Prints count reclaimed.
    """

    def _op(s: dict[str, Any]) -> int:
        now = time.time()
        n = 0
        for tid, t in s["tasks"].items():
            if t.get("status") != "claimed":
                continue
            claimed_at = t.get("claimed_at") or 0
            if now - float(claimed_at) >= max_age_s:
                t["status"] = "open"
                t["claimed_by"] = None
                t["claimed_at"] = None
                s["signals"].append(
                    {
                        "ts": now,
                        "from": "board",
                        "type": "reclaim",
                        "task": tid,
                        "message": f"stale after {max_age_s}s",
                    }
                )
                n += 1
        return n

    print(_atomic(_op))


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]
    try:
        if cmd == "board":
            cmd_board()
        elif cmd == "available":
            cmd_available()
        elif cmd == "claim" and len(argv) >= 4:
            cmd_claim(argv[2], argv[3])
        elif cmd == "done" and len(argv) >= 5:
            cmd_done(argv[2], argv[3], argv[4])
        elif cmd == "signal" and len(argv) >= 5:
            cmd_signal(argv[2], argv[3], argv[4])
        elif cmd == "signals":
            cmd_signals()
        elif cmd == "result" and len(argv) >= 3:
            cmd_result(argv[2])
        elif cmd == "add" and len(argv) >= 4:
            needs = argv[4] if len(argv) >= 5 else ""
            cmd_add(argv[2], argv[3], needs)
        elif cmd == "reclaim" and len(argv) >= 3:
            cmd_reclaim_stale(float(argv[2]))
        else:
            print(__doc__)
            return 1
    except FileNotFoundError:
        print(f"board missing: {BOARD}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"board corrupt: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
