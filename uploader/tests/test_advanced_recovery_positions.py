"""Validate advanced recovery positions before delegating to checkpoint checks."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class AdvancedRecoveryPositionTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        with patch.dict(os.environ,{"LOCALAPPDATA":str(self.root)}):
            spec=importlib.util.spec_from_file_location(
                "advanced_position_gui",Path(__file__).resolve().parents[1]/"gui/app.py")
            gui=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(gui)
        self.api=gui.API.__new__(gui.API)
        self.api.proc=None
        self.api._active_dir=lambda:self.root
        (self.root/"upload.jsonl").write_text("checkpoint exists\n",encoding="utf-8")

    def test_valid_positions_reach_cli_for_both_operations(self):
        for operation,flag in (("noreply","--recover-noreply"),("migrate","--abandon-reply")):
            for position in ("1:1","1:499","12:345"," 1:499 "):
                with self.subTest(operation=operation,position=position), \
                     patch.object(self.api,"recovery_status",return_value={"state":"SAFE_TO_RESUME"}), \
                     patch.object(self.api,"_run",return_value=True) as run:
                    self.assertTrue(self.api.advanced_resume(operation,position))
                    args=run.call_args.args[0]
                    self.assertEqual(args[args.index(flag)+1],position.strip())
                    self.assertIn("--resume",args)
                    if operation=="migrate":
                        self.assertIn("--new-room-on-resume",args)

    def test_invalid_positions_are_rejected_before_checkpoint_access(self):
        for position in ("", "0:1", "1:0", "-1:2", "1.5:2", "1", "1:2:3", "n:n", "01:2", "1:02", "1:2d"):
            with self.subTest(position=position), \
                 patch.object(self.api,"_active_dir",side_effect=AssertionError("checkpoint access")), \
                 patch.object(self.api,"_run") as run:
                with self.assertRaisesRegex(ValueError,"positive integers"):
                    self.api.advanced_resume("noreply",position)
                run.assert_not_called()

    def test_completed_checkpoint_cannot_be_resumed(self):
        with patch.object(self.api,"recovery_status",return_value={"state":"COMPLETE"}), \
             patch.object(self.api,"_run") as run:
            with self.assertRaisesRegex(ValueError,"cannot be resumed"):
                self.api.advanced_resume("noreply","1:499")
            run.assert_not_called()

    def test_continue_after_receipts_never_authorizes_retries(self):
        for state in ("SAFE_TO_RESUME", "COMPLETE"):
            with self.subTest(state=state), \
                 patch.object(self.api,"recovery_status",return_value={"state":state}), \
                 patch.object(self.api,"_run",return_value=True) as run:
                self.assertTrue(self.api.continue_after_received_replies())
                args=run.call_args.args[0]
                self.assertIn("--resume",args)
                self.assertFalse(any(x.startswith(("--recover-","--retry-","--manual-restart")) for x in args))

    def test_continue_refuses_other_pending_operations(self):
        for pending in ("uncertain_sends", "ambiguous_replies", "retryable_replies"):
            with self.subTest(pending=pending), \
                 patch.object(self.api,"recovery_status",return_value={"state":"SAFE_TO_RESUME",pending:[[1,499]]}), \
                 patch.object(self.api,"_run") as run:
                with self.assertRaisesRegex(ValueError,"No resend was authorized"):
                    self.api.continue_after_received_replies()
                run.assert_not_called()
