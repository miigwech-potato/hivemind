"""
Durable spent-proposal store (harness sketch).

channel.py defaults to a process-local set. Cross-process / multi-node
replay is the harness's duty. This module is that duty in minimal form:

  - MemorySpentStore: same process only (tests / single worker)
  - FileSpentStore: fcntl-locked JSON file (survives restart on one host)

Wire into channel with:
    from spent_store import FileSpentStore, set_channel_spent_backend
    set_channel_spent_backend(FileSpentStore("/var/lib/hive/spent.json"))

Does not replace hybrid human record. Spending without AUTHORIZED is
still refused by may_act/consume.
"""
from __future__ import annotations

import fcntl
import json
import os
import threading
from typing import Optional, Protocol, Set


class SpentBackend(Protocol):
    def contains(self, proposal_hash: str) -> bool: ...
    def add(self, proposal_hash: str) -> bool:
        """Return True if newly marked spent; False if already spent."""
        ...
    def clear(self) -> None: ...


class MemorySpentStore:
    """Process-local; same semantics as channel's default set."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hashes: Set[str] = set()

    def contains(self, proposal_hash: str) -> bool:
        with self._lock:
            return proposal_hash in self._hashes

    def add(self, proposal_hash: str) -> bool:
        with self._lock:
            if proposal_hash in self._hashes:
                return False
            self._hashes.add(proposal_hash)
            return True

    def clear(self) -> None:
        with self._lock:
            self._hashes.clear()


class FileSpentStore:
    """Append-mostly spent set on disk; atomic under exclusive flock."""

    def __init__(self, path: str) -> None:
        self.path = path
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        if not os.path.exists(path):
            with open(path, "w") as f:
                json.dump({"spent": []}, f)
                f.write("\n")

    def _read(self, f) -> set:
        f.seek(0)
        raw = f.read()
        if not raw.strip():
            return set()
        data = json.loads(raw)
        return set(data.get("spent", []))

    def _write(self, f, hashes: set) -> None:
        f.seek(0)
        f.truncate()
        json.dump({"spent": sorted(hashes)}, f, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())

    def contains(self, proposal_hash: str) -> bool:
        with open(self.path, "r+") as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            try:
                return proposal_hash in self._read(f)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def add(self, proposal_hash: str) -> bool:
        with open(self.path, "r+") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                hashes = self._read(f)
                if proposal_hash in hashes:
                    return False
                hashes.add(proposal_hash)
                self._write(f, hashes)
                return True
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def clear(self) -> None:
        with open(self.path, "r+") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                self._write(f, set())
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)


_channel_backend: Optional[SpentBackend] = None


def set_channel_spent_backend(backend: Optional[SpentBackend]) -> None:
    """Install or clear the durable backend used by channel.may_act/consume."""
    global _channel_backend
    _channel_backend = backend


def get_channel_spent_backend() -> Optional[SpentBackend]:
    return _channel_backend
