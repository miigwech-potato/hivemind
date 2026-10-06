"""Gate variants experiment: open rules + hybrid seal invariant."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.gate_variants import (
    run_evidence_accumulation,
    run_majority,
    run_queen_override,
    run_suite,
)


def test_majority_can_open_and_seals():
    t = run_majority(seed=1, noise=0.2, theta=3.0)
    if t.opened:
        assert t.hybrid_may_act and t.hybrid_consume
        assert t.chosen in ("alpha", "beta")


def test_queen_bounds_latency():
    t = run_queen_override(seed=2, queen_step=5, noise=0.9, theta=100.0)
    assert t.opened is True
    assert t.latency_steps == 5
    assert t.hybrid_may_act and t.hybrid_consume


def test_evidence_under_noise():
    t = run_evidence_accumulation(seed=3, noise=0.6, max_steps=80)
    if t.opened:
        assert t.hybrid_may_act and t.hybrid_consume


def test_suite_hybrid_invariant():
    summaries = run_suite(n_trials=8, seed0=7)
    assert all(s.passed for s in summaries)
    assert all(s.hybrid_seal_rate == 1.0 or s.open_rate == 0.0 for s in summaries)


if __name__ == "__main__":
    test_majority_can_open_and_seals()
    print("majority: ok")
    test_queen_bounds_latency()
    print("queen: ok")
    test_evidence_under_noise()
    print("evidence: ok")
    test_suite_hybrid_invariant()
    print("suite hybrid: ok")
    print("All gate variant tests passed.")
