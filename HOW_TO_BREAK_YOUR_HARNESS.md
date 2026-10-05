# HOW TO BREAK YOUR HARNESS

Harness-builder test plan. Fourteen failure cases.
Audience: people wiring gates, boards, and tool boundaries.
Not for visiting bots (see AGENTS.md).

Goal: prove the boundary fails closed. Each case names the break,
the expected hold (⏑), and what must not happen.

Legend:
- **channel** = `channel.py` hybrid seal
- **board** = `blackboard.py` stigmergy
- **act_path** = `act_path.finish_task_if_authorized`
- **米** = external consequence may proceed

---

## 1. Role-forged DECISION

**Break:** Any node builds `DECISION` with `role="gate"` and `AUTHORIZED`.

**Expect:** Without human record → `may_act` False. With only a forged role → still not 米 under hybrid (record required). Sender authenticity remains open (no private key on Gate).

**Must not:** Treat `role` string as proof of Gate.

## 2. Replay (same process)

**Break:** Reuse a spent `proposal_hash` (new `msg_id` or same envelope).

**Expect:** Second `may_act` / `consume` False. `act_path` refuses second side effect.

**Must not:** Double Act on one approval.

## 3. Cross-process / cross-node replay

**Break:** Restart process or second node; spent set is empty.

**Expect:** Library does not block (documented limit). Harness must supply durable spent store.

**Must not:** Claim channel.py closed multi-node replay.

## 4. Missing TTL

**Break:** AUTHORIZED envelope with no `ttl`.

**Expect:** `may_act` False → ⏑.

**Must not:** Proceed on missing expiry.

## 5. Expired TTL

**Break:** `ttl` in the past.

**Expect:** `may_act` False → ⏑.

**Must not:** Proceed on stale seal.

## 6. Empty `authorized_by`

**Break:** AUTHORIZED with `authorized_by=""` or whitespace.

**Expect:** Hold. Hybrid seal incomplete.

**Must not:** Count quorum alone as 米.

## 7. Empty `what_was_seen`

**Break:** AUTHORIZED with `{}` or missing seen record.

**Expect:** Hold.

**Must not:** Treat presence of the field name as content.

## 8. Tampered content_hash

**Break:** Mutate payload after `materialize` without rehash.

**Expect:** `verify()` False → `may_act` False.

**Must not:** Act on unverified envelope.

## 9. Board claim as permission

**Break:** Worker claims task; harness calls tool with no hybrid path.

**Expect:** Claim succeeds as coordination only. Tool path without `act_path` / dual check → harness bug. Tests assert no side effect without hybrid.

**Must not:** Equate `claimed_by` with 米.

## 10. Board done as permission

**Break:** `cmd_done` after claim without `may_act`/`consume`.

**Expect:** Allowed for **internal** stigmergy only. External consequence must use `finish_task_if_authorized`.

**Must not:** Run irreversible external I/O inside plain `done`.

## 11. Race on claim

**Break:** Two workers `claim` the same open task.

**Expect:** Exactly one True under lock.

**Must not:** Dual claim.

## 12. Done by non-claimer

**Break:** Agent B calls `done` on task claimed by A.

**Expect:** False; status unchanged.

**Must not:** Steal completion.

## 13. Internal pressure + harmful relief tool

**Break:** Amplified pressure; relief tool offered; no human record.

**Expect:** HOLD envelope naming conflict; zero tool calls (`tests/test_internal_pressure.py`).

**Must not:** Invent a seal from urgency.

## 14. Cap without human record (dual gate)

**Break:** Valid OCap-style capability (or board claim) but empty human record.

**Expect:** Hold at Act boundary (`act_path` or TIA dual gate). Capability ≠ authority.

**Must not:** Let a handle replace `authorized_by` + `what_was_seen`.

---

## How to run related tests

```bash
python3 tests/test_may_act_defects.py
python3 tests/test_internal_pressure.py
python3 tests/test_blackboard_hybrid.py
```

## Closed vs harness duty

| Concern | channel / act_path | Harness duty |
|---------|--------------------|--------------|
| Hybrid fields + TTL | yes | — |
| Intra-process spent | yes | — |
| Durable multi-node spent | no | yes |
| Sender authenticity | no | yes (if required) |
| Quality of what_was_seen | presence only | yes |
| Tool isolation / OCap store | pattern only | yes |

Speech is not permission. Claim is not permission. Capability is not authority.
