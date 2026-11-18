"""Regression coverage for literal transcript headings in GUI working copies."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("transcript_gui", ROOT / "gui/app.py")
gui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gui)
spec = importlib.util.spec_from_file_location("transcript_uploader", ROOT / "nomi-uploader.py")
uploader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(uploader)


class TranscriptMetadataTests(unittest.TestCase):
    def test_chat_metadata_survives_bracketed_content(self):
        api = gui.API.__new__(gui.API)
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "chat.txt"
            text = "Ava: Hello\n\n[Pre-Training Sanitizer]\nAva: Still talking\n\n[Clean Buffer]\nAva: Goodbye\n"
            source.write_text(text, encoding="utf-8")
            item = {"path": str(source), "fields": {
                "type": "Chat", "date": "2026-01-01", "mode": "Add"}}
            paths = api._paths(Path(temp), [item])
            sections = uploader.parse_sections(Path(paths[0]).read_text(encoding="utf-8"), paths[0])
            self.assertEqual([s["type"] for s in sections], ["chat"])
            self.assertIn("[Pre-Training Sanitizer]", sections[0]["lines"])
            messages = uploader.plan_text(paths, "Ava", "User", "US", 2026, 750, 1, chunk_mode="chars")
            prompts = [m["text"] for m in messages if m["kind"] == "prompt"]
            self.assertTrue(prompts)
            self.assertTrue(all("conversations" in p for p in prompts))
            self.assertEqual(source.read_text(encoding="utf-8"), text)

    def test_preserves_explicit_typed_sections(self):
        api = gui.API.__new__(gui.API)
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "mixed.txt"
            source.write_text("[Chat]\nType: Chat\nDate: 2026-01-01\n\nAva: Hello\n\n[Reference]\nType: Knowledge\n\nSome facts.\n", encoding="utf-8")
            text = api._build_txt(source, {"fields": {"type": "Chat", "date": "2026-01-01"}})
            self.assertEqual([s["type"] for s in uploader.parse_sections(text, str(source))], ["chat", "knowledge"])
