"""Tests for task mutations and pure helper operations."""

from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from todotxt_lib.operations import (
    add_task,
    all_contexts,
    all_projects,
    complete_task,
    delete_task,
    deprioritize,
    filter_tasks,
    replace_task,
    set_priority,
    sort_key,
    sort_tasks,
    uncomplete_task,
)
from todotxt_lib.parser import parse_task
from todotxt_lib.task import Priority
from todotxt_lib.todo_directory import TodoDirectory


class TodoDirectoryCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name) / "todo.txt.d"
        self.root.mkdir()
        (self.root / "done.txt.d").mkdir()

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def write_active(self, name: str, content: str) -> None:
        (self.root / name).write_text(content, encoding="utf-8")

    def write_done(self, name: str, content: str) -> None:
        (self.root / "done.txt.d" / name).write_text(content, encoding="utf-8")

    def load_store(self, *, auto_normalize: bool = True) -> TodoDirectory:
        store = TodoDirectory(
            self.root,
            auto_normalize_multi_task_files=auto_normalize,
        )
        store.load()
        return store


class TestAddTask(TodoDirectoryCase):
    def test_prepends_creation_date(self) -> None:
        store = self.load_store()

        task = add_task(store, "Call Mom @phone", creation_date=date(2024, 1, 15))

        self.assertEqual(task.creation_date, date(2024, 1, 15))
        self.assertEqual(task.text, "Call Mom @phone")
        self.assertEqual(task.contexts, ("phone",))
        self.assertEqual(len(store.tasks), 1)
        self.assertEqual(store.tasks[0].raw, "2024-01-15 Call Mom @phone")


class TestCompleteTask(TodoDirectoryCase):
    def test_single_task_completion_moves_file_to_done_directory(self) -> None:
        self.write_active("call-mom.txt", "(A) 2026-03-20 Call Mom +Home @phone\n")
        store = self.load_store()
        task = store.tasks[0]

        done = complete_task(store, task, date(2026, 3, 24))

        self.assertFalse((self.root / "call-mom.txt").exists())
        archived_path = self.root / "done.txt.d" / "call-mom.txt"
        self.assertTrue(archived_path.exists())
        self.assertEqual(
            archived_path.read_text(encoding="utf-8"),
            "x 2026-03-24 2026-03-20 Call Mom +Home @phone\n",
        )
        self.assertTrue(done.done)
        self.assertIsNone(done.priority)
        self.assertEqual(done.projects, ("Home",))
        self.assertEqual(done.contexts, ("phone",))
        self.assertEqual(done.ref.relative_path, "done.txt.d/call-mom.txt")  # type: ignore[union-attr]

    def test_complete_multi_task_file_rewrites_source_when_normalization_opted_out(self) -> None:
        self.write_active("batch.txt", "Task one\nTask two\n")
        store = self.load_store(auto_normalize=False)

        done = complete_task(store, store.tasks[0], date(2026, 3, 24))

        self.assertEqual((self.root / "batch.txt").read_text(encoding="utf-8"), "Task two\n")
        done_files = sorted((self.root / "done.txt.d").glob("*.txt"))
        self.assertEqual(len(done_files), 1)
        self.assertEqual(done_files[0].name, "done-000001.txt")
        self.assertEqual(done_files[0].read_text(encoding="utf-8"), "x 2026-03-24 Task one\n")
        self.assertTrue(done.done)
        self.assertEqual(done.ref.relative_path, "done.txt.d/done-000001.txt")  # type: ignore[union-attr]


class TestUncompleteTask(TodoDirectoryCase):
    def test_single_task_uncomplete_moves_file_back_to_root(self) -> None:
        self.write_done("done-task.txt", "x 2026-03-24 2026-03-20 Done task +Work\n")
        store = self.load_store()

        result = uncomplete_task(store, store.tasks[0])

        self.assertFalse((self.root / "done.txt.d" / "done-task.txt").exists())
        active_path = self.root / "done-task.txt"
        self.assertTrue(active_path.exists())
        self.assertEqual(
            active_path.read_text(encoding="utf-8"),
            "2026-03-20 Done task +Work\n",
        )
        self.assertFalse(result.done)
        self.assertEqual(result.ref.relative_path, "done-task.txt")  # type: ignore[union-attr]


