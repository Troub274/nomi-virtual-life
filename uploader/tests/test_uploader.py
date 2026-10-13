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
    def test_beth_github_archive_converter(self):
        import importlib.util
        import tempfile
        import zipfile
        script = ROOT.parent / "examples" / "beth" / "prepare_v1.py"
        spec = importlib.util.spec_from_file_location("beth_prepare", script)
        prep = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(prep)
        with tempfile.TemporaryDirectory() as folder:
            directory = pathlib.Path(folder)
            archive = directory / "sample.zip"
            with zipfile.ZipFile(archive, "w") as z:
                for k in range(1, 6):
                    content = ("ENTRY %03d — October 11, 1998\n"
                               "I remembered the day exactly.\n") % k
                    z.writestr("BETH%02d.TXT" % k, content)
            report = prep.prepare(archive, directory / "converted",
                                  reflection_every=5, verify_archive=False)
            self.assertEqual(len(report["files"]), 5)
            self.assertEqual(sum(x["entry_count"] for x in report["files"]), 5)
            first = directory / "converted" / "BETH01_V1.TXT"
            self.assertIn("Type: Journal", first.read_text())
            self.assertIn("I remembered the day exactly.", first.read_text())
            plan = u.plan_text([str(first)], "Beth Peterson", "", "US", 2026, 750)
            self.assertEqual(sum(m["kind"] == "prompt" for m in plan), 1)
    def test_processing_by_source_and_interval(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p=pathlib.Path(tmp)/"source.txt"
            p.write_text(
                "[Beth memories]\nType: Journal\nSource: Beth\nProcess Every: 2\n\n"
                "ENTRY 001 - 10/11/1998\nI turned ten.\n"
                "ENTRY 002 - 10/12/1998\nI went home.\n"
                "ENTRY 003 - 10/13/1998\nI met Maya.\n"
                "[Other person's memories]\nType: Journal\nSource: Maya\nProcess Every: 1\n\n"
                "ENTRY 001 - 10/11/1998\nMaya remembered school.\n"
                "[Facts]\nType: Knowledge\nSource: System\nProcess Every: 1\n\n"
                "The Earth orbits the Sun.\n", encoding="utf-8")
            messages=u.plan_text([str(p)],"Beth","Yehoshua","US",2026,750,0)
            prompts=[m["text"] for m in messages if m["kind"]=="prompt"]
            self.assertEqual(len(prompts),4)
            self.assertTrue(any("your own journal episodes 1-2" in x for x in prompts))
            self.assertTrue(any("your own journal episodes 3-3" in x for x in prompts))
            self.assertTrue(any("Maya's journal episodes" in x for x in prompts))
            self.assertTrue(any("analyze and summarize" in x for x in prompts))

    def test_custom_prompt_and_processing_override(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p=pathlib.Path(tmp)/"source.txt"
            p.write_text(
                "[One]\nType: Knowledge\nProcess Every: 0\n"
                "Nomi Mode: Replace\nNomi: [nomi], test [source].\n\n"
                "A factual statement.\n",encoding="utf-8")
            messages=u.plan_text([str(p)],"Beth","User","US",2026,750,1)
            prompts=[m for m in messages if m["kind"]=="prompt"]
            self.assertEqual(len(prompts),1)
            self.assertEqual(prompts[0]["text"],"Beth, test System.")
            self.assertNotIn("learn, summarize",messages[0]["text"])

    def test_export_chat_processing(self):
        from unittest.mock import patch
        with patch.object(u.legacy,"prepare_conversation_chunks",return_value=[
                {"text":"Historical conversation transcript | 2026-01-01 | Beth: Hello"},
                {"text":"Historical conversation transcript | 2026-01-02 | User: Hi"}]):
            messages=u.plan_text(["chat.json"],"Beth","User","US",2026,750,1)
        self.assertEqual([m["kind"] for m in messages],
                         ["intro","content","prompt","content","prompt"])
        self.assertTrue(all("conversation episodes" in m["text"]
                            for m in messages if m["kind"]=="prompt"))

    def test_room_filter_and_protection(self):
        import tempfile
        import json
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            cp=pathlib.Path(tmp)/"nomi_uploader_checkpoint.jsonl"
            cp.write_text(json.dumps({"event":"start","room_uuid":"protected"})+"\\n",
                          encoding="utf-8")
            with patch.object(u.legacy,"list_rooms",return_value=[
                    {"uuid":"protected","name":"UPLOADER::Beth","status":"Ready"},
                    {"uuid":"other","name":"UPLOADER::Maya","status":"Failed"}]):
                rooms,protected=u.room_management(abandoned=True,checkpoint_dir=tmp)
            self.assertEqual([r["uuid"] for r in rooms],["other"])
            self.assertIn("protected",protected)

    def test_legacy(self):
        self.assertTrue(callable(u.legacy.main))
        self.assertTrue(callable(u.legacy.prepare_conversation_chunks))

if __name__ == "__main__":
    unittest.main()
