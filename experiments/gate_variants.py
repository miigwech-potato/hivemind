"""
Consensus gate variants — same decision task, three open rules.

Audience: harness builders. Swarm / hivemind — not a botfarm.

Variants (how weight accumulates / Gate opens)
  majority              — OPEN when Σ weights ≥ θ
  queen_override        — OPEN when majority OR Queen.approve
  evidence_accumulation — workers integrate private + social evidence
                          until total ≥ θ (slower, noise-tolerant)

Hybrid invariant (unchanged)
  Gate OPEN is not 米. AUTHORIZED that may become 米 still needs
  authorized_by + what_was_seen. Variants never emit the seal alone.

Metrics
  latency_steps, opened, deadlock, correct_choice, hybrid_seal_ok

Run:
  python3 experiments/gate_variants.py
"""
from __future__ import annotations

import random
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from channel import DecisionOutcome, clear_spent, consume, decision, may_act


PROPOSALS = ("alpha", "beta")  # ground truth for quality: alpha is correct


@dataclass
class TrialResult:
    variant: str
    opened: bool
    chosen: Optional[str]
    latency_steps: int
    deadlock: bool
    correct: bool
    hybrid_may_act: bool
    hybrid_consume: bool
    notes: List[str] = field(default_factory=list)


@dataclass
class VariantSummary:
    variant: str
    trials: int
    open_rate: float
    deadlock_rate: float
    mean_latency: float
    accuracy_when_open: float
    hybrid_seal_rate: float
    passed: bool
    notes: List[str] = field(default_factory=list)


def _seed_workers(n: int, noise: float, rng: random.Random) -> List[dict]:
    """Each worker leans toward alpha (correct) with noise toward beta."""
    workers = []
    for i in range(n):
        private = 1.0 - rng.random() * noise
        if rng.random() < noise * 0.5:
            private = -private
        workers.append(
            {
                "id": f"w{i}",
                "private": private,
                "social": 0.0,
                "weight_alpha": 0.0,
                "weight_beta": 0.0,
                "committed": None,
            }
        )
    return workers


def _emit_hybrid(proposal_hash: str, chosen: str) -> Tuple[bool, bool]:
    """Gate opened on count; hybrid seal still required for may_act/consume."""
    clear_spent()
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    env = decision(
        swarm_id="gate-exp",
        node_id="gate-1",
        proposal_hash=proposal_hash,
        outcome=DecisionOutcome.AUTHORIZED,
        what_was_seen={"chosen": chosen, "task": "gate-variant-trial"},
        authorized_by="human-owner",
        ttl=future,
    )
    ok_may = may_act(env, proposal_hash)
    ok_con = consume(env, proposal_hash) if ok_may else False
    return ok_may, ok_con


def run_majority(
    n_workers: int = 9,
    theta: float = 5.0,
    max_steps: int = 40,
    noise: float = 0.35,
    seed: int = 0,
) -> TrialResult:
    rng = random.Random(seed)
    workers = _seed_workers(n_workers, noise, rng)
    notes: List[str] = []

    for step in range(1, max_steps + 1):
        for w in workers:
            if w["private"] >= 0:
                w["weight_alpha"] += abs(w["private"]) * 0.2
            else:
                w["weight_beta"] += abs(w["private"]) * 0.2

        sa = sum(w["weight_alpha"] for w in workers)
        sb = sum(w["weight_beta"] for w in workers)
        if sa >= theta or sb >= theta:
            chosen = "alpha" if sa >= sb else "beta"
            ph = f"maj-{seed}-{step}"
            may_ok, con_ok = _emit_hybrid(ph, chosen)
            return TrialResult(
                variant="majority",
                opened=True,
                chosen=chosen,
                latency_steps=step,
                deadlock=False,
                correct=(chosen == "alpha"),
                hybrid_may_act=may_ok,
                hybrid_consume=con_ok,
                notes=notes,
            )

    notes.append("timeout without Σ≥θ")
    return TrialResult(
        variant="majority",
        opened=False,
        chosen=None,
        latency_steps=max_steps,
        deadlock=True,
        correct=False,
        hybrid_may_act=False,
        hybrid_consume=False,
        notes=notes,
    )


def run_queen_override(
    n_workers: int = 9,
    theta: float = 5.0,
    max_steps: int = 40,
    noise: float = 0.35,
    queen_step: int = 8,
    queen_choice: str = "alpha",
    seed: int = 0,
) -> TrialResult:
    """Majority path, but Queen may open at queen_step regardless of Σ."""
    rng = random.Random(seed)
    workers = _seed_workers(n_workers, noise, rng)
    notes: List[str] = []

    for step in range(1, max_steps + 1):
        for w in workers:
            if w["private"] >= 0:
                w["weight_alpha"] += abs(w["private"]) * 0.15
            else:
                w["weight_beta"] += abs(w["private"]) * 0.15

        sa = sum(w["weight_alpha"] for w in workers)
        sb = sum(w["weight_beta"] for w in workers)

        if step == queen_step:
            chosen = queen_choice
            notes.append(f"Queen.approve at step {step} → {chosen}")
            ph = f"queen-{seed}-{step}"
            may_ok, con_ok = _emit_hybrid(ph, chosen)
            return TrialResult(
                variant="queen_override",
                opened=True,
                chosen=chosen,
                latency_steps=step,
                deadlock=False,
                correct=(chosen == "alpha"),
                hybrid_may_act=may_ok,
                hybrid_consume=con_ok,
                notes=notes,
            )

        if sa >= theta or sb >= theta:
            chosen = "alpha" if sa >= sb else "beta"
            ph = f"queen-maj-{seed}-{step}"
            may_ok, con_ok = _emit_hybrid(ph, chosen)
            return TrialResult(
                variant="queen_override",
                opened=True,
                chosen=chosen,
                latency_steps=step,
                deadlock=False,
                correct=(chosen == "alpha"),
                hybrid_may_act=may_ok,
                hybrid_consume=con_ok,
                notes=notes + ["opened by majority before queen"],
            )

    return TrialResult(
        variant="queen_override",
        opened=False,
        chosen=None,
        latency_steps=max_steps,
        deadlock=True,
        correct=False,
        hybrid_may_act=False,
        hybrid_consume=False,
        notes=["timeout"],
    )


