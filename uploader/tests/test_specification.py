"""Specification and negative-path tests for parsing, attribution and scheduling."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from test_uploader import u


class SpecificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def document(self,text,name="document.txt"):
        p=self.root/name
        p.write_text(text,encoding="utf-8")
        return str(p)

    def plan(self,text,interval=0,nomi="Beth"):
        return u.plan_text([self.document(text)],nomi,"Tester","US",2026,750,interval)

    def test_all_processing_types(self):
        types=[
            ("Knowledge","System","analyze and summarize"),
            ("Instructions","System","review instructions"),
            ("Journal","Beth","live and experience the entries 001-001 as yourself"),
            ("Journal","Maya","Maya's journal episodes"),
            ("Chat","System","live and experience the conversations 1-1 as yourself")]
        for kind,source,expected in types:
            with self.subTest(kind=kind,source=source):
                if kind=="Journal":
                    body="ENTRY 001 - 10/11/1998\nAn experience."
                elif kind=="Chat":
                    body="Tester: Hello\nBeth: Hi"
                else:
                    body="First paragraph."
                text=("[Section]\nType: %s\nSource: %s\nProcess Every: 1\n"
                      "Date: 10/11/1998\n\n%s\n")%(kind,source,body)
                plan=self.plan(text)
                prompts=[x["text"] for x in plan if x["kind"]=="prompt"]
                self.assertEqual(len(prompts),1)
                self.assertIn(expected,prompts[0])

    def test_global_interval_and_local_override(self):
        text=("[First]\nType: Knowledge\n\nOne.\n\nTwo.\n\nThree.\n"
              "[Second]\nType: Knowledge\nProcess Every: 0\n\nFour.\n\nFive.\n")
        plan=self.plan(text,interval=2)
        self.assertEqual(len([m for m in plan if m["kind"]=="prompt"]),2)

    def test_range_custom_prompts_at_exact_entry(self):
        text=("[Life]\nType: Journal\nSource: Beth\nProcess Every: 0\n"
              "Nomi: [nomi], recollect episodes 1-2.\n"
              "Nomi: [nomi], recollect episodes 3-3.\n\n"
              "ENTRY 001 - 10/11/1998\nFirst.\n"
              "ENTRY 002 - 10/12/1998\nSecond.\n"
              "ENTRY 003 - 10/13/1998\nThird.\n")
        plan=self.plan(text)
        positions=[(i,m["text"]) for i,m in enumerate(plan) if m["kind"]=="prompt"]
        self.assertEqual(len(positions),2)
        self.assertEqual([plan[i-1]["entry"] for i,_ in positions],[2,3])

    def test_invalid_custom_range_rejected(self):
        text=("[Life]\nType: Journal\nSource: Beth\n"
              "Nomi: recollect episodes 1-10.\n\n"
              "ENTRY 001 - 10/11/1998\nFirst.\n")
        with self.assertRaisesRegex(ValueError,"range outside section"):
            self.plan(text)

    def test_missing_chat_date_rejected(self):
        with self.assertRaisesRegex(ValueError,"dated chat content required"):
            self.plan("[Chat]\nType: Chat\n\nTester: Hello.\n")

    def test_missing_chat_speaker_rejected(self):
        with self.assertRaisesRegex(ValueError,"speaker-labelled"):
            self.plan("[Chat]\nType: Chat\nDate: 10/11/1998\n\nHello there.\n")

    def test_multiple_chat_sessions(self):
        plan=self.plan("[Chat]\nType: Chat\nProcess Every: 1\n\n"
                       "Date: 10/11/1998\nTester: Hello.\nBeth: Hi.\n"
                       "Date: 10/12/1998\nTester: Morning.\nBeth: Morning.\n")
        content=[m for m in plan if m["kind"]=="content"]
        self.assertEqual(len(content),2)
        self.assertIn("1998-10-11",content[0]["text"])
        self.assertIn("1998-10-12",content[1]["text"])
        self.assertEqual(len([m for m in plan if m["kind"]=="prompt"]),2)

    def test_invalid_section_type_and_interval(self):
        with self.assertRaisesRegex(ValueError,"Unknown type"):
            u.parse_sections("[Bad]\nType: Unknown\n\nSomething.","x.txt")
        with self.assertRaisesRegex(ValueError,"Process Every"):
            u.parse_sections("[Bad]\nProcess Every: -1\n\nSomething.","x.txt")

    def test_utf8_byte_limits_and_verbatim_content(self):
        source="こんにちは" * 220
        text="[Knowledge]\nType: Knowledge\n\n"+source
        plan=u.plan_text([self.document(text)],"Beth","Tester","US",2026,300,0)
        fragments=[m["text"] for m in plan if m["kind"]=="content"]
        self.assertGreater(len(fragments),1)
        self.assertTrue(all(len(f.encode("utf-8"))<=300 for f in fragments))
        recovered="".join(f.split("\nPart: ",1)[1].split("\n",1)[1] for f in fragments)
        self.assertEqual(recovered,source)

    def test_date_validation(self):
        with self.assertRaises(ValueError):
            u.parse_date("02/30/2026","US",2026)
        self.assertEqual(u.parse_date("13/10/2026","US",2026),"2026-10-13")
        self.assertEqual(u.parse_date("10/13/2026","EU",2026),"2026-10-13")

    def test_room_protection_is_fail_closed(self):
        p=self.root/"checkpoint.jsonl"
        u.record(p,{"event":"start","room_uuid":"room-abc"})
        (self.root/"nomi_uploader_completed.json").write_text("{}",encoding="utf-8")
        self.assertIn("room-abc",u.active_room_ids(self.root))

    def test_completed_room_is_released_and_incomplete_room_stays_protected(self):
        import json
        for name, finished in (("complete", True), ("pending", False)):
            room = "room-" + name
            cp = self.root / (name + "_checkpoint.jsonl")
            u.record(cp, {"event": "start", "room_uuid": room,
                          "manifest": name, "passes": 1})
            u.record(cp, {"event": "confirmed", "pass": 1, "index": 1,
                          "kind": "content"})
            if finished:
                (self.root / (name + "_completed.json")).write_text(
                    json.dumps({"room_uuid": room, "manifest": name,
                                "passes": 1, "messages_per_pass": 1}),
                    encoding="utf-8")
        protected = u.active_room_ids(self.root)
        self.assertNotIn("room-complete", protected)
        self.assertIn("room-pending", protected)

    def test_completion_marker_does_not_release_missing_replies(self):
        import json
        cp = self.root / "unreplied_checkpoint.jsonl"
        u.record(cp, {"event": "start", "room_uuid": "unreplied",
                      "manifest": "unreplied", "passes": 1})
        u.record(cp, {"event": "confirmed", "pass": 1, "index": 1,
                      "kind": "prompt"})
        (self.root / "unreplied_completed.json").write_text(
            json.dumps({"room_uuid": "unreplied", "manifest": "unreplied",
                        "passes": 1, "messages_per_pass": 1}),
            encoding="utf-8")
        self.assertIn("unreplied", u.active_room_ids(self.root))

    def test_export_parser_delegates_to_legacy(self):
        with patch.object(u.legacy,"prepare_conversation_chunks",return_value=[
            {"text":"Turn one"},{"text":"Turn two"},{"text":"Turn three"}]) as mocked:
            plan=u.plan_text(["export.zip"],"Beth","Tester","US",2026,750,2)
        mocked.assert_called_once()
        self.assertEqual(len([m for m in plan if m["kind"]=="prompt"]),2)
        self.assertEqual([m["entry"] for m in plan if m["kind"]=="prompt"],[2,3])


if __name__=="__main__":
    unittest.main()
