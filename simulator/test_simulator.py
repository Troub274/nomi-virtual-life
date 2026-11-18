import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

from nomi_simulator import ROOM, Simulator


class RecoveryTests(unittest.TestCase):
    def test_real_uploader_stops_then_resumes_lost_send(self):
        with Simulator(scenario="lost-send") as server, tempfile.TemporaryDirectory() as tmp:
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                root = Path(tmp)
                root.joinpath("facts.txt").write_text("[Facts]\nType: Knowledge\n\nFirst fact.\n\nSecond fact.\n", encoding="utf-8")
                client = Path(__file__).with_name("run_test_harness.py")
                command = [sys.executable, str(client), "--port", str(server.server_port), "--", "--delay", "0"]
                def run(*args):
                    return subprocess.run(command + list(args), cwd=tmp, input="", capture_output=True, text=True, timeout=15)
                failed = run("--nomi-uuid", "22222222-2222-2222-2222-222222222222", "--room", ROOM, "facts.txt")
                self.assertNotEqual(failed.returncode, 0)
                self.assertIn("outcome uncertain", failed.stderr)
                blocked = run("--resume")
                self.assertNotEqual(blocked.returncode, 0)
                self.assertEqual(len([e for e in server.events if e["path"].endswith("/chat")]), 2)
                resumed = run("--resume", "--retry-uncertain-send", "1:2")
                self.assertEqual(resumed.returncode, 0, resumed.stdout + resumed.stderr)
                sends = [e for e in server.events if e["path"].endswith("/chat")]
                self.assertEqual(len(sends), 4)
                self.assertTrue(sends[1]["response_dropped"])
                self.assertEqual(sends[1]["body"], sends[2]["body"])
                self.assertTrue(json.loads(root.joinpath("nomi_uploader_completed.json").read_text())["completed_at"])
            finally:
                server.shutdown()
                thread.join()
    def test_dry_run_posts_nothing_and_live_range_sends_only_selected_chunk(self):
        with Simulator() as server, tempfile.TemporaryDirectory() as tmp:
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                Path(tmp, "facts.txt").write_text(
                    "[Facts]\nType: Knowledge\n\nFirst fact.\n\nSecond fact.\n", encoding="utf-8")
                client = Path(__file__).with_name("run_test_harness.py")
                command = [sys.executable, str(client), "--port", str(server.server_port),
                           "--", "--delay", "0", "--start-chunk", "2", "--end-chunk", "2"]
                preview = subprocess.run(command + ["--dry-run", "facts.txt"], cwd=tmp,
                                         input="", capture_output=True, text=True, timeout=15)
                self.assertEqual(preview.returncode, 0, preview.stderr)
                self.assertFalse(server.events)
                live = subprocess.run(command + ["--nomi-uuid", "22222222-2222-2222-2222-222222222222",
                                                 "--room", ROOM, "facts.txt"], cwd=tmp,
                                      input="", capture_output=True, text=True, timeout=15)
                self.assertEqual(live.returncode, 0, live.stderr)
                sends = [e for e in server.events if e["method"] == "POST"]
                self.assertEqual(len(sends), 1)
                self.assertIn("First fact.", sends[0]["body"]["messageText"])
            finally:
                server.shutdown()
                thread.join()
    def test_isolated_ini_controls_key_and_endpoint(self):
        import os
        with Simulator() as server, tempfile.TemporaryDirectory() as tmp:
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                ini = Path(tmp, "test.ini")
                Path(tmp, "facts.txt").write_text("[Facts]\nType: Knowledge\n\nExample.\n", encoding="utf-8")
                command = [sys.executable, str(Path(__file__).with_name("run_test_harness.py")),
                           "--ini", str(ini), "--", "--nomi-uuid",
                           "22222222-2222-2222-2222-222222222222", "--room", ROOM, "facts.txt"]
                for key, expected in [("", "No API key configured"), ("wrong-dummy", "401"),
                                      ("simulator-only-key", None)]:
                    ini.write_text(f"[nomi]\nendpoint = http://127.0.0.1:{server.server_port}/v1\n"
                                   f"api_key = {key}\n", encoding="utf-8")
                    result = subprocess.run(command, cwd=tmp, input="", capture_output=True, text=True,
                                            timeout=90, env={**os.environ, "NOMI_API_KEY": "simulator-only-key"})
                    if expected is None:
                        self.assertEqual(result.returncode, 0, result.stderr)
                    else:
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn(expected, result.stderr)
                        self.assertFalse(server.events)
            finally:
                server.shutdown()
                thread.join()
