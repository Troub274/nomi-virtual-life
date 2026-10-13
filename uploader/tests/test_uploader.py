import importlib.util
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("nomi_uploader", ROOT / "nomi-uploader.py")
u = importlib.util.module_from_spec(spec)
spec.loader.exec_module(u)

class UploaderTests(unittest.TestCase):
    def test_dates(self):
        self.assertEqual(u.parse_date("9/21/95", "US", 2026), "1995-09-21")
        self.assertEqual(u.parse_date("21/9/1995", "EU", 2026), "1995-09-21")
        self.assertEqual(u.parse_date("9/21", "US", 2026), "2026-09-21")
        self.assertEqual(u.parse_date("2026-09-21", "EU", 2025), "2026-09-21")
    def test_sections(self):
        sections = u.parse_sections("[Facts]\nType: Knowledge\nSource: Sam\n\nA fact.\n[Rules]\nType: Instructions\n\nBe kind.", "test.txt")
        self.assertEqual(len(sections), 2)
        self.assertEqual(sections[0]["source"], "Sam")
        self.assertEqual(sections[1]["type"], "instructions")
    def test_missing_journal_date(self):
        section = u.parse_sections("[Life]\nType: Journal\n\nENTRY 001 - No date\nI was there.", "x.txt")[0]
        with self.assertRaises(ValueError):
            u.split_units(section, "US", 2026)
    def test_dated_journal(self):
        section = u.parse_sections("[Life]\nType: Journal\n\nENTRY 001 - 9/21/95\nI remember.\nENTRY 002 - 9/22/95\nNext day.", "x.txt")[0]
        units = u.split_units(section, "US", 2026)
        self.assertEqual(len(units), 2)
        self.assertEqual(units[0]["date"], "1995-09-21")
    def test_chat(self):
        section = u.parse_sections("[Talk]\nType: Chat\nDate: 10/13/2026\n\nBeth: Hello\nSam: Hi", "x.txt")[0]
        self.assertEqual(len(u.split_units(section, "US", 2026)), 1)
    def test_beth_diary_100_entries(self):
        fixture = ROOT / "tests" / "fixtures" / "beth_diary_v1_test.txt"
        sections = u.parse_sections(fixture.read_text(encoding="utf-8"), str(fixture))
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0]["source"], "Beth Peterson")
        units = u.split_units(sections[0], "US", 2026)
        self.assertEqual(len(units), 100)
        self.assertEqual(units[0]["date"], "1998-10-11")
        self.assertEqual(units[-1]["date"], "2005-02-06")
        messages = u.plan_text([str(fixture)], "Beth Peterson", "", "US", 2026, 750)
        prompts = [m for m in messages if m["kind"] == "prompt"]
        self.assertEqual(len(prompts), 4)
        self.assertTrue(any("episodes 76-100" in p["text"] for p in prompts))
    def test_legacy(self):
        self.assertTrue(callable(u.legacy.main))
        self.assertTrue(callable(u.legacy.prepare_conversation_chunks))

if __name__ == "__main__":
    unittest.main()
