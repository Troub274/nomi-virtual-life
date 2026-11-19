"""Operator-verified private replies unblock resume without another API request."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_uploader import u


class VerifiedPrivateReplyTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.cp=Path(temporary.name)/"checkpoint.jsonl"
        self.prompt="Reflect on conversations 101-110.\nMemory date: 2025-04-26"
        events=[
            {"event":"start","reply_destination":"private","nomi_uuid":"nomi","room_uuid":"room",
             "passes":1,"messages_per_pass":123},
            {"event":"confirmed","pass":1,"index":122,"kind":"prompt",
             "sha256":hashlib.sha256(self.prompt.encode()).hexdigest(),
             "api_response":{"sentMessage":{"text":self.prompt}}},
            {"event":"reply_attempt","pass":1,"index":122,"reply_destination":"private"},
            {"event":"reply_uncertain","pass":1,"index":122,"http_status":500,
             "api_response":{"error":{"type":"NoReply"}}}]
        self.cp.write_text("".join(json.dumps(e)+"\n" for e in events),encoding="utf-8")

    def test_records_reply_with_backup_and_is_idempotent(self):
        before=self.cp.read_bytes()
        with patch.object(u.legacy,"api_request",side_effect=AssertionError("network")):
            result=u.accept_private_reply(self.cp,"1:122","The actual received reply.")
            repeat=u.accept_private_reply(self.cp,"1:122","The actual received reply.")
        self.assertTrue(result["recorded"])
        self.assertFalse(repeat["recorded"])
        self.assertEqual(result["state"],"SAFE_TO_RESUME")
        self.assertEqual(Path(result["backup"]).read_bytes(),before)
        self.assertTrue(self.cp.read_bytes().startswith(before))
        committed=[e for e in u.records(self.cp) if e["event"]=="reply_committed"]
        self.assertEqual(len(committed),1)
        self.assertTrue(committed[0]["operator_verified"])
        self.assertEqual(committed[0]["prompt"],self.prompt)

    def test_rejects_empty_wrong_position_room_and_changed_prompt(self):
        for token,text in (("1:122",""),("1:121","Reply"),("0:122","Reply")):
            with self.assertRaises(ValueError):
                u.accept_private_reply(self.cp,token,text)
        events=u.records(self.cp)
        events[1]["api_response"]["sentMessage"]["text"]="Different prompt"
        self.cp.write_text("".join(json.dumps(e)+"\n" for e in events),encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"verify"):
            u.accept_private_reply(self.cp,"1:122","Reply")
        events[0]["reply_destination"]="room"
        self.cp.write_text("".join(json.dumps(e)+"\n" for e in events),encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"private"):
            u.accept_private_reply(self.cp,"1:122","Reply")

    def test_active_upload_lock_blocks_receipt(self):
        with u.checkpoint_lock(self.cp):
            with self.assertRaises(RuntimeError):
                u.accept_private_reply(self.cp,"1:122","Reply")

    def cli_args(self):
        from types import SimpleNamespace
        return SimpleNamespace(checkpoint=self.cp,recover_uncertain_reply=[])

    def test_cli_enter_confirms_without_resending(self):
        args=self.cli_args()
        with patch("builtins.input",return_value=""), patch("builtins.print"):
            self.assertTrue(u.review_private_replies(args))
        self.assertEqual(u.checkpoint_summary(self.cp)["state"],"SAFE_TO_RESUME")
        self.assertEqual(u.records(self.cp)[-1]["reply"],{"text":""})
        self.assertEqual(args.recover_uncertain_reply,[])

    def test_cli_pastes_multiline_reply(self):
        with patch("builtins.input",side_effect=["p","First line","Second line","."]), patch("builtins.print"):
            self.assertTrue(u.review_private_replies(self.cli_args()))
        self.assertEqual(u.records(self.cp)[-1]["reply"]["text"],"First line\nSecond line")

    def test_cli_wait_and_retry_do_not_commit_receipt(self):
        before=self.cp.read_bytes()
        args=self.cli_args()
        with patch("builtins.input",return_value="w"), patch("builtins.print"):
            self.assertFalse(u.review_private_replies(args))
        with patch("builtins.input",side_effect=["r","no","r","RETRY"]), patch("builtins.print"):
            self.assertTrue(u.review_private_replies(args))
        self.assertEqual(args.recover_uncertain_reply,["1:122"])
        self.assertEqual(self.cp.read_bytes(),before)

    def test_cli_noninteractive_resume_does_not_prompt(self):
        with patch.object(u.sys.stdin,"isatty",return_value=False), \
             patch.object(u.legacy,"resolved_api_key",return_value="test"), \
             patch.object(u,"review_private_replies") as review, patch.object(u,"upload") as upload:
            u.main(["--resume","--checkpoint",str(self.cp)])
        review.assert_not_called()
        upload.assert_called_once()

    def test_cli_resume_wait_stops_before_upload(self):
        with patch.object(u.sys.stdin,"isatty",return_value=True), \
             patch("builtins.input",return_value="w"), patch("builtins.print"), \
             patch.object(u,"upload") as upload:
            u.main(["--resume","--checkpoint",str(self.cp)])
        upload.assert_not_called()

    def test_explicit_confirmation_without_text_unblocks_resume(self):
        result=u.accept_private_reply(self.cp,"1:122","",allow_empty=True)
        self.assertEqual(result["state"],"SAFE_TO_RESUME")
        event=u.records(self.cp)[-1]
        self.assertEqual(event["reply"],{"text":""})
        self.assertTrue(event["operator_verified"])
        self.assertFalse(u.accept_private_reply(self.cp,"1:122","",allow_empty=True)["recorded"])

    def test_gui_recovers_matching_run_without_network(self):
        import importlib.util
        import sys
        from types import SimpleNamespace
        spec=importlib.util.spec_from_file_location("verified_reply_gui",Path(u.__file__).parent/"gui"/"app.py")
        gui=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,{"webview":SimpleNamespace()}):
            spec.loader.exec_module(gui)
        api=gui.API.__new__(gui.API)
        api.proc=None
        api._active_dir=lambda:self.cp.parent
        # The GUI uses the fixed upload.jsonl filename.
        target=self.cp.with_name("upload.jsonl")
        self.cp.rename(target)
        self.cp=target
        api._checkpoint_module=u
        details=api.private_reply_recovery()
        self.assertEqual(details[0]["prompt"],self.prompt)
        with self.assertRaisesRegex(ValueError,"changed"):
            api.accept_received_reply("another run","1:122","")
        with patch.object(u.legacy,"api_request",side_effect=AssertionError("network")):
            result=api.accept_received_reply(str(target),"1:122","")
        self.assertEqual(result["state"],"SAFE_TO_RESUME")
        self.assertEqual(api.private_reply_recovery(),[])
        self.assertEqual(api._checkpoint_view()["replies"][-1]["reply"],"No reply text was recorded.")
