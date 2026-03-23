"""Tests for TodoFile load/save round-trip."""

import tempfile
import time
import unittest
from pathlib import Path

from todotxt_lib.task import Priority
from todotxt_lib.todo_file import TodoFile


class TestTodoFileLoad(unittest.TestCase):
    def test_load_nonexistent_file_gives_empty_list(self) -> None:
        f = TodoFile(Path("/nonexistent/path/todo.txt"))
        f.load()
        self.assertEqual(f.tasks, [])

    def test_load_parses_all_lines(self) -> None:
        content = (
            "(A) Thank Mom for the meatballs @phone\n"
            "(B) Schedule Goodwill pickup +GarageSale @phone\n"
            "Post signs around the neighborhood +GarageSale\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as fh:
            fh.write(content)
            path = Path(fh.name)
        try:
            f = TodoFile(path)
            f.load()
            self.assertEqual(len(f.tasks), 3)
            self.assertEqual(f.tasks[0].priority, Priority.A)
            self.assertEqual(f.tasks[1].priority, Priority.B)
            self.assertIsNone(f.tasks[2].priority)
        finally:
            path.unlink()

    def test_load_skips_blank_lines(self) -> None:
        content = "Task one\n\n\nTask two\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as fh:
            fh.write(content)
            path = Path(fh.name)
        try:
            f = TodoFile(path)
            f.load()
            self.assertEqual(len(f.tasks), 2)
        finally:
            path.unlink()


class TestTodoFileSave(unittest.TestCase):
    def test_save_and_reload_round_trip(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as fh:
            path = Path(fh.name)
        try:
            original_lines = [
                "(A) 2011-03-02 Call Mom",
                "(B) Schedule Goodwill pickup +GarageSale @phone",
                "x 2011-03-03 2011-03-01 Done task",
            ]
            f = TodoFile(path)
            f.load()
            from todotxt_lib.parser import parse_task

            f.tasks = [parse_task(line) for line in original_lines]
            f.save()

            f2 = TodoFile(path)
            f2.load()
            self.assertEqual(len(f2.tasks), 3)
            for task, expected_line in zip(f2.tasks, original_lines):
                self.assertEqual(task.raw, expected_line)
        finally:
            path.unlink()

    def test_save_empty_file(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as fh:
            path = Path(fh.name)
        try:
            f = TodoFile(path)
            f.tasks = []
            f.save()
            self.assertEqual(path.read_text(), "")
        finally:
            path.unlink()

    def test_save_ends_with_newline(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as fh:
            path = Path(fh.name)
        try:
            from todotxt_lib.parser import parse_task

            f = TodoFile(path)
            f.tasks = [parse_task("Call Mom")]
            f.save()
            self.assertTrue(path.read_text().endswith("\n"))
        finally:
            path.unlink()


class TestAtomicSave(unittest.TestCase):
    def test_save_no_leftover_temp_files(self) -> None:
        """Atomic save should not leave .tmp files behind."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "todo.txt"
            f = TodoFile(path)
            from todotxt_lib.parser import parse_task

            f.tasks = [parse_task("Task one")]
            f.save()
            remaining = list(Path(tmpdir).glob(".todo-*.tmp"))
            self.assertEqual(remaining, [])
            self.assertTrue(path.exists())

    def test_save_is_atomic_content_intact(self) -> None:
        """After save, file content matches in-memory tasks exactly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "todo.txt"
            f = TodoFile(path)
            from todotxt_lib.parser import parse_task

            f.tasks = [parse_task("(A) Important"), parse_task("Normal task")]
            f.save()
            content = path.read_text(encoding="utf-8")
            self.assertEqual(content, "(A) Important\nNormal task\n")


class TestExternalChangeDetection(unittest.TestCase):
    def test_no_changes_after_load(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as fh:
            fh.write("Task one\n")
            path = Path(fh.name)
        try:
            f = TodoFile(path)
            f.load()
            self.assertFalse(f.has_external_changes())
        finally:
            path.unlink()

    def test_no_changes_after_save(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "todo.txt"
            f = TodoFile(path)
            from todotxt_lib.parser import parse_task

            f.tasks = [parse_task("Task one")]
            f.save()
            self.assertFalse(f.has_external_changes())

    def test_detects_external_modification(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as fh:
            fh.write("Task one\n")
            path = Path(fh.name)
        try:
            f = TodoFile(path)
            f.load()
            self.assertFalse(f.has_external_changes())
            # Simulate external edit (ensure different mtime)
            time.sleep(0.05)
            path.write_text("Task one\nTask two\n", encoding="utf-8")
            self.assertTrue(f.has_external_changes())
        finally:
            path.unlink()

    def test_detects_external_deletion(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as fh:
            fh.write("Task one\n")
            path = Path(fh.name)
        try:
            f = TodoFile(path)
            f.load()
            path.unlink()
            self.assertTrue(f.has_external_changes())
        finally:
            if path.exists():
                path.unlink()

    def test_nonexistent_file_no_false_positive(self) -> None:
        f = TodoFile(Path("/nonexistent/todo.txt"))
        f.load()
        # File never existed — no external changes
        self.assertFalse(f.has_external_changes())

    def test_reload_clears_external_changes(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as fh:
            fh.write("Task one\n")
            path = Path(fh.name)
        try:
            f = TodoFile(path)
            f.load()
            time.sleep(0.05)
            path.write_text("Task one\nTask two\n", encoding="utf-8")
            self.assertTrue(f.has_external_changes())
            f.load()
            self.assertFalse(f.has_external_changes())
            self.assertEqual(len(f.tasks), 2)
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
