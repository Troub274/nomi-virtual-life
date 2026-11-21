"""File fields, sidecar headers, Settings defaults, and actual upload plans agree."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_uploader import u

spec=importlib.util.spec_from_file_location("file_header_gui",Path(u.__file__).parent/"gui/app.py")
gui=importlib.util.module_from_spec(spec)
spec.loader.exec_module(gui)


class FileHeaderTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.addCleanup(patch.stopall)
        patch.object(gui,"DATA",self.root).start()
        patch.object(gui,"CONFIG",self.root/"settings.json").start()
        self.api=gui.API()
        self.api.project={"nomi":"Ava","process":10,"header_every":0,"queue":[]}
        self.source=self.root/"facts.txt"
        self.body="First information paragraph.\n\nSecond information paragraph.\n"
        self.source.write_text(self.body,encoding="utf-8")

    def item(self):
        fields=self.api.inspect_file(str(self.source))["header"]
        fields.update(headerPrompt="[nomi], custom introduction.\nA second line.",
                      replyPrompt="[nomi], custom reply {first}-{last}.\nUse [source].",
                      source="Steve",date="2026-11-21",process=1,headerEvery=1)
        return {"path":str(self.source),"fields":fields}

    def test_virtual_header_drives_plan_and_sample_without_writing_source_or_sidecar(self):
        item=self.item()
        sample=self.api.file_sample(item)
        self.assertIn("Header Prompt: [nomi], custom introduction.\nHeader Prompt: A second line.",sample)
        self.assertTrue(sample.endswith(self.body))
        directory=self.root/"prepared"
        directory.mkdir()
        paths=self.api._paths(directory,[item])
        plan=u.plan_text(paths,"Ava","Steve","US",2026,750,999,chunk_mode="chars")
        self.assertIn("Ava, custom introduction.\nA second line.",plan[0]["text"])
        content=[m for m in plan if m["kind"]=="content"]
        replies=[m for m in plan if m["kind"]=="prompt"]
        self.assertTrue(content[0]["text"].startswith("Ava, custom introduction."))
        self.assertEqual(len(replies),2)
        self.assertIn("Ava, custom reply 1-1.\nUse Steve.",replies[0]["text"])
        self.assertEqual(self.source.read_text(encoding="utf-8"),self.body)
        self.assertFalse(Path(str(self.source)+".upldhdr").exists())

    def test_saved_sidecar_and_project_restore_custom_fields_and_zero_counts(self):
        item=self.item()
        item["fields"].update(type="Instructions",headerEvery=0,process=0)
        sidecar=Path(self.api.save_file_header(item))
        self.assertIn("Type: Instructions",sidecar.read_text(encoding="utf-8"))
        restored=self.api.inspect_file(str(self.source))["header"]
        for prop in ("type","headerPrompt","replyPrompt","source","date","process","headerEvery"):
            self.assertEqual(str(restored[prop]),str(item["fields"][prop]))
        self.api.project["queue"]=[item]
        self.api.save(self.api.project)
        reopened=gui.API()
        self.assertEqual(reopened.project["queue"][0]["fields"],item["fields"])
        self.assertEqual(self.source.read_text(encoding="utf-8"),self.body)

    def test_embedded_header_populates_fields_and_roundtrips_multiline_prompts(self):
        item=self.item()
        self.source.write_text(self.api._header_text(self.source,item["fields"])+"\n\n"+self.body,encoding="utf-8")
        fields=self.api.inspect_file(str(self.source))["header"]
        self.assertEqual(fields["headerPrompt"],item["fields"]["headerPrompt"])
        self.assertEqual(fields["replyPrompt"],item["fields"]["replyPrompt"])
        self.assertEqual(self.api._inspect_file(str(self.source))["preview"],self.body)

    def test_settings_persist_reset_to_builtins_and_reject_invalid_without_losing_saved(self):
        table=copy.deepcopy(u.BUILTIN_PROMPTS)
        table["opening"]["chat"]="Custom chat introduction"
        self.api.save_prompt_defaults(table)
        self.assertEqual(gui.API().prompt_defaults()["opening"]["chat"],"Custom chat introduction")
        table["periodic"]["chat"]="Invalid {unknown}"
        with self.assertRaises(ValueError):
            self.api.save_prompt_defaults(table)
        self.assertEqual(self.api.prompt_defaults()["opening"]["chat"],"Custom chat introduction")
        self.assertEqual(self.api.save_prompt_defaults(reset=True),u.BUILTIN_PROMPTS)

    def test_counts_are_limited_and_existing_header_beats_defaults(self):
        self.source.write_text("[Original]\nType: Chat\nSource: Ava\nDate: 2026-11-21\nHeader Prompt: File opening\nReply Prompt: File reply\nProcess Every: 0\nHeader Every: 0\n\nAva: Hello\n",encoding="utf-8")
        fields=self.api.inspect_file(str(self.source))["header"]
        self.assertEqual(fields["headerPrompt"],"File opening")
        self.assertEqual(fields["replyPrompt"],"File reply")
        for value in (-1,1001,"1.5",""):
            with self.assertRaises(ValueError):
                self.api._header_text(self.source,dict(fields,process=value))
        with self.assertRaisesRegex(ValueError,"reply prompt"):
            self.api._header_text(self.source,dict(fields,process=1,replyPrompt=""))
        with self.assertRaisesRegex(ValueError,"header prompt"):
            self.api._header_text(self.source,dict(fields,headerEvery=1,headerPrompt=""))

    def test_docx_and_exports_use_same_virtual_fields(self):
        from docx import Document
        source=self.root/"notes.docx"
        document=Document()
        document.add_paragraph("A Word paragraph.")
        document.save(source)
        fields=self.api.inspect_file(str(source))["header"]
        fields.update(headerPrompt="Word opening",replyPrompt="Word reply",process=0,headerEvery=0)
        directory=self.root/"prepared"
        directory.mkdir()
        paths=self.api._paths(directory,[{"path":str(source),"fields":fields}])
        self.assertIn("Header Prompt: Word opening",Path(paths[0]).read_text(encoding="utf-8"))
        item=self.item()
        item["path"]=str(self.root/"export.json")
        item["fields"]["type"]="Instructions"
        options=self.api._export_options([item])
        with patch.object(u.legacy,"prepare_conversation_chunks",return_value=[{"text":"Export text"}]):
            plan=u.plan_text([item["path"]],"Ava","Steve","US",2026,750,0,chunk_mode="chars",export_options=options)
        self.assertIn("custom introduction",plan[0]["text"])
        self.assertIn("Use Steve.",plan[-1]["text"])
