"""ChatGPT selected-branch imports and Nomi downloader compatibility."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import legacy_v085 as legacy

spec = importlib.util.spec_from_file_location("gpt_uploader", ROOT / "nomi-uploader.py")
uploader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(uploader)


def node(parent, role, text, **extra):
    message = {"author": {"role": role}, "content": {"content_type": "text", "parts": [text]},
               "create_time": 1745629158, **extra}
    return {"parent": parent, "children": [], "message": message}


def conversation():
    return {"title": "A chat", "create_time": 1745629158, "id": "chat-1", "current_node": "answer",
            "mapping": {
                "root": {"parent": None, "children": ["hidden"], "message": None},
                "hidden": node("root", "system", "hidden instructions"),
                "user": node("hidden", "user", "Hello"),
                "alternate": node("user", "assistant", "Unselected answer"),
                "thought": node("user", "assistant", "Internal text", channel="analysis"),
                "tool": node("thought", "tool", "Tool result"),
                "answer": node("tool", "assistant", "Selected answer", create_time=1745629159000)}}


class ChatGPTExportTests(unittest.TestCase):
    def load(self, data):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "conversation.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            return legacy.load_conversation(path)

    def test_selected_branch_and_millisecond_dates(self):
        for data in (conversation(), [conversation()]):
            name, rows = self.load(data)
            self.assertEqual(name, "ChatGPT")
            self.assertEqual([r["message"] for r in rows], ["Hello", "Selected answer"])
            self.assertEqual([r["sender"] for r in rows], ["User", "ChatGPT"])
            self.assertEqual(rows[1]["date"], "2025-04-26T00:59:19+00:00")
            self.assertEqual(rows[1]["conversation_title"], "A chat")

    def test_chronological_conversations_and_multimodal_text(self):
        later = conversation()
        later.update(id="chat-2", create_time=1745629160)
        later["mapping"]["user"]["message"]["content"] = {
            "content_type": "multimodal_text", "parts": ["Before", {"asset_pointer": "image"}, " after"]}
        _, rows = self.load([later, conversation()])
        self.assertEqual([r["session"] for r in rows], ["chat-1", "chat-1", "chat-2", "chat-2"])
        self.assertEqual(rows[2]["message"], "Before after")

    def test_rejects_invalid_branch(self):
        data = conversation()
        data["mapping"]["user"]["parent"] = "answer"
        with self.assertRaisesRegex(ValueError, "branch"):
            self.load(data)

    def test_zip_prefers_conversations_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "export.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("other.json", "{}")
                archive.writestr("export/conversations.json", json.dumps([conversation()]))
            self.assertEqual(len(legacy.load_conversation(path)[1]), 2)

    def test_nomi_text_and_voice_unchanged(self):
        data = {"nomi": {"name": "Ava", "chat": [
            {"date": "2025-01-01", "sender": "User", "message": "Hi"}],
            "voiceCalls": [{"messages": [
                {"date": "2025-01-02", "sender": "Ava", "message": "Hello"}]}]}}
        name, rows = self.load(data)
        self.assertEqual(name, "Ava")
        self.assertEqual([(r["source"], r["message"]) for r in rows], [("chat", "Hi"), ("voice", "Hello")])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nomi.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("ava_data.json", json.dumps(data))
            self.assertEqual(legacy.load_conversation(path), (name, rows))

    def test_chunk_interval_and_zero(self):
        data = conversation()
        data["mapping"]["answer"]["message"]["content"]["parts"] = ["Long reply. " * 1200]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "conversation.json"
            path.write_text(json.dumps([data]), encoding="utf-8")
            for interval in (10, 20, 0):
                messages = uploader.plan_text([str(path)], "Ava", "", "US", 2026, 750,
                                              interval, chunk_mode="chars")
                pending = 0
                prompts = 0
                for message in messages:
                    if message["kind"] == "content":
                        pending += 1
                    elif message["kind"] == "prompt":
                        self.assertGreater(pending, 0)
                        self.assertLessEqual(pending, interval)
                        pending = 0
                        prompts += 1
                self.assertEqual(prompts > 0, interval > 0)
                if interval:
                    self.assertEqual(pending, 0)