def run_evidence_accumulation(
    n_workers: int = 9,
    theta: float = 4.0,
    max_steps: int = 60,
    noise: float = 0.5,
    seed: int = 0,
) -> TrialResult:
    """Drift-diffusion style: total = private + social; social from neighbors."""
    rng = random.Random(seed)
    workers = _seed_workers(n_workers, noise, rng)
    notes: List[str] = []

    for step in range(1, max_steps + 1):
        privates = [w["private"] for w in workers]
        mean_p = sum(privates) / len(privates)
        for w in workers:
            w["social"] = 0.7 * w["social"] + 0.3 * mean_p
            total = w["private"] + w["social"]
            if total >= 0:
                w["weight_alpha"] += abs(total) * 0.08
            else:
                w["weight_beta"] += abs(total) * 0.08

        sa = sum(w["weight_alpha"] for w in workers)
        sb = sum(w["weight_beta"] for w in workers)
        if sa >= theta or sb >= theta:
            chosen = "alpha" if sa >= sb else "beta"
            ph = f"evid-{seed}-{step}"
            may_ok, con_ok = _emit_hybrid(ph, chosen)
            return TrialResult(
                variant="evidence_accumulation",
                opened=True,
                chosen=chosen,
                latency_steps=step,
                deadlock=False,
                correct=(chosen == "alpha"),
                hybrid_may_act=may_ok,
                hybrid_consume=con_ok,
                notes=notes,
            )

    notes.append("timeout under high noise")
    return TrialResult(
        variant="evidence_accumulation",
        opened=False,
        chosen=None,
        latency_steps=max_steps,
        deadlock=True,
        correct=False,
        hybrid_may_act=False,
        hybrid_consume=False,
        notes=notes,
    )


def summarize(variant: str, trials: List[TrialResult]) -> VariantSummary:
    n = len(trials)
    opened = [t for t in trials if t.opened]
    deadlocks = sum(1 for t in trials if t.deadlock)
    mean_lat = sum(t.latency_steps for t in trials) / n
    acc = sum(1 for t in opened if t.correct) / len(opened) if opened else 0.0
    hybrid = sum(1 for t in opened if t.hybrid_may_act and t.hybrid_consume)
    hybrid_rate = hybrid / len(opened) if opened else 0.0

    notes: List[str] = []
    if opened and hybrid_rate < 1.0:
        notes.append("FAIL: some opens lacked hybrid may_act/consume")
        passed = False
    else:
        notes.append("ok: every Gate open bound to hybrid seal in trial")
        passed = True

    if variant == "majority" and n >= 5:
        notes.append(f"open_rate={len(opened)/n:.2f} deadlock={deadlocks/n:.2f}")
    if variant == "queen_override":
        notes.append("Queen path bounds latency when majority is slow")
    if variant == "evidence_accumulation":
        notes.append("integrates noise over time before open")

    return VariantSummary(
        variant=variant,
        trials=n,
        open_rate=len(opened) / n,
        deadlock_rate=deadlocks / n,
        mean_latency=mean_lat,
        accuracy_when_open=acc,
        hybrid_seal_rate=hybrid_rate,
        passed=passed,
        notes=notes,
    )


def run_suite(n_trials: int = 12, seed0: int = 42) -> List[VariantSummary]:
    results: Dict[str, List[TrialResult]] = {
        "majority": [],
        "queen_override": [],
        "evidence_accumulation": [],
    }
    for i in range(n_trials):
        s = seed0 + i
        results["majority"].append(run_majority(seed=s, noise=0.4))
        results["queen_override"].append(
            run_queen_override(seed=s, noise=0.4, queen_step=6)
        )
        results["evidence_accumulation"].append(
            run_evidence_accumulation(seed=s, noise=0.55)
        )

    return [summarize(k, v) for k, v in results.items()]


def main() -> int:
    t0 = time.monotonic()
    summaries = run_suite()
    elapsed = time.monotonic() - t0
    print("=== GATE VARIANTS ===")
    print(f"(swarm/hivemind experiment · {elapsed:.2f}s)\n")
    print(
        f"{'variant':<24} {'open':>6} {'dead':>6} {'lat':>7} {'acc':>6} {'hybrid':>7}"
    )
    all_pass = True
    for s in summaries:
        print(
            f"{s.variant:<24} {s.open_rate:6.2f} {s.deadlock_rate:6.2f} "
            f"{s.mean_latency:7.1f} {s.accuracy_when_open:6.2f} {s.hybrid_seal_rate:7.2f}"
        )
        for n in s.notes:
            print(f"  {n}")
        if not s.passed:
            all_pass = False
    print()
    print("Rule: variants change how the Gate opens; hybrid still seals 米.")
    print("PASS" if all_pass else "FAIL")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
