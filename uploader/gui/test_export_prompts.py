"""Regression tests for ZIP/JSON prompt overrides; no network or files sent."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec=importlib.util.spec_from_file_location("uploader_module", ROOT / "nomi-uploader.py")
uploader=importlib.util.module_from_spec(spec)
spec.loader.exec_module(uploader)

ROWS=[{"text":"one"},{"text":"two"},{"text":"three"}]
FILE="sample-export.zip"

def plan(options,global_interval=0):
    with patch.object(uploader.legacy, "prepare_conversation_chunks", return_value=ROWS):
        return uploader.plan_text([FILE],"Ava","User","US",2026,750,
                                  global_interval,None,"chars",{FILE:options})

class ExportOptionsTests(unittest.TestCase):
    def test_unspecified_inherits_but_zero_disables_export(self):
        inherited=plan({"mode":"Replace","intro":"","process_every":""},2)
        disabled=plan({"mode":"Replace","intro":"","process_every":"0"},2)
        self.assertEqual(sum(m["kind"]=="prompt" for m in inherited),2)
        self.assertEqual(sum(m["kind"]=="prompt" for m in disabled),0)

    def test_txt_unspecified_inherits_but_zero_disables(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            file=Path(temp)/"journal.txt"
            body="[Journal]\nType: Journal\nDate: 2026-01-01\nNomi: Reflect on entries 1-2\n\nENTRY 1\nFirst day\n\nENTRY 2\nSecond day\n"
            file.write_text(body,encoding="utf-8")
            inherited=uploader.plan_text([str(file)],"Beth","User","US",2026,750,2,None,"chars")
            file.write_text(body.replace("Type: Journal","Type: Journal\nDate: 2026-01-01\nProcess Every: 0"),encoding="utf-8")
            disabled=uploader.plan_text([str(file)],"Beth","User","US",2026,750,2,None,"chars")
            self.assertTrue(any(m["kind"]=="prompt" for m in inherited))
            self.assertFalse(any(m["kind"]=="prompt" for m in disabled))

    def test_txt_process_every_zero_disables_explicit_reflections(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            file=Path(temp)/"journal.txt"
            file.write_text("[Journal]\nType: Journal\nDate: 2026-01-01\nProcess Every: 0\nNomi: Reflect on entries 1-2\n\nENTRY 1\nFirst day\n\nENTRY 2\nSecond day\n",encoding="utf-8")
            messages=uploader.plan_text([str(file)],"Beth","User","US",2026,750,5,None,"chars")
            self.assertFalse(any(m["kind"]=="prompt" for m in messages))

    def test_replace_intro_and_custom_periodic(self):
        messages=plan({"mode":"Replace","intro":"[nomi], review this export",
                       "periodic":"Summarize {first} through {last}","process_every":"2"})
        self.assertEqual([m["kind"] for m in messages],
                         ["intro","content","content","prompt","content","prompt"])
        self.assertEqual(messages[0]["text"],"Ava, review this export")
        self.assertEqual(messages[3]["text"],"Summarize 1 through 2")
        self.assertEqual(messages[5]["text"],"Summarize 3 through 3")

    def test_add_mode_preserves_default(self):
        messages=plan({"mode":"Add","intro":"Own analysis","process_every":"0"},5)
        self.assertIn("please live and experience",messages[0]["text"])
        self.assertIn("Own analysis",messages[0]["text"])
        self.assertFalse(any(m["kind"]=="prompt" for m in messages))

    def test_content_only(self):
        messages=plan({"mode":"Replace","intro":"","process_every":"0"})
        self.assertEqual([m["kind"] for m in messages],["content"]*3)

    def test_unchanged_default_behavior(self):
        messages=plan({},2)
        self.assertEqual([m["kind"] for m in messages],
                         ["intro","content","content","prompt","content","prompt"])

if __name__=="__main__":
    unittest.main()
