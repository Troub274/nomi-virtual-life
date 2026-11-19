"""Reply destination controls and package forwarding, without credentials."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReplyDestinationControlsTests(unittest.TestCase):
    def test_desktop_forwards_choice_and_older_settings_default_to_room(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"LOCALAPPDATA": tmp}):
            app = load_module("reply_destination_gui", ROOT / "uploader/gui/app.py")
            api = app.API()
            api.project.update(queue=[], nomi_uuid="nomi", room_uuid="room")
            source = Path(tmp) / "biography.txt"
            source.write_text("A biography", encoding="utf-8")
            with patch.object(api, "_paths", return_value=[str(source)]), \
                 patch.object(api, "save"), patch.object(api, "_run", return_value=True) as run:
                for destination in ("room", "private", None):
                    if destination is None:
                        api.project.pop("reply_destination", None)
                    else:
                        api.project["reply_destination"] = destination
                    self.assertTrue(api.begin())
                    args = run.call_args.args[0]
                    self.assertEqual(args[args.index("--reply-destination") + 1], destination or "room")
                api.project["reply_destination"] = "invalid"
                run.reset_mock()
                with self.assertRaises(ValueError):
                    api.begin()
                run.assert_not_called()

    def test_package_forwards_private_for_new_runs_and_preserves_resume(self):
        runner = load_module("reply_destination_packages", ROOT / "examples/run_package.py")
        for package in runner.PACKAGES:
            args = runner.command(package, dry_run=True, reply_destination="private")
            self.assertEqual(args[args.index("--reply-destination") + 1], "private")
            resumed = runner.command(package, resume=True, reply_destination="room")
            self.assertIn("--resume", resumed)
            self.assertNotIn("--reply-destination", resumed)
