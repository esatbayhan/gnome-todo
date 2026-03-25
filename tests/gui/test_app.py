"""Tests for the GTK4 GUI application."""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from todotxt_gui import __version__
from todotxt_gui._core import done_file_path, sort_key, todo_file_path
from todotxt_lib import parse_task


class TestVersionMetadata(unittest.TestCase):
    def test_runtime_version_matches_release(self) -> None:
        self.assertEqual(__version__, "0.2.1")


class TestFilePaths(unittest.TestCase):
    @patch("todotxt_gui._core.get_todo_dir", return_value=None)
    def test_default_todo_path(self, _mock: object) -> None:
        skip = {"TODO_FILE", "TODO_DIR"}
        env = {k: v for k, v in os.environ.items() if k not in skip}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(todo_file_path(), Path.home() / "todo.txt")

    def test_todo_file_env_overrides(self) -> None:
        with patch.dict(os.environ, {"TODO_FILE": "/custom/my.txt"}, clear=False):
            self.assertEqual(todo_file_path(), Path("/custom/my.txt"))

    @patch("todotxt_gui._core.get_todo_dir", return_value=None)
    def test_todo_dir_env_fallback(self, _mock: object) -> None:
        skip = {"TODO_FILE", "TODO_DIR"}
        env = {k: v for k, v in os.environ.items() if k not in skip}
        env["TODO_DIR"] = "/custom/dir"
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(todo_file_path(), Path("/custom/dir/todo.txt"))

    def test_todo_file_takes_priority_over_dir(self) -> None:
        with patch.dict(
            os.environ,
            {"TODO_FILE": "/explicit/todo.txt", "TODO_DIR": "/dir"},
            clear=False,
        ):
            self.assertEqual(todo_file_path(), Path("/explicit/todo.txt"))

    @patch("todotxt_gui._core.get_todo_dir", return_value=None)
    def test_default_done_path(self, _mock: object) -> None:
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in {"TODO_DONE_FILE", "TODO_DIR"}
        }
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(done_file_path(), Path.home() / "done.txt")

    def test_done_file_env_overrides(self) -> None:
        env = {"TODO_DONE_FILE": "/custom/done.txt"}
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(done_file_path(), Path("/custom/done.txt"))

    @patch("todotxt_gui._core.get_todo_dir", return_value=None)
    def test_done_dir_env_fallback(self, _mock: object) -> None:
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in {"TODO_DONE_FILE", "TODO_DIR"}
        }
        env["TODO_DIR"] = "/custom/dir"
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(done_file_path(), Path("/custom/dir/done.txt"))


class TestSortKey(unittest.TestCase):
    def test_active_before_done(self) -> None:
        active = parse_task("Buy milk")
        done = parse_task("x 2025-01-01 Done task")
        self.assertLess(sort_key(active), sort_key(done))

    def test_priority_a_before_b(self) -> None:
        a = parse_task("(A) High priority")
        b = parse_task("(B) Lower priority")
        self.assertLess(sort_key(a), sort_key(b))

    def test_unprioritized_after_any_priority(self) -> None:
        z = parse_task("(Z) Last priority letter")
        none_ = parse_task("No priority at all")
        self.assertLess(sort_key(z), sort_key(none_))

    def test_alphabetical_within_same_priority(self) -> None:
        apple = parse_task("Apple task")
        banana = parse_task("Banana task")
        self.assertLess(sort_key(apple), sort_key(banana))

    def test_case_insensitive_alphabetical(self) -> None:
        lower = parse_task("apple")
        upper = parse_task("Banana")
        self.assertLess(sort_key(lower), sort_key(upper))

    def test_done_tasks_sort_after_active(self) -> None:
        active = parse_task("(A) Very important")
        done = parse_task("x 2025-01-01 Trivial done task")
        self.assertGreater(sort_key(done), sort_key(active))


if __name__ == "__main__":
    unittest.main()
