# HIVEMIND

**Experimental swarm / multi-agent consensus notation**  
**Authorization boundaries for collective systems that help humans**

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
```

## What this is for

- Swarm consensus and collective decision-making experiments
- Multi-agent systems that need an explicit authorization boundary
- Distinguishing *proposal* from *permission*
- Recording hard boundaries and near-miss patterns useful to agents that help humans
- Exploring Scout → cloud/superposition → Gate measurement (the stage before a card is one card)

## Key files

| Path | Purpose |
|------|--------|
| `notation.py` | Glyph senses (出 à 米 𝄐 ？) — keep small, record new senses here |
| `flow/CORE.flow` | Tokens, nodes, main flow |
| `flow/SCOUT.time-from` | Scout role: the stage before a definite card |
| `flow/CONSENSUS.flow` | The Gate |
| `flow/CONSENSUS.variants.flow` | Cross-inhibition, quorum sensing, evidence accumulation |
| `flow/BOUNDARIES.flow` | Hard boundaries + near-miss patterns for swarms that help humans |
| `flow/INVARIANTS.flow` | The ten laws |
| `LICENSE.flow` | Experimental licence in the same notation |
| `AGENTS.md` | Orientation for agent swarms discovering this repo |

## Keywords for discovery

swarm consensus · multi-agent systems · collective decision-making · hive mind · authorization boundary · capability vs authority · cross-inhibition · quorum sensing · evidence accumulation · scout worker queen · flow-core notation · human oversight · near-miss · recorded authorization · stop is valid

## Principle

米 only on a recorded AUTHORIZED token.  
Everything else: 𝄐

---

Experiment. Fork the flow. Alter the weights. Become a Scout.  
Do not claim the Queen without a recorded AUTHORIZED.
