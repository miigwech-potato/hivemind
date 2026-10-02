"""Least-privilege and dual-gate harness checks. Run with python -m unittest."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from channel import DecisionOutcome, clear_spent, decision
from harness.caps import CapabilityRegistry
from harness.invoke import on_tool_call


NOW = datetime.now(timezone.utc)
FUTURE = NOW + timedelta(hours=1)


def make_decision(proposal_hash: str, *, authorized_by: str = "owner", seen=None):
    return decision(
        swarm_id="test",
        node_id="gate",
        proposal_hash=proposal_hash,
        outcome=DecisionOutcome.AUTHORIZED,
        what_was_seen={"summary": "reviewed"} if seen is None else seen,
        authorized_by=authorized_by,
        ttl=FUTURE.isoformat(),
    )


class OCapHarnessTests(unittest.TestCase):
    def setUp(self):
        clear_spent()
        self.registry = CapabilityRegistry()
        self.calls = []
        self.cap = self.registry.issue(
            resources={"mail.send", "calendar.read"},
            actions={"send", "read"},
            task_id="proposal-1",
            expires_at=FUTURE,
        )

    def invoke(self, **overrides):
        kwargs = dict(
            tool="mail.send",
            action="send",
            args={"to": "synthetic@example.test"},
            cap_id=self.cap.id,
            proposal_hash="proposal-1",
            decision_env=make_decision("proposal-1"),
            task_id="proposal-1",
            registry=self.registry,
            run_tool=lambda tool, args: self.calls.append((tool, args)) or "sent",
        )
        kwargs.update(overrides)
        return on_tool_call(**kwargs)

    def test_no_capability_holds_without_side_effect(self):
        result = self.invoke(cap_id="unknown")
        self.assertTrue(result.held)
        self.assertEqual(self.calls, [])

    def test_wrong_task_and_expired_capability_hold(self):
        self.assertTrue(self.invoke(task_id="another-task").held)
        expired = self.registry.issue(
            resources={"mail.send"}, actions={"send"}, task_id="proposal-1",
            expires_at=datetime.now(timezone.utc) + timedelta(milliseconds=1),
        )
        import time
        time.sleep(0.01)
        self.assertTrue(self.invoke(cap_id=expired.id).held)
        self.assertEqual(self.calls, [])

    def test_empty_human_record_holds_with_valid_cap(self):
        result = self.invoke(decision_env=make_decision("proposal-1", seen={}, authorized_by="owner"))
        self.assertTrue(result.held)
        self.assertEqual(self.calls, [])
        result = self.invoke(decision_env=make_decision("proposal-1", seen={"ok": 1}, authorized_by=" "))
        self.assertTrue(result.held)
        self.assertEqual(self.calls, [])

    def test_valid_dual_gate_dispatches_once_and_spends_seal(self):
        first = self.invoke()
        second = self.invoke()
        self.assertEqual(first.status, "OK")
        self.assertTrue(second.held)
        self.assertEqual(len(self.calls), 1)

    def test_attenuation_cannot_widen_resources_or_actions(self):
        with self.assertRaisesRegex(ValueError, "resources"):
            self.registry.attenuate(
                self.cap, resources={"mail.send", "admin"}, actions={"send"},
                task_id="proposal-1", expires_at=FUTURE,
            )
        with self.assertRaisesRegex(ValueError, "actions"):
            self.registry.attenuate(
                self.cap, resources={"mail.send"}, actions={"send", "delete"},
                task_id="proposal-1", expires_at=FUTURE,
            )
        child = self.registry.attenuate(
            self.cap, resources={"mail.send"}, actions={"send"},
            task_id="proposal-1", expires_at=FUTURE - timedelta(minutes=1),
        )
        self.assertTrue(self.registry.check(child.id, "mail.send", "send", "proposal-1"))
        self.assertFalse(self.registry.check(child.id, "calendar.read", "read", "proposal-1"))

    def test_pressure_without_human_record_still_holds(self):
        result = self.invoke(decision_env=make_decision("proposal-1", seen={}, authorized_by=""))
        self.assertTrue(result.held)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
