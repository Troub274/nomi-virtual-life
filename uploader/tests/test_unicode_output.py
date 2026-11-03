"""Unicode regression: source CLI and GUI pipe must survive Windows code pages."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
SAMPLE='Citation \ue203 — שלום — café — 🙂'

class UnicodeOutputTests(unittest.TestCase):
    def fixture(self,folder):
        path=Path(folder)/'sample_data.json'
        path.write_text(json.dumps({'nomi':{'name':'Test','chat':[{'date':'2025-01-01T00:00:00Z','sender':'User','message':SAMPLE}]}},ensure_ascii=False),encoding='utf-8')
        return path

    def test_cli_dry_run_under_cp1252_preserves_unicode(self):
        with tempfile.TemporaryDirectory() as folder:
            source=self.fixture(folder)
            env={**os.environ,'PYTHONIOENCODING':'cp1252:strict','PYTHONUTF8':'0'}
            result=subprocess.run([sys.executable,str(ROOT/'nomi-uploader.py'),str(source),'--dry-run','--nomi','Test'],cwd=folder,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr.decode('utf-8',errors='replace'))
            self.assertIn(SAMPLE,result.stdout.decode('utf-8'))
            self.assertFalse((Path(folder)/'nomi_uploader_checkpoint.jsonl').exists())

    def test_gui_pipe_preserves_unicode_with_legacy_parent_encoding(self):
        with tempfile.TemporaryDirectory() as folder:
            source=self.fixture(folder)
            with patch.dict(os.environ,{'LOCALAPPDATA':folder}):
                spec=importlib.util.spec_from_file_location('gui_unicode_test',ROOT/'gui/app.py')
                gui=importlib.util.module_from_spec(spec);spec.loader.exec_module(gui)
            import legacy_v085
            api=gui.API.__new__(gui.API)
            api.proc=None;api.lines=[];api.lock=threading.Lock();api.project={'nomi':'Test'}
            with patch.object(gui,'DATA',Path(folder)),patch.object(legacy_v085,'resolved_api_key',return_value=''),patch.dict(os.environ,{'PYTHONIOENCODING':'cp1252:strict','PYTHONUTF8':'0'}):
                api._run([str(source),'--dry-run','--nomi','Test'])
                self.assertEqual(api.proc.wait(timeout=30),0)
                deadline=time.monotonic()+5
                while SAMPLE not in '\n'.join(api.lines) and time.monotonic()<deadline:time.sleep(.01)
                self.assertIn(SAMPLE,'\n'.join(api.lines))
                api.proc.stdout.close()

if __name__=='__main__':unittest.main()
