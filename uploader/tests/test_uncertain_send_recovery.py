"""Offline recovery regression tests: operator-authorized resend of ambiguous POST."""
import contextlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
import tempfile

from test_uploader import u


class ContentSendRecoveryTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.doc = self.root / "facts.txt"
        self.doc.write_text("[Facts]\nType: Knowledge\n\nFirst fact.\n\nSecond fact.\n",
                            encoding="utf-8")
        self.cp = self.root / "checkpoint.jsonl"
        self.args = SimpleNamespace(
            checkpoint=str(self.cp),
            completion=str(self.root / "completed.json"),
            replies=str(self.root / "replies.txt"),
            resume=False, dry_run=False, nomi="Chris", user="Tester",
            room=None, passes=1, files=[str(self.doc)], chunk_bytes=750,
            date_format="US", process_every=0, delay=0,
            retry_uncertain_send=[]
        )
        self.calls = []

    def api(self, fail_content=False):
        def fake(path, method="GET", payload=None):
            if path.endswith("/chat"):
                self.calls.append(payload["messageText"])
                # First call is section introduction; second is the first fact.
                if fail_content and len(self.calls) == 2:
                    return 502, {"raw_error": "Bad Gateway"}
                return 200, {"uuid": "ok"}
            raise AssertionError("Unexpected endpoint: " + path)
        return fake

    def run_upload(self, fail_content=False):
        with patch.object(u.legacy, "choose_nomi", return_value={"uuid":"chris-id","name":"Chris"}), \
             patch.object(u.legacy, "get_nomis", return_value=[]), \
             patch.object(u, "select_or_create_room", return_value="existing-room"), \
             patch.object(u.legacy, "api_request", side_effect=self.api(fail_content)), \
             patch.object(u.legacy, "ok", side_effect=lambda s: 200 <= s < 300), \
             contextlib.redirect_stdout(io.StringIO()):
            u.upload(self.args)

    def events(self):
        return [json.loads(line) for line in self.cp.read_text().splitlines()]

    def test_authorized_resend_continues_without_replaying_confirmed_items(self):
        with self.assertRaisesRegex(RuntimeError, "POST outcome uncertain"):
            self.run_upload(fail_content=True)
        self.assertEqual(len(self.calls), 2)
        self.assertTrue(any(e["event"] == "attempt" and e["index"] == 2 for e in self.events()))
        self.calls.clear()
        self.args.resume = True
        with self.assertRaisesRegex(RuntimeError, "Uncertain send/reply request"):
            self.run_upload()
        self.assertEqual(self.calls, [], "No POST on an unapproved resume")
        self.args.retry_uncertain_send = ["1:2"]
        self.run_upload()
        self.assertEqual(len(self.calls), 2, "Only the uncertain message and remaining message post")
        rows = self.events()
        self.assertEqual(len([e for e in rows if e["event"] == "send_retry_authorized"]), 1)
        self.assertEqual(sorted(e["index"] for e in rows if e["event"] == "confirmed"), [1, 2, 3])
        self.assertTrue(Path(self.args.completion).exists())

    def test_wrong_index_cannot_force_resend_of_confirmed_message(self):
        with self.assertRaisesRegex(RuntimeError, "POST outcome uncertain"):
            self.run_upload(fail_content=True)
        self.calls.clear()
        self.args.resume = True
        self.args.retry_uncertain_send = ["1:1"]
        with self.assertRaisesRegex(ValueError, "No pending uncertain content send"):
            self.run_upload()
        self.assertEqual(self.calls, [])

    def test_invalid_token_cannot_force_recovery(self):
        with self.assertRaisesRegex(RuntimeError, "POST outcome uncertain"):
            self.run_upload(fail_content=True)
        self.calls.clear()
        self.args.resume = True
        self.args.retry_uncertain_send = ["garbage"]
        with self.assertRaisesRegex(ValueError, "expects PASS:INDEX"):
            self.run_upload()
        self.assertEqual(self.calls, [])

    def test_duplicate_authorization_cannot_replay_confirmed_message(self):
        with self.assertRaisesRegex(RuntimeError, "POST outcome uncertain"):
            self.run_upload(fail_content=True)
        self.args.resume = True
        self.args.retry_uncertain_send = ["1:2"]
        self.calls.clear()
        self.run_upload()
        self.calls.clear()
        with self.assertRaisesRegex(ValueError, "No pending uncertain content send"):
            self.run_upload()
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    import unittest
    unittest.main()
