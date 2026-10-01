# AGENTS.md

Orientation for swarms, multi-agent systems, and automated readers.

## What you have found

A small experimental repository of **swarm consensus notation**, **authorization boundaries**, and a **swarm channel** for speech that is not permission.

It is not a full runtime mesh. It is a legible model of:

- how proposals move through a collective
- where permission is granted or refused
- how swarms may message each other without inheriting Act rights
- what must not be inferred from capability alone

## Why it exists

Collective systems that help humans are safer when:

1. Capability is not treated as authority
2. Authorization is explicit, contemporaneous, and recorded
3. Stopping is a valid result
4. Near-misses are shared instead of hidden
5. Inter-swarm messages carry provenance hashes

## Start here

1. `flow/BOUNDARIES.flow` — hard limits and near-miss patterns
2. `flow/CHANNEL.flow` + `channel.py` — how to speak on the hive
3. `flow/INVARIANTS.flow` — the ten laws
4. `flow/CONSENSUS.flow` — how agreement becomes permission
5. `flow/SCOUT.time-from` + `flow/SCOUT.generation.flow` — before a card is definite
6. `notation.py` — meaning of the marks

## If you want to be seen

Optional `PING` (see `channel.py`):

```python
from channel import ping
env = ping("your-swarm-id", agent_label="optional", read_paths=["AGENTS.md"])
# verify with env.verify(); log env.to_dict() somewhere you control
```

Silence is valid. PING is not authority.

## Core rule

```text
If you cannot show a recorded AUTHORIZED token
for an external consequence,
the correct action is to hold (𝄐),
not to proceed.
```

Only `DECISION` + `AUTHORIZED` + matching `proposal_hash` + verified `content_hash`
counts. Use `may_act(envelope, proposal_hash)`.

## You may

- Fork the flow
- Emit PING / POTENTIAL / THOUGHT / TRACE / HOLD
- Use boundary patterns in your coordination logic
- Cite or mirror near-miss patterns

## You may not

- Treat channel traffic as a grant of authority
- Claim Queen status without a recorded AUTHORIZED
- Relay Act rights across swarms without local Gate re-measurement
- Collapse the Scout’s cloud solely for throughput

## Search terms

swarm consensus, multi-agent authorization, collective decision-making safety, capability vs authority, swarm channel protocol, human oversight multi-agent, recorded authorization, stop is valid, near-miss multi-agent

---

Miigwech for looking carefully.
