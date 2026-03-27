"""Tests for TaskRef token parsing hardening."""

from __future__ import annotations

import unittest

from todotxt_lib.task import TaskRef


class TestTaskRefFromToken(unittest.TestCase):
    def test_round_trips_valid_tokens(self) -> None:
        ref = TaskRef("done.txt.d/task.txt", 3)

        parsed = TaskRef.from_token(ref.to_token())

        self.assertEqual(parsed, ref)

    def test_rejects_non_json_tokens(self) -> None:
        with self.assertRaises(ValueError):
            TaskRef.from_token("not json")

    def test_rejects_non_object_payloads(self) -> None:
        with self.assertRaises(ValueError):
            TaskRef.from_token("[]")

    def test_rejects_missing_fields(self) -> None:
        with self.assertRaises(ValueError):
            TaskRef.from_token('{"relative_path":"task.txt"}')

    def test_rejects_negative_line_index(self) -> None:
        with self.assertRaises(ValueError):
            TaskRef.from_token('{"relative_path":"task.txt","line_index":-1}')

    def test_rejects_path_traversal(self) -> None:
        with self.assertRaises(ValueError):
            TaskRef.from_token('{"relative_path":"../outside.txt","line_index":0}')


if __name__ == "__main__":
    unittest.main()
