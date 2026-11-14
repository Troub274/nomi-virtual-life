import json
from pathlib import Path
import tempfile
import unittest

from test_uploader import u


class PromptPersonalizationTests(unittest.TestCase):
    def test_sample_matches_embedded_defaults_and_partial_override(self):
        sample = Path(u.__file__).with_name("prompts.example.json")
        self.assertEqual(json.loads(sample.read_text(encoding="utf-8")), u.BUILTIN_PROMPTS)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = root / "prompts.json"
            source = root / "facts.txt"
            source.write_text("[Facts]\nType: Knowledge\n\nOne fact.\n", encoding="utf-8")
            settings.write_text(json.dumps({"periodic": {"knowledge": "[nomi], reflect on {first}-{last}."}}), encoding="utf-8")
            saved = u.load_prompt_table(root)
            self.assertEqual(saved["opening"], u.BUILTIN_PROMPTS["opening"])
            settings.write_text("{}", encoding="utf-8")
            args = ([str(source)], "Beth", "", "US", 2026, 750, 1)
            plan = u.plan_text(*args, prompt_table=saved)
            self.assertEqual(plan[-1]["text"], "Beth, reflect on 1-1.")
            self.assertNotEqual(u.digest(plan), u.digest(u.plan_text(*args, prompt_table=u.load_prompt_table(root))))

    def test_invalid_periodic_placeholder_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "prompts.json").write_text('{"periodic":{"chat":"{unknown}"}}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Invalid prompt file"):
                u.load_prompt_table(root)
