# Harness builder note: capabilities under the hybrid seal

This package is for harness builders. It gives workers no ambient tool rights:
they receive opaque capability handles scoped to resources, actions, task ids,
and expiry. Delegation can only narrow those scopes. Keep the registry and its
issuer private to trusted harness/Governor code.

Every external call passes two independent gates in `on_tool_call`:

1. The registered capability must cover the requested tool, action, task, and
   current time.
2. `channel.may_act` must accept the proposal-bound DECISION, then
   `channel.consume` must spend it at the point of action. The existing hybrid
   human record (`authorized_by` plus non-empty `what_was_seen`) remains
   required by the channel library.

Either failure returns HOLD without calling the tool. A capability never
substitutes for the human record or routes around `may_act` / `consume`.

The registry and replay store in this MVP are in-memory and process-local.
Production harnesses must provide durable, shared spent-state where needed and
must reconcile uncertain tool outcomes before retrying.
