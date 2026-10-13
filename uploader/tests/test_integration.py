"""Offline integration tests for the uploader state machine. No Nomi credentials required."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_uploader import u


class FakeNomi:
    def __init__(self, fail_at=None, malformed_reply=False, fail_reply=False):
        self.calls = []
        self.fail_at = fail_at
        self.malformed_reply = malformed_reply
        self.fail_reply = fail_reply
        self.counter = 0

    def api(self, path, method="GET", payload=None):
        self.counter += 1
        self.calls.append((path, method, payload))
        if self.fail_at == self.counter:
            return 503, {"error": "synthetic transport failure"}
        if path == "/rooms":
            return 200, {"uuid": "room-001"}
        if path.endswith("/chat/request"):
            if self.fail_reply:
                return 503, {"error": "synthetic reply transport failure"}
            if self.malformed_reply:
                return 200, {"unexpected": True}
            return 200, {"replyMessage": {"messageText": "Recollection %d" % self.counter,
                                           "uuid": "reply-%d" % self.counter}}
        if path.endswith("/chat"):
            return 200, {"uuid": "sent-%d" % self.counter}
        raise AssertionError("Unexpected endpoint: " + path)

    def calls_to(self, suffix):
        return [c for c in self.calls if c[0].endswith(suffix)]


class StateMachineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.diary = self.root / "diary.txt"
        self.diary.write_text(
            "[Diary]\nType: Journal\nSource: Beth\nProcess Every: 2\n\n"
            "ENTRY 001 - 10/11/1998\nI remember the birthday.\n"
            "ENTRY 002 - 10/12/1998\nI remember the park.\n"
            "ENTRY 003 - 10/13/1998\nI remember the rain.\n",
            encoding="utf-8")
        self.checkpoint = self.root / "checkpoint.jsonl"
        self.completion = self.root / "completed.json"
        self.replies = self.root / "replies.txt"

    def args(self, resume=False, passes=1):
        return SimpleNamespace(
            checkpoint=str(self.checkpoint), completion=str(self.completion),
            replies=str(self.replies), resume=resume, dry_run=False,
            nomi="Beth", user="Tester", room=None, passes=passes,
            files=[str(self.diary)], chunk_bytes=750, date_format="US",
            process_every=0, delay=0)

    def run_upload(self, fake, args):
        with patch.object(u.legacy, "get_nomis", return_value=[{"uuid":"beth-id","name":"Beth"}]), \
             patch.object(u.legacy, "choose_nomi", return_value={"uuid":"beth-id","name":"Beth"}), \
             patch.object(u.legacy, "api_request", side_effect=fake.api), \
             patch.object(u.legacy, "wait_for_room", return_value={"uuid":"room-001"}), \
             patch.object(u.legacy, "ok", side_effect=lambda status: 200 <= status < 300), \
             contextlib.redirect_stdout(io.StringIO()):
            u.upload(args)

    def test_noreply_retries_with_visible_backoff(self):
        calls=[]
        responses=iter([
            (500, {"type":"NoReply"}),
            (500, {"type":"NoReply"}),
            (200, {"replyMessage":{"messageText":"I remember."}})
        ])
        def api(*args):
            calls.append(args)
            return next(responses)
        output=io.StringIO()
        with patch.object(u.legacy,"api_request",side_effect=api), \
             patch.object(u.time,"sleep") as sleeping, \
             contextlib.redirect_stderr(output):
            status,payload=u.request_reply_with_backoff("room-001","beth-id",attempts=8)
        self.assertEqual(status,200)
        self.assertEqual(len(calls),3)
        self.assertEqual([x.args[0] for x in sleeping.call_args_list],[1.0,2.0])
        self.assertIn("HTTP 500",output.getvalue())
        self.assertIn("NoReply",output.getvalue())
        self.assertIn("NoReply attempt 1; retry in 1.0s",output.getvalue())

    def test_ambiguous_reply_failure_is_not_retried(self):
        with patch.object(u.legacy,"api_request",
                          return_value=(None,{"error":{"type":"TimeoutError"}})) as api, \
             patch.object(u.time,"sleep") as sleeping, \
             contextlib.redirect_stderr(io.StringIO()):
            status,_=u.request_reply_with_backoff("room-001","beth-id")
        self.assertIsNone(status)
        api.assert_called_once()
        sleeping.assert_not_called()

    def test_noreply_exhaustion_reports_error(self):
        output=io.StringIO()
        with patch.object(u.legacy,"api_request",
                          return_value=(500,{"type":"NoReply"})) as api, \
             patch.object(u.time,"sleep") as sleeping, \
             contextlib.redirect_stderr(output):
            status,_=u.request_reply_with_backoff("room-001","beth-id",attempts=3)
        self.assertEqual(status,500)
        self.assertEqual(api.call_count,3)
        self.assertEqual(sleeping.call_count,2)
        self.assertIn("test retry limit reached",output.getvalue())

    def test_noreply_waits_until_reply(self):
        calls=[]
        responses=iter([(500,{"type":"NoReply"}),(500,{"type":"NoReply"}),
                        (200,{"replyMessage":{"messageText":"Beth remembered"}})])
        def api(*args):
            calls.append(args)
            return next(responses)
        with patch.object(u.legacy,"api_request",side_effect=api), \
             patch.object(u.time,"sleep") as sleeping, \
             contextlib.redirect_stderr(io.StringIO()):
            status,response=u.request_reply_with_backoff("room-001","beth-id")
        self.assertEqual(status,200)
        self.assertEqual(len(calls),3)
        self.assertEqual(sleeping.call_count,2)

    def test_complete_upload_captures_all_replies(self):
        fake = FakeNomi()
        self.run_upload(fake, self.args())
        plan = u.plan_text([str(self.diary)], "Beth", "Tester", "US", 2026, 750)
        self.assertEqual(len(fake.calls_to("/chat")), len(plan))
        self.assertEqual(len(fake.calls_to("/chat/request")), 2)
        events = u.records(self.checkpoint)
        self.assertEqual(sum(e["event"]=="confirmed" for e in events), len(plan))
        self.assertEqual(sum(e["event"]=="reply_committed" for e in events), 2)
        transcript = self.replies.read_text(encoding="utf-8")
        self.assertIn("Recollection", transcript)
        self.assertIn("PROMPT:", transcript)
        self.assertEqual(json.loads(self.completion.read_text())["room_uuid"],"room-001")

    def test_completed_resume_is_idempotent(self):
        self.run_upload(FakeNomi(), self.args())
        fake = FakeNomi()
        self.run_upload(fake, self.args(resume=True))
        self.assertEqual(fake.calls, [])

    def test_failed_message_send_is_not_retried(self):
        fake = FakeNomi(fail_at=3)
        with self.assertRaises(RuntimeError):
            self.run_upload(fake, self.args())
        events = u.records(self.checkpoint)
        self.assertTrue(any(e["event"]=="attempt" for e in events))
        second = FakeNomi()
        with self.assertRaisesRegex(RuntimeError,"Uncertain"):
            self.run_upload(second, self.args(resume=True))
        self.assertEqual(second.calls, [])
        self.assertFalse(self.completion.exists())

    def test_failed_reply_is_not_retried(self):
        # Fail the reply endpoint itself, regardless of preceding API calls.
        fake = FakeNomi(fail_reply=True)
        with self.assertRaises(RuntimeError):
            self.run_upload(fake, self.args())
        events = u.records(self.checkpoint)
        self.assertTrue(any(e["event"]=="reply_attempt" for e in events))
        second = FakeNomi()
        with self.assertRaisesRegex(RuntimeError,"Uncertain"):
            self.run_upload(second, self.args(resume=True))
        self.assertEqual(second.calls, [])

    def test_malformed_reply_is_preserved_as_uncertain(self):
        fake = FakeNomi(malformed_reply=True)
        with self.assertRaisesRegex(RuntimeError,"no replyMessage"):
            self.run_upload(fake, self.args())
        self.assertFalse(self.completion.exists())
        with self.assertRaisesRegex(RuntimeError,"Uncertain"):
            self.run_upload(FakeNomi(), self.args(resume=True))

    def test_resume_after_confirmed_message_without_reply(self):
        # Simulate an interruption after prompt send was confirmed but before
        # the reply request was issued. Only the missing reply may be requested.
        plan = u.plan_text([str(self.diary)],"Beth","Tester","US",2026,750)
        first_prompt = next(i for i,m in enumerate(plan,1) if m["kind"]=="prompt")
        self.run_upload(FakeNomi(), self.args())
        original = u.records(self.checkpoint)
        events = [e for e in original
                  if not (e.get("pass")==1 and e.get("index")>=first_prompt
                          and e["event"] in ("reply_attempt","reply_committed"))
                  and not (e.get("pass")==1 and e.get("index")>first_prompt)]
        self.checkpoint.write_text("".join(json.dumps(e)+"\n" for e in events),encoding="utf-8")
        self.completion.unlink()
        fake = FakeNomi()
        self.run_upload(fake,self.args(resume=True))
        self.assertEqual(len(fake.calls_to("/chat/request")),2)
        self.assertEqual(len(fake.calls_to("/chat")),len(plan)-first_prompt)
        self.assertEqual(sum(e["event"]=="reply_committed" for e in u.records(self.checkpoint)),2)

    def test_modified_input_refuses_resume(self):
        fake = FakeNomi(fail_at=3)
        with self.assertRaises(RuntimeError):
            self.run_upload(fake,self.args())
        self.diary.write_text(self.diary.read_text()+"Changed.",encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"Manifest changed"):
            self.run_upload(FakeNomi(),self.args(resume=True))

    def test_multiple_passes_and_new_run_archiving(self):
        self.run_upload(FakeNomi(),self.args(passes=2))
        events = u.records(self.checkpoint)
        self.assertEqual(sum(e["event"]=="reply_committed" for e in events),4)
        self.run_upload(FakeNomi(),self.args())
        self.assertTrue(list(self.root.glob("checkpoint.jsonl.*.archive")))
        self.assertTrue(list(self.root.glob("replies.txt.*.archive")))
        self.assertEqual(sum(e["event"]=="reply_committed" for e in u.records(self.checkpoint)),2)

    def test_dry_run_makes_no_network_calls_or_files(self):
        args=self.args()
        args.dry_run=True
        with patch.object(u.legacy,"api_request",side_effect=AssertionError("network")), \
             contextlib.redirect_stdout(io.StringIO()):
            u.upload(args)
        self.assertFalse(self.checkpoint.exists())
        self.assertFalse(self.completion.exists())

    def test_checkpoint_record_roundtrip_unicode(self):
        u.record(self.checkpoint,{"event":"note","text":"Café — 東京"})
        self.assertEqual(u.records(self.checkpoint)[0]["text"],"Café — 東京")


if __name__ == "__main__":
    unittest.main()
