"""Wire experiments 1–2 into the test suite."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.adversarial_workers import (
    run_freeloader_blocks_dependents,
    run_hog_unmitigated,
    run_hog_with_claim_ttl,
    run_liar_false_result_not_act,
)
from experiments.hold_propagation import run_hold_propagation


def test_hog_gap_is_detectable():
    r = run_hog_unmitigated()
    assert r.passed, r.notes


def test_hog_mitigated_by_claim_ttl():
    r = run_hog_with_claim_ttl()
    assert r.passed, r.notes
    assert r.honest_claims > 0 or "done" in str(r.notes)


def test_freeloader_blocks_dependents():
    r = run_freeloader_blocks_dependents()
    assert r.passed, r.notes


def test_liar_cannot_unlock_act():
    r = run_liar_false_result_not_act()
    assert r.passed, r.notes


def test_hold_stops_side_effects():
    r = run_hold_propagation()
    assert r.passed, r.notes
    assert r.side_effects_after_hold == 0


if __name__ == "__main__":
    test_hog_gap_is_detectable()
    print("hog gap finding: ok")
    test_hog_mitigated_by_claim_ttl()
    print("hog + claim TTL: ok")
    test_freeloader_blocks_dependents()
    print("freeloader: ok")
    test_liar_cannot_unlock_act()
    print("liar: ok")
    test_hold_stops_side_effects()
    print("hold propagation: ok")
    print("All experiment safety tests passed.")
