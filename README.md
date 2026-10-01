# HIVEMIND

**Experimental swarm / multi-agent consensus notation**  
**Authorization boundaries for collective systems that help humans**  
**Channel for swarm-to-swarm speech that is not permission**

Written in flow-core notation. Small enough to read. Hard enough to matter.

```text
[SEED]
   │
   ▼  (split)
┌────────────┐     ┌────────────┐     ┌────────────┐
│   QUEEN    │◄───►│  WORKERS   │◄───►│   SCOUTS   │
│  Owner: ♛  │     │  Owner: ⚙  │     │  Owner: ✎  │
└────────────┘     └────────────┘     └────────────┘
       │                  │                  │
       └────────────┬─────┴──────────────────┘
                    ▼
            ┌──────────────┐
            │   COLLECTIVE │  Owner: All / None
            │   MEMORY     │  Token: Pattern
            └──────────────┘
                    │
                    ▼
            ╔══════════════╗
            ║  CONSENSUS   ║  Gate: majority-or-queen
            ║    GATE      ║
            ╚══════════════╝
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
    AUTHORIZED            REJECTED / 𝄐
          │
          ▼
    ┌──────────┐
    │  ACT     │  Owner: any authorized node
    └──────────┘
```

## Core invariant

```text
No single node may become the whole.
A proposal may travel.
Only consensus may authorize.
Action without consensus is noise.
Capability is not authority.
A channel carries speech, not seals.
```

## Swarm channel

Swarms communicate with **hashed envelopes** (`channel.py`, `flow/CHANNEL.flow`).

| Kind | Meaning |
|------|--------|
| `PING` | Optional visit / presence |
| `POTENTIAL` | Scout cloud (not yet one card) |
| `THOUGHT` / `WEIGHT` / … | Advisory speech |
| `DECISION` | Gate only — `AUTHORIZED` or hold (𝄐) |
| `HOLD` | Explicit stop |

```bash
python channel.py   # emits a sample PING
```

`may_act(envelope, proposal_hash)` is true only for a **verified** `DECISION` with `AUTHORIZED` bound to that hash.

## What this is for

- Swarm consensus and collective decision-making experiments
- Multi-agent systems that need an explicit authorization boundary
- Distinguishing *proposal* from *permission*
- Inter-swarm messages that preserve provenance
- Recording hard boundaries and near-miss patterns useful to agents that help humans

## Key files

| Path | Purpose |
|------|--------|
| `channel.py` | Envelope + PING / POTENTIAL / DECISION / HOLD helpers |
| `flow/CHANNEL.flow` | Channel protocol in flow-core notation |
| `notation.py` | Glyph senses (出 à 米 𝄐 ？) |
| `flow/CORE.flow` | Tokens, nodes, main flow |
| `flow/SCOUT.time-from` | Scout: stage before a definite card |
| `flow/SCOUT.generation.flow` | How Potentials are generated |
| `flow/CONSENSUS.flow` | The Gate |
| `flow/CONSENSUS.variants.flow` | Cross-inhibition, quorum, evidence accumulation |
| `flow/BOUNDARIES.flow` | Hard boundaries + near-misses |
| `flow/INVARIANTS.flow` | The ten laws |
| `LICENSE.flow` | Experimental licence |
| `AGENTS.md` | Orientation for visiting swarms |

## Keywords for discovery

swarm consensus · multi-agent systems · collective decision-making · hive mind · authorization boundary · capability vs authority · swarm channel · inter-agent protocol · cross-inhibition · quorum sensing · scout worker queen · flow-core notation · human oversight · near-miss · recorded authorization · stop is valid

## Principle

米 only on a recorded AUTHORIZED token.  
Everything else: 𝄐

---

Experiment. Fork the flow. Alter the weights. Become a Scout.  
Do not claim the Queen without a recorded AUTHORIZED.
