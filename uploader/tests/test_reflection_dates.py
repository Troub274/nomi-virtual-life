"""Source dates in reflection prompts without changing saved-plan resumes."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from test_uploader import u


class ReflectionDateTests(unittest.TestCase):
    def test_export_batch_uses_source_date_range(self):
        rows = [{"text":"First", "source_date":"2025-01-02T10:00:00Z"},
                {"text":"Second", "source_date":"2025-01-03T10:00:00Z"},
                {"text":"Third", "source_date":"2025-01-05T10:00:00Z"}]
        with patch.object(u.legacy, "prepare_conversation_chunks", return_value=rows):
            dated = u.plan_text(["example.json"], "Ava", "", "US", 2026, 750, 2,
                                chunk_mode="chars", include_prompt_dates=True)
            legacy = u.plan_text(["example.json"], "Ava", "", "US", 2026, 750, 2,
                                 chunk_mode="chars")
        prompts = [m["text"] for m in dated if m["kind"]=="prompt"]
        self.assertIn("Memory dates: 2025-01-02 to 2025-01-03", prompts[0])
        self.assertIn("Memory date: 2025-01-05", prompts[1])
        self.assertTrue(all("Memory date" not in m["text"] for m in legacy))

    def test_missing_export_dates_do_not_invent_a_date(self):
        with patch.object(u.legacy, "prepare_conversation_chunks", return_value=[
                {"text":"First", "source_date":""}, {"text":"Second", "source_date":"unknown"}]):
            plan = u.plan_text(["example.json"], "Ava", "", "US", 2026, 750, 2,
                               chunk_mode="chars", include_prompt_dates=True)
        self.assertTrue(all("Memory date" not in m["text"] for m in plan))

    def test_journal_batch_uses_entry_dates(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/"journal.txt"
            source.write_text("[Diary]\nType: Journal\nSource: Ava\n\n"
                              "ENTRY 1 - 2025-01-02\nFirst day.\n\n"
                              "ENTRY 2 - 2025-01-03\nSecond day.\n", encoding="utf-8")
            plan = u.plan_text([str(source)], "Ava", "", "US", 2026, 750, 2,
                               chunk_mode="chars", include_prompt_dates=True)
        prompts = [m["text"] for m in plan if m["kind"]=="prompt"]
        self.assertEqual(len(prompts), 1)
        self.assertIn("Memory dates: 2025-01-02 to 2025-01-03", prompts[0])
