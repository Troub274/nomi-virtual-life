"""Regression tests for existing-room reuse and one-step yes confirmation.

All API methods and user input are mocked. No rooms are created or deleted.
"""
import contextlib
import io
import unittest
from unittest.mock import patch

from test_uploader import u


class RoomManagerRegressionTests(unittest.TestCase):
    def setUp(self):
        self.nomi = {"name": "Christine", "uuid": "nomi-christine"}
        self.room = {
            "uuid": "existing-christine-room", "name": "REHYDRATE::Christine::sample",
            "nomiUuids": ["nomi-christine"], "status": "Default",
        }

    def test_room_reuse_is_default(self):
        with patch.object(u.legacy, "list_rooms", return_value=[self.room]), \
             patch.object(u.legacy, "get_room", return_value=self.room), \
             patch.object(u, "active_room_ids", return_value=set()), \
             patch.object(u, "create_upload_room", side_effect=AssertionError("new room attempted")), \
             patch("builtins.input", return_value=""), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(u.select_or_create_room(self.nomi), self.room["uuid"])

    def test_explicit_create_new_room(self):
        with patch.object(u.legacy, "list_rooms", return_value=[self.room]), \
             patch.object(u, "active_room_ids", return_value=set()), \
             patch.object(u, "create_upload_room", return_value="new-room") as creator, \
             patch("builtins.input", return_value="2"), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(u.select_or_create_room(self.nomi), "new-room")
            creator.assert_called_once_with(self.nomi)

    def test_protected_existing_room_does_not_default_to_new(self):
        with patch.object(u.legacy, "list_rooms", return_value=[self.room]), \
             patch.object(u, "active_room_ids", return_value={self.room["uuid"]}), \
             patch.object(u, "create_upload_room", side_effect=AssertionError("should not create")):
            with self.assertRaisesRegex(RuntimeError, "protected or unavailable"):
                u.select_or_create_room(self.nomi)

    def test_no_existing_room_creates_one(self):
        with patch.object(u.legacy, "list_rooms", return_value=[]), \
             patch.object(u, "active_room_ids", return_value=set()), \
             patch.object(u, "create_upload_room", return_value="new-room") as creator, \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(u.select_or_create_room(self.nomi), "new-room")
            creator.assert_called_once()

    def run_deletion(self, response, protected=None, choice="ALL"):
        rooms = [
            {"uuid": "room-one", "name": "REHYDRATE::Beth", "status": "Default"},
            {"uuid": "room-two", "name": "REHYDRATE::Christine", "status": "Default"},
        ]
        protected = set(protected or [])
        inputs = iter(["", "n", "", choice, response])
        with patch.object(u, "room_management", return_value=(rooms, protected)), \
             patch.object(u.legacy, "delete_room") as delete, \
             patch("builtins.input", side_effect=lambda *args: next(inputs)), \
             contextlib.redirect_stdout(io.StringIO()):
            u.utilities()
        return [call.args[0] for call in delete.call_args_list]

    def test_yes_variants_bulk(self):
        for response in ("y", "Y", "yes", "YES", "YeS", " yes "):
            with self.subTest(response=response):
                self.assertEqual(self.run_deletion(response), ["room-one", "room-two"])

    def test_no_and_unrecognized_cancel(self):
        for response in ("", "n", "NO", "DELETE 2", "yes please"):
            with self.subTest(response=response):
                self.assertEqual(self.run_deletion(response), [])

    def test_protected_room_is_never_deleted(self):
        self.assertEqual(self.run_deletion("y", {"room-one"}), ["room-two"])

    def test_single_room_uses_same_one_step_confirmation(self):
        self.assertEqual(self.run_deletion("yes", choice="2"), ["room-two"])


if __name__ == "__main__":
    unittest.main()
