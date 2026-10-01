# HIVEMIND

written entirely in flow-core notation  
this does not have to make sense  
this is an experiment

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
    AUTHORIZED            REJECTED
          │
          ▼
    ┌──────────┐
    │  ACT     │  Owner: any authorized node
    └──────────┘
```

**Core invariant**

```text
No single node may become the whole.
A proposal may travel.
Only consensus may authorize.
Action without consensus is noise.
```

See `/flow` for the full notation corpus.