class TestPriorityAndReplacement(TodoDirectoryCase):
    def test_set_priority_and_deprioritize(self) -> None:
        self.write_active("task.txt", "2026-03-20 Call Mom\n")
        store = self.load_store()

        prioritized = set_priority(store, store.tasks[0], Priority.B)
        deprioritized = deprioritize(store, prioritized)

        self.assertEqual(prioritized.raw, "(B) 2026-03-20 Call Mom")
        self.assertEqual(deprioritized.raw, "2026-03-20 Call Mom")

    def test_replace_task_updates_single_task_file(self) -> None:
        self.write_active("task.txt", "2026-03-20 Call Mom\n")
        store = self.load_store()

        updated = replace_task(store, store.tasks[0], "(A) 2026-03-20 New task")

        self.assertEqual(updated.priority, Priority.A)
        self.assertEqual(
            (self.root / "task.txt").read_text(encoding="utf-8"),
            "(A) 2026-03-20 New task\n",
        )

    def test_delete_task_rewrites_multi_task_file_in_place_when_normalization_is_off(self) -> None:
        self.write_active("batch.txt", "Task one\nTask two\n")
        store = self.load_store(auto_normalize=False)

        delete_task(store, store.tasks[0])

        self.assertEqual((self.root / "batch.txt").read_text(encoding="utf-8"), "Task two\n")


class TestMultiTaskNormalization(TodoDirectoryCase):
    def test_replace_task_normalizes_multi_task_file_when_enabled(self) -> None:
        self.write_active("batch.txt", "Task one\nTask two\n")
        store = self.load_store(auto_normalize=True)

        updated = replace_task(store, store.tasks[0], "(B) Task one updated")

        self.assertFalse((self.root / "batch.txt").exists())
        active_files = sorted(self.root.glob("*.txt"))
        self.assertEqual(len(active_files), 2)
        self.assertEqual([path.name for path in active_files], ["task-000001.txt", "task-000002.txt"])
        self.assertEqual(updated.raw, "(B) Task one updated")
        self.assertEqual(store.find_task(updated.ref).raw, "(B) Task one updated")  # type: ignore[arg-type]
        self.assertCountEqual([task.raw for task in store.tasks], ["(B) Task one updated", "Task two"])

    def test_replace_task_keeps_multi_task_file_when_normalization_is_disabled(self) -> None:
        self.write_active("batch.txt", "Task one\nTask two\n")
        store = self.load_store(auto_normalize=False)

        replace_task(store, store.tasks[0], "(B) Task one updated")

        self.assertTrue((self.root / "batch.txt").exists())
        self.assertEqual(
            (self.root / "batch.txt").read_text(encoding="utf-8"),
            "(B) Task one updated\nTask two\n",
        )


class TestPureHelpers(unittest.TestCase):
    def test_sort_key_active_before_done(self) -> None:
        active = parse_task("Call Mom")
        done = parse_task("x 2024-01-01 Done task")
        self.assertLess(sort_key(active), sort_key(done))

    def test_sort_tasks_and_tag_helpers(self) -> None:
        tasks = [
            parse_task("Task +Work @desk"),
            parse_task("(A) Another +Home @phone"),
            parse_task("x 2024-01-01 Done +Archive @desk"),
        ]

        sorted_tasks = sort_tasks(tasks)

        self.assertEqual(sorted_tasks[0].raw, "(A) Another +Home @phone")
        self.assertEqual(all_projects(tasks), ["Archive", "Home", "Work"])
        self.assertEqual(all_contexts(tasks), ["desk", "phone"])

    def test_filter_tasks(self) -> None:
        tasks = [
            parse_task("Task +Work @desk"),
            parse_task("(A) Another +Home @phone"),
            parse_task("x 2024-01-01 Done +Archive @desk"),
        ]

        filtered = filter_tasks(tasks, context="desk", done=False)

        self.assertEqual([task.raw for task in filtered], ["Task +Work @desk"])


if __name__ == "__main__":
    unittest.main()
