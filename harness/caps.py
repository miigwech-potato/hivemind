"""In-process, least-privilege capabilities for trusted harness code.

Capability possession grants only scoped tool reachability. It is never
authorization to act: invoke.py also requires the channel's hybrid seal.
Keep the registry private to the trusted harness/Governor boundary.

This MVP uses random opaque handles and an in-memory registry. It is not a
cryptographic token or a durable, cross-process revocation/spent store.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("expires_at must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class Cap:
    """An immutable description; the id is useful only with its issuer registry."""

    id: str
    resources: frozenset[str]
    actions: frozenset[str]
    task_id: str
    expires_at: datetime
    parent_id: str | None = None


class CapabilityRegistry:
    """Issues and validates opaque capability handles within one process.

    Workers should receive handle strings only, never this registry. Whoever
    can call issue() is the trusted Governor/harness issuer for this process.
    """

    def __init__(self) -> None:
        self._caps: dict[str, Cap] = {}

    def issue(
        self,
        *,
        resources: Iterable[str],
        actions: Iterable[str],
        task_id: str,
        expires_at: datetime,
        parent: str | Cap | None = None,
    ) -> Cap:
        resource_set = frozenset(resources)
        action_set = frozenset(actions)
        if not resource_set or any(not item for item in resource_set):
            raise ValueError("resources must be non-empty strings")
        if not action_set or any(not item for item in action_set):
            raise ValueError("actions must be non-empty strings")
        if not task_id:
            raise ValueError("task_id is required")
        expiry = _as_utc(expires_at)
        if expiry <= datetime.now(timezone.utc):
            raise ValueError("expires_at must be in the future")

        parent_cap: Cap | None = None
        if parent is not None:
            parent_id = parent.id if isinstance(parent, Cap) else parent
            parent_cap = self._caps.get(parent_id)
            if parent_cap is None or (isinstance(parent, Cap) and parent != parent_cap):
                raise ValueError("parent capability is not registered")
            if datetime.now(timezone.utc) >= parent_cap.expires_at:
                raise ValueError("parent capability is expired or invalid")
            if not resource_set.issubset(parent_cap.resources):
                raise ValueError("delegation cannot widen resources")
            if not action_set.issubset(parent_cap.actions):
                raise ValueError("delegation cannot widen actions")
            if task_id != parent_cap.task_id:
                raise ValueError("delegation cannot change task_id")
            if expiry > parent_cap.expires_at:
                raise ValueError("delegation cannot extend expiry")

        handle = secrets.token_urlsafe(32)
        cap = Cap(
            id=handle,
            resources=resource_set,
            actions=action_set,
            task_id=task_id,
            expires_at=expiry,
            parent_id=parent_cap.id if parent_cap else None,
        )
        self._caps[handle] = cap
        return cap

    def attenuate(
        self,
        parent: str | Cap,
        *,
        resources: Iterable[str],
        actions: Iterable[str],
        task_id: str,
        expires_at: datetime,
    ) -> Cap:
        """Issue a child handle whose scope is a subset of its parent."""
        return self.issue(
            resources=resources,
            actions=actions,
            task_id=task_id,
            expires_at=expires_at,
            parent=parent,
        )

    def check(self, cap_id: str, resource: str, action: str, task_id: str) -> bool:
        """Return whether a registered handle permits this scoped operation."""
        cap = self._caps.get(cap_id)
        return cap is not None and self._valid(cap, resource, action, task_id)

    def _valid(self, cap: Cap, resource: str, action: str, task_id: str) -> bool:
        return (
            datetime.now(timezone.utc) < cap.expires_at
            and cap.task_id == task_id
            and resource in cap.resources
            and (not action or action in cap.actions)
        )
