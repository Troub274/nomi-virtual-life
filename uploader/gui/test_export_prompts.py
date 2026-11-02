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


    def test_header_every_one_without_reflections(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/"book.txt"
            file.write_text("[Biography]\nType: Knowledge\n\n"+"A long autobiographical passage. "*80)
            messages=uploader.plan_text([str(file)],"Beth","User","US",2026,180,0,None,"chars",None,1,"Your autobiography:","")
            contents=[m["text"] for m in messages if m["kind"]=="content"]
            self.assertGreater(len(contents),1)
            self.assertTrue(all(x.startswith("Your autobiography:\n") for x in contents))
            self.assertTrue(all(len(x)<=180 for x in contents))
            self.assertFalse(any(m["kind"]=="prompt" for m in messages))

    def test_header_every_two_and_global_reply_prompt(self):
        with patch.object(uploader.legacy,"prepare_conversation_chunks",return_value=ROWS):
            result=uploader.plan_text([FILE],"Ava","User","US",2026,750,2,None,"chars",{FILE:{"mode":"Replace","intro":""}},2,"My biography","Revisit {first}-{last}")
        contents=[m["text"] for m in result if m["kind"]=="content"]
        self.assertEqual(contents,["one","My biography\ntwo","three"])
        self.assertEqual([m["text"] for m in result if m["kind"]=="prompt"],["Revisit 1-2","Revisit 3-3"])

    def test_section_header_zero_overrides_global(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/"book.txt"
            file.write_text("[Bio]\nType: Knowledge\nHeader Every: 0\nHeader Text: Different\nProcess Every: 0\n\nPassage")
            result=uploader.plan_text([str(file)],"Beth","User","US",2026,750,0,None,"chars",None,1,"Global","")
            content=[m["text"] for m in result if m["kind"]=="content"]
            self.assertEqual(len(content),1)
            self.assertNotIn("Global",content[0])
            self.assertNotIn("Different",content[0])


    def test_manual_restart_boundary_preserves_history_and_recalculates_state(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cp=Path(tmp)/"upload.jsonl"
            start={"event":"start","nomi_name":"Mary","nomi_uuid":"nomi","room_uuid":"room",
                   "passes":1,"messages_per_pass":4,"manifest":"old"}
            uploader.record(cp,start)
            for i in range(1,5):
                uploader.record(cp,{"event":"attempt","pass":1,"index":i})
                uploader.record(cp,{"event":"confirmed","pass":1,"index":i,"kind":"content"})
            revision=dict(start,messages_per_pass=6,manifest="changed")
            uploader.record(cp,{"event":"manual_restart","generation":2,"pass":1,"index":3,
                                "start":revision,"prefix_prompts":[]})
            active=uploader.active_records(cp)
            self.assertEqual(len(uploader.records(cp)),10)
            self.assertEqual(active[0]["messages_per_pass"],6)
            self.assertEqual({(e["pass"],e["index"]) for e in active if e["event"]=="confirmed"},
                             {(1,1),(1,2)})
            info=uploader.checkpoint_summary(cp)
            self.assertEqual(info["expected"],6)
            self.assertEqual(info["confirmed"],2)
            self.assertEqual(info["next"],(1,3))
            uploader.record(cp,{"event":"attempt","pass":1,"index":3})
            uploader.record(cp,{"event":"confirmed","pass":1,"index":3,"kind":"content"})
            self.assertEqual(uploader.checkpoint_summary(cp)["confirmed"],3)

    def test_second_manual_restart_supersedes_previous_generation(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cp=Path(tmp)/"checkpoint.jsonl"
            start={"event":"start","nomi_name":"Mary","nomi_uuid":"nomi","room_uuid":"room",
                   "passes":1,"messages_per_pass":5,"manifest":"old"}
            uploader.record(cp,start)
            first=dict(start,messages_per_pass=6,manifest="first")
            second=dict(start,messages_per_pass=8,manifest="second")
            uploader.record(cp,{"event":"manual_restart","generation":2,"pass":1,"index":4,
                                "start":first,"prefix_prompts":[]})
            uploader.record(cp,{"event":"confirmed","pass":1,"index":4,"kind":"content"})
            uploader.record(cp,{"event":"manual_restart","generation":3,"pass":1,"index":2,
                                "start":second,"prefix_prompts":[]})
            summary=uploader.checkpoint_summary(cp)
            self.assertEqual((summary["confirmed"],summary["expected"],summary["next"]),(1,8,(1,2)))


    def test_frozen_macos_tls_uses_certifi_ca_without_shell_exports(self):
        import ssl
        import sys
        from types import SimpleNamespace
        from unittest.mock import patch
        import legacy_v085
        known_context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        fake_certifi=SimpleNamespace(where=lambda:"/packaged/certifi/cacert.pem")
        with patch.object(legacy_v085.sys,"platform","darwin"), \
             patch.object(legacy_v085.sys,"frozen",True,create=True), \
             patch.dict(sys.modules,{"certifi":fake_certifi}), \
             patch("ssl.create_default_context",return_value=known_context) as factory, \
             patch.dict(legacy_v085.os.environ,{},clear=True):
            context=legacy_v085.api_ssl_context()
        factory.assert_called_once_with(cafile="/packaged/certifi/cacert.pem")
        self.assertIs(context,known_context)
        self.assertEqual(context.verify_mode,ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)


    def test_source_macos_cli_tls_uses_certifi_without_export(self):
        import ssl
        import sys
        from types import SimpleNamespace
        from unittest.mock import patch
        import legacy_v085
        fake_certifi=SimpleNamespace(where=lambda:"/bundled/ca.pem")
        with patch.object(legacy_v085.sys,"platform","darwin"), \
             patch.object(legacy_v085.sys,"frozen",False,create=True), \
             patch.dict(sys.modules,{"certifi":fake_certifi}), \
             patch("ssl.create_default_context") as factory, \
             patch.dict(legacy_v085.os.environ,{},clear=True):
            legacy_v085.api_ssl_context()
        factory.assert_called_once_with(cafile="/bundled/ca.pem")

    def test_macos_cli_explicit_ssl_ca_override(self):
        from unittest.mock import patch
        import legacy_v085
        with patch.object(legacy_v085.sys,"platform","darwin"), \
             patch("ssl.create_default_context") as factory, \
             patch.dict(legacy_v085.os.environ,{"SSL_CERT_FILE":"/private/trusted.pem"},clear=True):
            legacy_v085.api_ssl_context()
        factory.assert_called_once_with(cafile="/private/trusted.pem")

if __name__=="__main__":
    unittest.main()
