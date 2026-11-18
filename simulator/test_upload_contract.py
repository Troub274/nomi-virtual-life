"""Drive GUI preparation and the real uploader through the loopback HTTP API."""
import importlib.util
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from nomi_simulator import NOMI, ROOM, Simulator
from regression_fixtures import write_chatgpt, write_nomi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "uploader"))


class UploadContractTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.environment = {**os.environ, "LOCALAPPDATA": str(self.root / "appdata"),
                            "NOMI_API_KEY": ""}
        with patch.dict(os.environ, self.environment):
            spec = importlib.util.spec_from_file_location("simulator_gui", ROOT / "uploader/gui/app.py")
            self.gui = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.gui)
        self.api = self.gui.API.__new__(self.gui.API)
        self.api.proc = None
        self.api.project = {"queue": [], "nomi": "Simulator", "nomi_uuid": NOMI,
                            "room_uuid": ROOM, "process": 10, "reply_wait": 30}
        self.api._run = self.execute

    def start_server(self, scenario="normal"):
        self.server = Simulator(scenario=scenario, delay=0)
        worker = threading.Thread(target=self.server.serve_forever)
        worker.start()
        def stop():
            self.server.shutdown()
            worker.join()
            self.server.server_close()
        self.addCleanup(stop)

    def execute(self, args):
        command = [sys.executable, str(ROOT / "simulator/run_test_harness.py"),
                   "--port", str(self.server.server_port), "--", "--delay", "0", *args]
        return subprocess.run(command, cwd=self.root, env=self.environment,
                              input="", capture_output=True, text=True, encoding="utf-8", timeout=45)

    def chat_item(self, path, interval=""):
        return {"path": str(path), "export_fields": {
            "mode": "Add", "intro": "", "periodic": "Simulator, relive chunks {first}-{last}.",
            "process": interval}}

    def chat_posts(self):
        return [event for event in self.server.events if event["path"].endswith("/chat")]

    def requests(self):
        return [event for event in self.server.events if event["path"].endswith("/chat/request")]

    def checkpoint(self):
        return self.gui.DATA / "runs" / self.api.project["active_run"] / "upload.jsonl"

    def events(self):
        return [json.loads(line) for line in self.checkpoint().read_text(encoding="utf-8").splitlines()]

    def expected_plan(self, item):
        directory = self.root / "expected"
        directory.mkdir(exist_ok=True)
        paths = self.api._paths(directory, [item])
        cli = runpy.run_path(str(ROOT / "uploader/nomi-uploader.py"))
        return cli["plan_text"](paths, "Simulator", "", "US", 2026, 750,
                                self.api.project["process"], chunk_mode="chars",
                                export_options=self.api._export_options([item]),
                                prompt_table=cli["load_prompt_table"](self.gui.DATA))

    def assert_cadence(self, expected, interval):
        self.assertEqual([e["body"]["messageText"] for e in self.chat_posts()],
                         [message["text"] for message in expected])
        self.assertEqual(len(self.requests()), sum(m["kind"] == "prompt" for m in expected))
        self.assertTrue(all(len(e["body"]["messageText"]) <= 750 for e in self.chat_posts()))
        pending = 0
        batches = []
        for message in expected:
            if message["kind"] == "content":
                pending += 1
            elif message["kind"] == "prompt":
                batches.append(pending)
                pending = 0
        if interval:
            self.assertTrue(batches)
            self.assertTrue(all(count == interval for count in batches[:-1]))
            self.assertTrue(1 <= batches[-1] <= interval)
            self.assertEqual(pending, 0)
        else:
            self.assertEqual(batches, [])
        # Every reflection must request a reply before sending later content.
        expected_paths = []
        for message in expected:
            expected_paths.append("/v1/rooms/" + ROOM + "/chat")
            if message["kind"] == "prompt":
                expected_paths.append("/v1/rooms/" + ROOM + "/chat/request")
        self.assertEqual([e["path"] for e in self.server.events if e["method"] == "POST"],
                         expected_paths)

    def test_export_cadence_file_overrides_and_zero(self):
        self.start_server()
        for writer in (write_chatgpt, write_nomi):
            for interval in ("", "20", "0"):
                with self.subTest(format=writer.__name__, interval=interval):
                    self.server.events.clear()
                    item = self.chat_item(writer(self.root / "chat.json"), interval)
                    self.api.project["queue"] = [item]
                    expected = self.expected_plan(item)
                    preview = self.api._preview_file(item, self.api.project)
                    self.assertEqual(preview["count"], len(expected))
                    self.assertEqual(self.server.events, [])
                    result = self.api.begin()
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertNotIn("DISCARDED BRANCH", "".join(
                        event["body"]["messageText"] for event in self.chat_posts()))
                    self.assert_cadence(expected, 10 if interval == "" else int(interval))

    def test_bracketed_txt_keeps_chat_prompts_on_the_wire(self):
        self.start_server()
        source = self.root / "chat.txt"
        body = "User: Hello\n\n[Pre-Training Sanitizer]\nSimulator: Still chatting.\n"
        source.write_text(body, encoding="utf-8")
        item = {"path": str(source), "fields": {
            "title": "Chat", "type": "Chat", "date": "2025-01-01", "process": "1"}}
        self.api.project["queue"] = [item]
        expected = self.expected_plan(item)
        result = self.api.begin()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_cadence(expected, 1)
        prompts = [m["text"] for m in expected if m["kind"] == "prompt"]
        self.assertTrue(all("conversations" in text for text in prompts))
        self.assertIn("[Pre-Training Sanitizer]", "".join(m["text"] for m in expected))
        self.assertEqual(source.read_text(encoding="utf-8"), body)

    def test_lost_reply_blocks_resume_and_authorized_retry_preserves_interval(self):
        self.start_server("lost-reply")
        self.api.project["queue"] = [self.chat_item(write_chatgpt(self.root / "chat.json"))]
        failed = self.api.begin()
        self.assertNotEqual(failed.returncode, 0)
        before = len(self.chat_posts())
        self.api.project["process"] = 20
        blocked = self.execute(["--resume", "--checkpoint", str(self.checkpoint()),
                                "--process-every", "20"])
        self.assertNotEqual(blocked.returncode, 0)
        self.assertEqual(len(self.chat_posts()), before)
        pending = next(e["index"] for e in self.events() if e["event"] == "reply_uncertain")
        recovered = self.api.recover_resume(reply_tokens=[f"1:{pending}"])
        self.assertEqual(recovered.returncode, 0, recovered.stdout + recovered.stderr)
        self.assertEqual(self.events()[0]["process_every"], 10)
        self.assertEqual(sum(e["event"] == "reply_operator_override" for e in self.events()), 1)
        # Only the explicitly retried reply is duplicated; its prompt is sent once.
        self.assertEqual(len(self.requests()), sum(e["event"] == "reply_committed" for e in self.events()) + 1)
        self.assertTrue(self.requests()[0]["response_dropped"])

    def test_manual_restart_replans_interval_in_same_journal(self):
        self.start_server("lost-reply")
        self.api.project["queue"] = [self.chat_item(write_chatgpt(self.root / "chat.json"))]
        self.assertNotEqual(self.api.begin().returncode, 0)
        checkpoint = self.checkpoint()
        prior = checkpoint.read_bytes()
        self.api.project["process"] = 20
        restarted = self.api.manual_restart(1, 1)
        self.assertEqual(restarted.returncode, 0, restarted.stdout + restarted.stderr)
        self.assertEqual(self.checkpoint(), checkpoint)
        self.assertTrue(checkpoint.read_bytes().startswith(prior))
        boundaries = [e for e in self.events() if e["event"] == "manual_restart"]
        self.assertEqual(len(boundaries), 1)
        self.assertEqual(boundaries[0]["start"]["process_every"], 20)

    def test_not_ready_retries_reply_without_replaying_content(self):
        self.start_server("slow-then-fast")
        self.api.project["queue"] = [self.chat_item(write_nomi(self.root / "chat.json"), "20")]
        expected = self.expected_plan(self.api.project["queue"][0])
        result = self.api.begin()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual([event["status"] for event in self.requests()[:4]], [500, 500, 400, 200])
        self.assertEqual([e["body"]["messageText"] for e in self.chat_posts()],
                         [m["text"] for m in expected])
        committed = sum(e["event"] == "reply_committed" for e in self.events())
        self.assertEqual(len(self.requests()), committed + 3)

    def test_ambiguous_room_creation_is_not_repeated(self):
        self.start_server("lost-create")
        source = self.root / "facts.txt"
        source.write_text("[Facts]\nType: Knowledge\n\nA fact.\n", encoding="utf-8")
        failed = self.execute(["--nomi-uuid", NOMI, str(source)])
        self.assertNotEqual(failed.returncode, 0)
        creates = [event for event in self.server.events
                   if event["method"] == "POST" and event["path"] == "/v1/rooms"]
        self.assertEqual(len(creates), 1)
        self.assertTrue(creates[0]["response_dropped"])
        self.assertEqual(len(self.server.rooms), 2)
        self.assertEqual(self.chat_posts(), [])


    def test_malformed_reply_stops_before_more_content(self):
        self.start_server("malformed-reply")
        self.api.project["queue"] = [self.chat_item(write_nomi(self.root / "chat.json"))]
        result = self.api.begin()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no replyMessage", result.stderr)
        self.assertFalse(any(e["event"] == "reply_committed" for e in self.events()))
        before = len(self.server.events)
        blocked = self.execute(["--resume", "--checkpoint", str(self.checkpoint())])
        self.assertNotEqual(blocked.returncode, 0)
        self.assertEqual(len(self.server.events), before)

    def test_pause_resume_keeps_saved_interval_and_sends_each_message_once(self):
        self.start_server()
        item = self.chat_item(write_chatgpt(self.root / "chat.json"))
        self.api.project["queue"] = [item]
        expected = self.expected_plan(item)
        dispatch = self.server.dispatch
        def pause_after_second_send(method, path, body):
            response = dispatch(method, path, body)
            if method == "POST" and path.endswith("/chat"):
                if self.server.counts[(method, path)] == 2:
                    Path(str(self.checkpoint()) + ".pause").touch()
            return response
        with patch.object(self.server, "dispatch", pause_after_second_send):
            result = self.api.begin()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(self.chat_posts()), 2)
        self.assertTrue(any(e["event"] == "paused" for e in self.events()))
        self.api.project["process"] = 20
        resumed = self.api.resume()
        self.assertEqual(resumed.returncode, 0, resumed.stdout + resumed.stderr)
        self.assert_cadence(expected, 10)

    def test_outage_does_not_repeat_rejected_content_without_authorization(self):
        self.start_server("outage")
        item = self.chat_item(write_nomi(self.root / "chat.json"))
        self.api.project["queue"] = [item]
        failed = self.api.begin()
        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual(len(self.chat_posts()), 2)
        self.assertFalse(self.chat_posts()[1]["accepted"])
        blocked = self.execute(["--resume", "--checkpoint", str(self.checkpoint())])
        self.assertNotEqual(blocked.returncode, 0)
        self.assertEqual(len(self.chat_posts()), 2)
        recovered = self.api.recover_resume(send_tokens=["1:2"])
        self.assertEqual(recovered.returncode, 0, recovered.stdout + recovered.stderr)
        self.assertEqual(self.chat_posts()[1]["body"], self.chat_posts()[2]["body"])


    def test_periodic_prompt_file_setting_fallback_and_builtin(self):
        self.start_server()
        for file_prompt, global_prompt, expected_text in (
                ("", "", "live or relive conversations"),
                ("", "GLOBAL_REFLECT {first}-{last}", "GLOBAL_REFLECT"),
                ("FILE_REFLECT {first}-{last}", "GLOBAL_REFLECT {first}-{last}", "FILE_REFLECT")):
            with self.subTest(file_prompt=file_prompt, global_prompt=global_prompt):
                self.server.events.clear()
                item = self.chat_item(write_chatgpt(self.root / "chat.json"), "20")
                item["export_fields"]["periodic"] = file_prompt
                self.api.project.update(queue=[item], reply_prompt=global_prompt)
                result = self.api.begin()
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                committed = [e["prompt"] for e in self.events() if e["event"] == "reply_committed"]
                self.assertTrue(committed)
                self.assertTrue(all(expected_text in prompt for prompt in committed))
