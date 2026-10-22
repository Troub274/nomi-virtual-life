"""Nomi Uploader v1.1 regression tests."""
import importlib.util
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location("nomi_uploader_v11", ROOT / "nomi-uploader.py")
u = importlib.util.module_from_spec(spec)
spec.loader.exec_module(u)

old_spec = importlib.util.spec_from_file_location(
    "nomi_uploader_v10_archive", ROOT / "archive" / "nomi-uploader-v1.0.py")
v10 = importlib.util.module_from_spec(old_spec)
old_spec.loader.exec_module(v10)


class V11Tests(unittest.TestCase):
    def test_entry_range_parser(self):
        self.assertEqual(u.parse_entry_range("45-100"), (45, 100))
        self.assertEqual(u.parse_entry_range("45-"), (45, None))
        self.assertEqual(u.parse_entry_range("-100"), (None, 100))
        self.assertEqual(u.parse_entry_range("45"), (45, 45))
        self.assertIsNone(u.parse_entry_range("all"))
        with self.assertRaises(ValueError):
            u.parse_entry_range("100-45")

    def test_character_split_uses_characters_not_utf8_bytes(self):
        text = "é" * 900
        parts = u.split_char_budget(text, 750)
        self.assertEqual([len(x) for x in parts], [750, 150])
        self.assertGreater(len(parts[0].encode("utf-8")), 750)

    def test_journal_entry_range_and_character_ceiling(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "journal.txt"
            entries = []
            for i in range(40, 106):
                entries.append(
                    "ENTRY %03d — 2026-01-%02d\n%s\n" %
                    (i, ((i - 1) % 28) + 1, ("Memory %d. " % i) * 80))
            path.write_text(
                "[Diary]\nType: Journal\nSource: Tammy\nProcess Every: 5\n\n"
                + "".join(entries), encoding="utf-8")
            plan = u.plan_text(
                [str(path)], "Tammy", "", "US", 2026, 750, 0,
                u.parse_entry_range("45-100"), "chars")
            contents = [m for m in plan if m["kind"] == "content"]
            labels = {int(m["entry_label"]) for m in contents}
            self.assertEqual(labels, set(range(45, 101)))
            self.assertTrue(all(len(m["text"]) <= 750 for m in plan))
            prompts = [m["text"] for m in plan if m["kind"] == "prompt"]
            self.assertIn("entries 045-049", prompts[0])
            self.assertIn("entries 095-099", prompts[-2])
            self.assertIn("entries 100-100", prompts[-1])

    def test_character_mode_refuses_more_than_api_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "journal.txt"
            path.write_text(
                "[Diary]\nType: Journal\nSource: Tammy\n\n"
                "ENTRY 001 — 2026-01-01\nShort memory.\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                u.plan_text([str(path)], "Tammy", "", "US", 2026, 801,
                            0, None, "chars")

    def test_v10_byte_planner_is_preserved_exactly(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "journal.txt"
            path.write_text(
                "[Diary]\nType: Journal\nSource: Beth\nProcess Every: 2\n"
                "Nomi: Beth, consider entries 1-2 carefully.\n\n"
                "ENTRY 001 — 1998-10-11\nA memory with é and punctuation. " + ("x" * 900) + "\n"
                "ENTRY 002 — 1998-10-12\nSecond memory.\n",
                encoding="utf-8")
            old_plan = v10.plan_text([str(path)], "Beth", "", "US", 2026, 750, 0)
            new_plan = u.plan_text([str(path)], "Beth", "", "US", 2026, 750, 0,
                                   None, "bytes")
            self.assertEqual(new_plan, old_plan)
            self.assertEqual(u.digest(new_plan), v10.digest(old_plan))

    def test_created_room_note_uses_current_version(self):
        with patch.object(u.legacy, "api_request",
                          return_value=(200, {"uuid": "room"})) as api_request, \
             patch.object(u.legacy, "wait_for_room"):
            room = u.create_upload_room({"name": "Tammy", "uuid": "nomi"})
        self.assertEqual(room, "room")
        payload = api_request.call_args.args[2]
        self.assertEqual(
            payload["note"],
            "Nomi Uploader v%s — persistent processing room" % u.VERSION)

    def test_checkpoint_status_classifies_safe_resume_and_ambiguity(self):
        with tempfile.TemporaryDirectory() as tmp:
            cp = pathlib.Path(tmp) / "checkpoint.jsonl"
            u.record(cp, {
                "event":"start", "run_id":"r", "nomi_uuid":"n", "nomi_name":"Tammy",
                "room_uuid":"room", "year":2026, "order":"US", "files":["x"],
                "passes":1, "messages_per_pass":3, "manifest":"m"
            })
            u.record(cp, {"event":"attempt", "pass":1, "index":1})
            u.record(cp, {"event":"confirmed", "pass":1, "index":1, "kind":"content"})
            self.assertEqual(u.checkpoint_summary(cp)["state"], "SAFE_TO_RESUME")
            u.record(cp, {"event":"attempt", "pass":1, "index":2})
            info = u.checkpoint_summary(cp)
            self.assertEqual(info["state"], "AMBIGUOUS_SEND")
            self.assertEqual(info["uncertain_sends"], [(1, 2)])


if __name__ == "__main__":
    unittest.main()
