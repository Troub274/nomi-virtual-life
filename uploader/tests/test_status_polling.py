"""Keep large checkpoint polling bounded and share one scan per revision."""
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_uploader import u

ROOT = Path(__file__).resolve().parents[1]


class StatusPollingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        with patch.dict(os.environ, {"LOCALAPPDATA": str(self.root)}):
            spec = importlib.util.spec_from_file_location("polling_gui", ROOT / "gui/app.py")
            self.gui = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.gui)
        self.api = self.gui.API.__new__(self.gui.API)
        self.api.project = {}
        self.api.proc = None
        self.api.lock = threading.Lock()
        self.api.lines = deque(maxlen=1000)
        self.api._checkpoint_lock = threading.Lock()
        self.api._checkpoint_module = u
        self.cp = self.gui.DATA / "upload.jsonl"

    def write_checkpoint(self, count):
        events = [{"event": "start", "nomi_name": "Simulator", "nomi_uuid": "nomi",
                   "room_uuid": "room", "passes": 1, "messages_per_pass": count}]
        for index in range(1, count + 1):
            events.append({"event": "confirmed", "pass": 1, "index": index,
                           "kind": "prompt" if index > count - 100 else "content"})
            if index > count - 100:
                events.append({"event": "reply_committed", "pass": 1, "index": index,
                               "prompt": "Reflect", "reply": {"messageText": "Reply " + str(index)}})
        self.cp.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")

    def test_31000_messages_share_one_scan_and_only_keep_recent_replies(self):
        self.write_checkpoint(31000)
        with patch.object(u, "active_records", wraps=u.active_records) as scan:
            recovery = self.api.recovery_status()
            for _ in range(20):
                status = self.api.status()
            self.assertEqual(scan.call_count, 1)
        self.assertEqual(recovery["state"], "COMPLETE")
        self.assertEqual(status["confirmed"], 31000)
        self.assertEqual(status["total"], 31000)
        self.assertEqual(len(status["replies"]), 50)
        self.assertEqual(status["replies"][-1]["index"], 31000)

    def test_concurrent_status_calls_share_the_checkpoint_scan(self):
        self.write_checkpoint(31000)
        with patch.object(u, "active_records", wraps=u.active_records) as scan:
            with ThreadPoolExecutor(max_workers=16) as workers:
                statuses = list(workers.map(lambda _: self.api.status(), range(64)))
            self.assertEqual(scan.call_count, 1)
        self.assertTrue(all(s["confirmed"] == 31000 for s in statuses))

    def test_append_and_manual_restart_invalidate_snapshot(self):
        self.write_checkpoint(1)
        with patch.object(u, "active_records", wraps=u.active_records) as scan:
            self.assertEqual(self.api.status()["confirmed"], 1)
            start = {"event": "start", "nomi_name": "Simulator", "nomi_uuid": "nomi",
                     "room_uuid": "room", "passes": 1, "messages_per_pass": 2}
            u.record(self.cp, {"event": "manual_restart", "pass": 1, "index": 1,
                               "start": start, "prefix_prompts": []})
            self.assertEqual(self.api.status()["confirmed"], 0)
            self.assertEqual(self.api.status()["total"], 2)
            u.record(self.cp, {"event": "confirmed", "pass": 1, "index": 1, "kind": "content"})
            self.assertEqual(self.api.status()["confirmed"], 1)
            self.assertEqual(scan.call_count, 3)

    def test_deleting_checkpoint_clears_cached_status(self):
        self.write_checkpoint(1)
        self.api.status()
        self.cp.unlink()
        self.assertEqual(self.api.status()["confirmed"], 0)
        self.assertEqual(self.api.recovery_status()["state"], "NO_CHECKPOINT")

    def test_subprocess_log_is_bounded(self):
        process = SimpleNamespace(stdout=iter(f"line {i}\n" for i in range(5000)))
        with patch.object(self.gui.subprocess, "Popen", return_value=process), \
             patch.object(self.gui.threading, "Thread") as worker:
            self.api._run(["--dry-run"])
            worker.call_args.kwargs["target"]()
        self.assertEqual(len(self.api.lines), 1000)
        self.assertEqual(self.api.lines[-1], "line 4999")


    def test_history_reads_only_the_start_of_large_checkpoint(self):
        self.write_checkpoint(31000)
        with patch.object(Path, "read_text", side_effect=AssertionError("whole-file history read")):
            runs = self.api.list_runs()
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["nomi"], "Simulator")
