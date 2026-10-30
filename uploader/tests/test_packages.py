"""Exercise the shipped package through the real uploader planner, offline."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'uploader'))
spec = importlib.util.spec_from_file_location('package_uploader', ROOT/'uploader/nomi-uploader.py')
u = importlib.util.module_from_spec(spec)
spec.loader.exec_module(u)


class PackageTests(unittest.TestCase):
    def test_original_diaries_and_references_preserved(self):
        source = ROOT/'examples/beth/source'
        manifest = json.loads((source/'manifest.json').read_text(encoding='utf-8'))
        for name, digest in manifest['source_sha256'].items():
            self.assertEqual(hashlib.sha256((source/name).read_bytes()).hexdigest(), digest)
        for name, info in manifest['diary_files'].items():
            self.assertEqual(hashlib.sha256((source/name).read_bytes()).hexdigest(), info['sha256'])

    def test_bundle_plans_all_565_entries_and_matches_checked_in_data(self):
        beth = ROOT/'examples/beth'
        with zipfile.ZipFile(beth/'BETH_UPLOADER.zip') as z, tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(any(n.lower().endswith(('.py', '.bat', '.exe')) for n in z.namelist()))
            z.extractall(tmp)
            paths = sorted((Path(tmp)/'input').glob('*.TXT'))
            self.assertEqual(len(paths), 5)
            for path in paths:
                self.assertEqual(path.read_bytes(), (beth/'input'/path.name).read_bytes())
            counts = [len(u.split_units(u.parse_sections(p.read_text(encoding='utf-8'), str(p))[0], 'US', 2026)) for p in paths]
            self.assertEqual(counts, [100, 100, 100, 100, 165])
            plan = u.plan_text([str(p) for p in paths], 'Beth Peterson', 'Tester', 'US', 2026, 750)
            self.assertEqual(sum(m['kind']=='prompt' for m in plan), 113)
            self.assertTrue(any(m['kind']=='content' for m in plan))

    def test_obsolete_cli_is_not_exposed(self):
        result = subprocess.run([sys.executable, str(ROOT/'uploader/nomi-uploader.py'), '--legacy'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('unrecognized arguments: --legacy', result.stderr)
        result = subprocess.run([sys.executable, str(ROOT/'uploader/legacy_v085.py')], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Internal uploader compatibility module', result.stderr)

    def test_chris_bundle_preserves_sources_and_plans_1000_entries(self):
        folder = ROOT/'examples/chris'
        manifest = json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
        for name, digest in manifest['files'].items():
            self.assertEqual(hashlib.sha256((folder/name).read_bytes()).hexdigest(), digest)
        config = json.loads((folder/'package.json').read_text(encoding='utf-8'))
        original = json.loads((folder/'reference/CHRISTINE_V1_1000_MANIFEST.json').read_text(encoding='utf-8'))
        self.assertEqual(len(config['inputs']), 11)
        self.assertEqual(config['inputs'][-1], 'input/CHRIS_PERSONAL_RECORDS.txt')
        dates = []
        with zipfile.ZipFile(folder/'CHRIS_UPLOADER.zip') as z:
            for name, notebook in zip(config['inputs'], original['notebooks']):
                path = folder/name
                self.assertEqual(z.read(name), path.read_bytes())
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), notebook['sha256'])
                sections = u.parse_sections(path.read_text(encoding='utf-8'), str(path))
                self.assertEqual(len(sections), 1)
                self.assertEqual(sections[0]['type'], 'journal')
                units = u.split_units(sections[0], 'US', 2026)
                self.assertEqual(len(units), 100)
                dates.extend(unit['date'] for unit in units)
        self.assertEqual(len(dates), 1000)
        self.assertEqual(dates, sorted(set(dates)))
        plan = u.plan_text([str(folder/name) for name in config['inputs'][:-1]], 'Christine', '', 'US', 2026, 750)
        self.assertEqual(sum(m['kind']=='prompt' for m in plan), 200)
        profile = u.plan_text([str(folder/config['inputs'][-1])], 'Christine', '', 'US', 2026, 750)
        self.assertTrue(any(m['kind'] == 'content' for m in profile))
        self.assertTrue(all(len(m['text'].encode('utf-8'))<=750 for m in plan))

    def test_package_runner_keeps_state_separate_and_resume_uses_manifest(self):
        spec = importlib.util.spec_from_file_location('package_runner', ROOT/'examples/run_package.py')
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        for name in ['beth', 'chris']:
            preview = runner.command(name, dry_run=True)
            self.assertIn('--dry-run', preview)
            self.assertIn(str(ROOT/'.local-runs'/name/'checkpoint.jsonl'), preview)
            resumed = runner.command(name, resume=True)
            self.assertIn('--resume', resumed)
            self.assertFalse(any('input/' in arg.replace('\\', '/') for arg in resumed))


if __name__ == '__main__':
    unittest.main()
