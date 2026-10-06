# Experiments (harness builders)

Runnable safety experiments. **Swarm / hivemind** — not a botfarm.

## 1. Adversarial workers

```bash
python3 experiments/adversarial_workers.py
```

| Adversary | Finding |
|-----------|---------|
| **Hog** (claims all, never done) | Without claim TTL, monopolizes the board. With `reclaim_stale`, honest workers recover. |
| **Freeloader** | Dependents stay blocked; non-claimer cannot complete. |
| **Liar** | False board `result` is speech only; hybrid seal still required for Act. |

Claim TTL: `python3 blackboard.py reclaim <seconds>` or `cmd_reclaim_stale`.

## 2. HOLD propagation

```bash
python3 experiments/hold_propagation.py
```

After HOLD is observed on the Act path: **zero side effects**. Board claims may continue (coordination ≠ 米). Measure `last_*_after_hold_ms`.

## 3. Consensus gate variants

```bash
python3 experiments/gate_variants.py
python3 tests/test_gate_variants.py
```

Same decision task under **majority**, **queen_override**, and **evidence_accumulation**.
Reports open rate, deadlock, mean latency, accuracy, hybrid seal rate.
Variants open the Gate; hybrid still seals 米.

## Tests

```bash
python3 tests/test_experiments_safety.py
python3 tests/test_gate_variants.py
```

## Later (not built yet)

4. Stigmergy at scale · 5. Scout flooding · 6. Two-swarm diplomacy
