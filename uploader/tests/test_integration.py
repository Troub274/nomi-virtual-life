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
    def private_api(self, fake, error=None):
        def api(path, method="GET", payload=None):
            if path == "/nomis/beth-id/chat":
                fake.calls.append((path, method, payload))
                return ((503, {"error": {"type": error}}) if error else
                        (200, {"sentMessage": {"text": payload["messageText"]},
                               "replyMessage": {"text": "Private reflection"}}))
            return fake.api(path, method, payload)
        return api

    def test_private_replies_keep_uploads_in_room_and_persist_destination(self):
        fake = FakeNomi()
        delegate = FakeNomi()
        args = self.args()
        args.reply_destination = "private"
        with patch.object(fake, "api", side_effect=self.private_api(delegate)):
            self.run_upload(fake, args)
        calls = delegate.calls
        prompts = [r for r in u.records(self.checkpoint) if r.get("event") == "reply_committed"]
        private_calls = [c for c in calls if c[0] == "/nomis/beth-id/chat"]
        self.assertEqual(len(private_calls), len(prompts))
        self.assertGreater(len(private_calls), 0)
        self.assertEqual([c[2]["messageText"] for c in private_calls], [r["prompt"] for r in prompts])
        self.assertFalse(any(c[0].endswith("/chat/request") for c in calls))
        self.assertTrue(any(c[0] == "/rooms/room-001/chat" for c in calls))
        self.assertEqual(u.records(self.checkpoint)[0]["reply_destination"], "private")
        self.assertEqual(u.checkpoint_summary(self.checkpoint)["reply_destination"], "private")
        self.assertEqual(json.loads(self.completion.read_text())["reply_destination"], "private")
        self.assertIn("Private reflection", self.replies.read_text())
        resumed = FakeNomi()
        self.run_upload(resumed, self.args(resume=True))
        self.assertEqual(resumed.calls, [])
        changed = self.args(resume=True)
        changed.reply_destination = "room"
        with self.assertRaisesRegex(ValueError, "cannot override checkpoint"):
            self.run_upload(resumed, changed)
        restarted, delegate = FakeNomi(), FakeNomi()
        restart = self.args(resume=True)
        restart.manual_restart = "1:1"
        with patch.object(restarted, "api", side_effect=self.private_api(delegate)):
            self.run_upload(restarted, restart)
        self.assertEqual(u.active_records(self.checkpoint)[0]["reply_destination"], "private")
        self.assertTrue(any(c[0] == "/nomis/beth-id/chat" for c in delegate.calls))
        self.assertFalse(any(c[0].endswith("/chat/request") for c in delegate.calls))

    def test_private_no_reply_requires_explicit_recovery_without_resending_content(self):
        args = self.args()
        args.reply_destination = "private"
        failing = FakeNomi()
        delegate = FakeNomi()
        with patch.object(failing, "api", side_effect=self.private_api(delegate, "NoReply")):
            with self.assertRaisesRegex(RuntimeError, "outcome uncertain"):
                self.run_upload(failing, args)
        self.assertEqual(sum(c[0] == "/nomis/beth-id/chat" for c in delegate.calls), 1)
        info = u.checkpoint_summary(self.checkpoint)
        self.assertEqual(info["state"], "AMBIGUOUS_REPLY")
        token = "%d:%d" % tuple(info["ambiguous_replies"][0])
        retry = self.args(resume=True)
        retry.recover_noreply = [token]
        with self.assertRaisesRegex(ValueError, "Private NoReply"):
            self.run_upload(FakeNomi(), retry)
        with self.assertRaisesRegex(RuntimeError, "Uncertain"):
            self.run_upload(FakeNomi(), self.args(resume=True))
        retry = self.args(resume=True)
        retry.recover_uncertain_reply = [token]
        resumed, delegate = FakeNomi(), FakeNomi()
        with patch.object(resumed, "api", side_effect=self.private_api(delegate)):
            self.run_upload(resumed, retry)
        history = u.records(self.checkpoint)
        first_prompt = next(r for r in history if r.get("event") == "reply_committed")["prompt"]
        self.assertEqual(delegate.calls[0], ("/nomis/beth-id/chat", "POST", {"messageText": first_prompt}))
        self.assertFalse(any(c[0].endswith("/chat/request") for c in delegate.calls))

    def test_private_readiness_retries_only_the_private_prompt(self):
        responses = [(409, {"error": {"type": "NomiStillResponding"}}),
                     (200, {"replyMessage": {"text": "Ready"}})]
        with patch.object(u.legacy, "api_request", side_effect=responses) as api, \
             patch.object(u.time, "sleep"):
            status, _ = u.request_reply_with_backoff("room", "nomi", destination="private", prompt="Reflect")
        self.assertEqual(status, 200)
        self.assertEqual(api.call_count, 2)
        for call in api.call_args_list:
            self.assertEqual(call.args, ("/nomis/nomi/chat", "POST", {"messageText": "Reflect"}))

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

    def test_chunk_range_is_inclusive_and_saved_for_resume(self):
        args = self.args()
        args.start_chunk = 2
        args.end_chunk = 3
        full_plan = u.plan_text(args.files, "Beth", args.user, "US", 2026, 750)
        fake = FakeNomi()
        self.run_upload(fake, args)
        sent = [call[2]["messageText"] for call in fake.calls_to("/chat")]
        self.assertEqual(sent, [message["text"] for message in full_plan[1:3]])
        history = u.records(self.checkpoint)
        self.assertEqual(history[0]["start_chunk"], 2)
        self.assertEqual(history[0]["end_chunk"], 3)
        self.assertEqual(history[0]["messages_per_pass"], 2)
        resumed = FakeNomi()
        self.run_upload(resumed, self.args(resume=True))
        self.assertEqual(resumed.calls_to("/chat"), [])

    def test_chunk_range_rejects_invalid_bounds_before_sending(self):
        for first, last in ((0, 2), (3, 2), (1, 999)):
            with self.subTest(first=first, last=last):
                args = self.args()
                args.start_chunk = first
                args.end_chunk = last
                fake = FakeNomi()
                with self.assertRaisesRegex(ValueError, "Chunk range"):
                    self.run_upload(fake, args)
                self.assertFalse(self.checkpoint.exists())
                self.assertEqual(fake.calls, [])

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
        self.assertEqual([x.args[0] for x in sleeping.call_args_list],[2.0,2.5])
        self.assertIn("HTTP 500",output.getvalue())
        self.assertIn("NoReply",output.getvalue())
        self.assertIn("NoReply attempt 1; retry in 2.0s",output.getvalue())

    def test_reply_backoff_learns_slower_and_faster_replies(self):
        timing = u.ReplyRetryTiming()
        now = 0.0
        waits = []
        def sleep(seconds):
            nonlocal now
            waits.append(seconds)
            now += seconds

        not_ready = (500, {"type": "NoReply"})
        ready = (200, {"replyMessage": {"text": "Ready"}})
        with patch.object(u.time, "monotonic", side_effect=lambda: now), \
             patch.object(u.time, "sleep", side_effect=sleep), \
             patch.object(u.legacy, "api_request",
                          side_effect=[not_ready, not_ready, ready, ready,
                                       not_ready, not_ready, (502, {})]), \
             contextlib.redirect_stderr(io.StringIO()):
            u.request_reply_with_backoff("room", "nomi", timing=timing)
            self.assertEqual(timing.initial_delay, 4.5)
            u.request_reply_with_backoff("room", "nomi", timing=timing)
            self.assertEqual(timing.initial_delay, 2.25)
            status, _ = u.request_reply_with_backoff("room", "nomi", timing=timing)
        self.assertEqual(status, 502)
        self.assertEqual(waits, [2.0, 2.5, 2.25, 2.8125])
        self.assertEqual(timing.samples, 2)

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

    def test_not_ready_waits_until_reply(self):
        responses=iter([(500,{"type":"NoReply"}),
                        (400,{"type":"RoomNomiNotReadyForMessage"}),
                        (200,{"replyMessage":{"messageText":"Ready"}})])
        with patch.object(u.legacy,"api_request",side_effect=lambda *a: next(responses)) as api, \
             patch.object(u.time,"sleep") as sleeping, \
             contextlib.redirect_stderr(io.StringIO()) as output:
            status,_=u.request_reply_with_backoff("room-001","beth-id")
        self.assertEqual(status,200)
        self.assertEqual(api.call_count,3)
        self.assertEqual([c.args[0] for c in sleeping.call_args_list],[2.0,2.5])
        self.assertIn("RoomNomiNotReadyForMessage",output.getvalue())

    def test_resume_recorded_not_ready_reply(self):
        plan=u.plan_text([str(self.diary)],"Beth","Tester","US",2026,750)
        first_prompt=next(i for i,m in enumerate(plan,1) if m["kind"]=="prompt")
        self.run_upload(FakeNomi(),self.args())
        events=[e for e in u.records(self.checkpoint)
                if not (e.get("pass")==1 and e.get("index")>first_prompt)
                and not (e.get("pass")==1 and e.get("index")==first_prompt
                         and e["event"]=="reply_committed")]
        events.append({"event":"reply_uncertain","pass":1,"index":first_prompt,
                       "http_status":400,
                       "api_response":{"type":"RoomNomiNotReadyForMessage"}})
        self.checkpoint.write_text("".join(json.dumps(e)+"\n" for e in events),
                                   encoding="utf-8")
        self.completion.unlink()
        fake=FakeNomi()
        self.run_upload(fake,self.args(resume=True))
        self.assertEqual(len(fake.calls_to("/chat/request")),2)
        self.assertEqual(len(fake.calls_to("/chat")),len(plan)-first_prompt)
        self.assertTrue(self.completion.exists())

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

    def test_explicit_legacy_noreply_recovery(self):
        plan=u.plan_text([str(self.diary)],"Beth","Tester","US",2026,750)
        first_prompt=next(i for i,m in enumerate(plan,1) if m["kind"]=="prompt")
        self.run_upload(FakeNomi(),self.args())
        original=u.records(self.checkpoint)
        events=[e for e in original if not
                (e.get("pass")==1 and e.get("index")>first_prompt) and not
                (e.get("pass")==1 and e.get("index")==first_prompt and
                 e["event"]=="reply_committed")]
        self.checkpoint.write_text("".join(json.dumps(e)+"\n" for e in events),
                                   encoding="utf-8")
        self.completion.unlink()
        with self.assertRaisesRegex(RuntimeError,"Uncertain"):
            self.run_upload(FakeNomi(),self.args(resume=True))
        args=self.args(resume=True)
        args.recover_noreply=["1:%d"%first_prompt]
        fake=FakeNomi()
        self.run_upload(fake,args)
        self.assertEqual(len(fake.calls_to("/chat/request")),2)
        self.assertEqual(len(fake.calls_to("/chat")),len(plan)-first_prompt)
        self.assertTrue(self.completion.exists())

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
