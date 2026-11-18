"""Run the uploader, GUI-control, and local HTTP simulator regressions."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix="nomi-regressions-") as directory:
        with patch.dict(os.environ, {"LOCALAPPDATA": directory, "NOMI_API_KEY": ""}):
            suite = unittest.TestSuite()
            for name in ("uploader/tests", "uploader/gui", "simulator"):
                pattern = "test_export_prompts.py" if name == "uploader/gui" else "test_*.py"
                suite.addTests(unittest.TestLoader().discover(str(ROOT / name), pattern=pattern))
            result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
