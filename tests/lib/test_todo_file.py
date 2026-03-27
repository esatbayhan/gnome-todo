"""Tests for TodoDirectory load/save style behavior."""

from __future__ import annotations

import tempfile
import time
import unittest
from datetime import date
from pathlib import Path

from todotxt_lib.task import Priority, TaskRef
from todotxt_lib.todo_directory import TodoDirectory


class TodoDirectoryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name) / "todo.txt.d"
        self.root.mkdir()
        (self.root / "done.txt.d").mkdir()

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def write_active(self, name: str, content: str) -> Path:
        path = self.root / name
        path.write_text(content, encoding="utf-8")
        return path

    def write_done(self, name: str, content: str) -> Path:
        path = self.root / "done.txt.d" / name
        path.write_text(content, encoding="utf-8")
        return path

    def load_store(self, *, auto_normalize: bool = True) -> TodoDirectory:
        store = TodoDirectory(
            self.root,
            auto_normalize_multi_task_files=auto_normalize,
        )
        store.load()
        return store


class TestTodoDirectoryLoad(TodoDirectoryTestCase):
    def test_load_nonexistent_directory_gives_empty_list(self) -> None:
        missing = TodoDirectory(self.root / "missing")
        missing.load()
        self.assertEqual(missing.tasks, [])

    def test_load_parses_root_and_done_files_with_refs(self) -> None:
        self.write_active(
            "active.txt",
            "(A) Thank Mom for the meatballs @phone\nSecond task +Home\n",
        )
        self.write_done("done.txt", "x 2026-03-24 Done task\n")
        self.write_active("notes.md", "ignored\n")

        store = self.load_store()

        self.assertEqual(len(store.tasks), 3)
        self.assertEqual(store.tasks[0].priority, Priority.A)
        self.assertEqual(store.tasks[0].ref.relative_path, "active.txt")  # type: ignore[union-attr]
        self.assertEqual(store.tasks[0].ref.line_index, 0)  # type: ignore[union-attr]
        self.assertEqual(store.tasks[1].ref.relative_path, "active.txt")  # type: ignore[union-attr]
        self.assertEqual(store.tasks[1].ref.line_index, 1)  # type: ignore[union-attr]
        self.assertTrue(store.tasks[2].done)
        self.assertEqual(store.tasks[2].ref.relative_path, "done.txt.d/done.txt")  # type: ignore[union-attr]

    def test_load_skips_blank_lines(self) -> None:
        self.write_active("tasks.txt", "Task one\n\n\nTask two\n")

        store = self.load_store()

        self.assertEqual([task.raw for task in store.tasks], ["Task one", "Task two"])

    def test_duplicate_raw_lines_keep_distinct_refs(self) -> None:
        self.write_active("dupes.txt", "Same task\nSame task\n")

        store = self.load_store()

        self.assertEqual(len(store.tasks), 2)
        self.assertNotEqual(store.tasks[0].ref, store.tasks[1].ref)

    def test_load_invalid_leading_dates_without_crashing(self) -> None:
        self.write_active("broken.txt", "2026-99-99 broken import\n")

        store = self.load_store()

        self.assertEqual(len(store.tasks), 1)
        self.assertIsNone(store.tasks[0].creation_date)
        self.assertEqual(store.tasks[0].text, "2026-99-99 broken import")

    def test_load_ignores_symlinked_task_files(self) -> None:
        outside = Path(self._tmpdir.name) / "outside.txt"
        outside.write_text("Leaked task\n", encoding="utf-8")
        try:
            (self.root / "link.txt").symlink_to(outside)
        except OSError as exc:
            self.skipTest(f"symlinks unavailable: {exc}")

        store = self.load_store()

        self.assertEqual(store.tasks, [])


class TestTodoDirectoryWrites(TodoDirectoryTestCase):
    def test_add_task_creates_sequentially_named_file(self) -> None:
        store = self.load_store()

        created = store.add_task("Write tests", creation_date=None)

        files = sorted(path.name for path in self.root.glob("*.txt"))
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0], "task-000001.txt")
        self.assertEqual(created.raw, f"{date.today()} Write tests")
        self.assertEqual(created.ref.relative_path, files[0])  # type: ignore[union-attr]

    def test_add_task_uses_next_available_sequential_name(self) -> None:
        self.write_active("task-000001.txt", "Existing\n")
        self.write_active("task-000003.txt", "Existing\n")
        store = self.load_store()

        created = store.add_task("Write more tests", creation_date=date(2026, 3, 27))

        self.assertEqual(created.ref.relative_path, "task-000004.txt")  # type: ignore[union-attr]
        self.assertTrue((self.root / "task-000004.txt").exists())

    def test_has_external_changes_after_modification(self) -> None:
        path = self.write_active("task.txt", "Task one\n")
        store = self.load_store()

        self.assertFalse(store.has_external_changes())
        time.sleep(0.01)
        path.write_text("Task one\nTask two\n", encoding="utf-8")
        self.assertTrue(store.has_external_changes())

    def test_has_external_changes_after_file_creation_and_reload(self) -> None:
        store = self.load_store()

        self.assertFalse(store.has_external_changes())
        time.sleep(0.01)
        self.write_active("new.txt", "New task\n")
        self.assertTrue(store.has_external_changes())
        store.load()
        self.assertFalse(store.has_external_changes())

    def test_has_external_changes_after_file_deletion(self) -> None:
        path = self.write_active("task.txt", "Task one\n")
        store = self.load_store()

        path.unlink()
        self.assertTrue(store.has_external_changes())

    def test_update_task_rejects_path_traversal_refs(self) -> None:
        outside = Path(self._tmpdir.name) / "outside.txt"
        outside.write_text("line one\nline two\n", encoding="utf-8")
        store = self.load_store(auto_normalize=False)

        updated = store.update_task(TaskRef("../outside.txt", 0), "PWNED")

        self.assertIsNone(updated)
        self.assertEqual(outside.read_text(encoding="utf-8"), "line one\nline two\n")

    def test_delete_task_rejects_path_traversal_refs(self) -> None:
        outside = Path(self._tmpdir.name) / "outside.txt"
        outside.write_text("line one\nline two\n", encoding="utf-8")
        store = self.load_store(auto_normalize=False)

        deleted = store.delete_task(TaskRef("../outside.txt", 1))

        self.assertFalse(deleted)
        self.assertEqual(outside.read_text(encoding="utf-8"), "line one\nline two\n")

    def test_delete_task_rejects_negative_line_indexes(self) -> None:
        self.write_active("task.txt", "Task one\nTask two\n")
        store = self.load_store(auto_normalize=False)

        deleted = store.delete_task(TaskRef("task.txt", -1))

        self.assertFalse(deleted)
        self.assertEqual(
            (self.root / "task.txt").read_text(encoding="utf-8"),
            "Task one\nTask two\n",
        )


if __name__ == "__main__":
    unittest.main()
