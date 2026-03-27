"""Tests for todotxt_lib.mutations helpers."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import tempfile
import unittest

from todotxt_lib import Priority
from todotxt_lib.mutations import (
    add_tag_to_task,
    add_task_with_priority,
    complete_task_by_ref,
    delete_task_by_ref,
    find_task_by_ref,
    uncomplete_task_by_ref,
    update_task_from_detail,
)
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


class TestFindTaskByRef(TodoDirectoryCase):
    def test_finds_task_in_done_directory(self) -> None:
        self.write_done("done-task.txt", "x 2026-03-24 Done task\n")
        store = self.load_store()

        located = find_task_by_ref(store, store.tasks[0].ref)

        assert located is not None
        self.assertEqual(located.source_kind, "done")
        self.assertEqual(located.task.raw, "x 2026-03-24 Done task")


class TestAddTaskWithPriority(TodoDirectoryCase):
    def test_adds_prioritized_task(self) -> None:
        store = self.load_store()

        outcome = add_task_with_priority(
            store,
            "Plan launch +Work",
            creation_date=date(2026, 3, 24),
            priority=Priority.B,
        )

        self.assertTrue(outcome.changed)
        assert outcome.task is not None
        self.assertEqual(outcome.task.priority, Priority.B)
        self.assertEqual(store.tasks[0].raw, "(B) 2026-03-24 Plan launch +Work")


class TestCompleteTaskByRef(TodoDirectoryCase):
    def test_completes_active_task(self) -> None:
        self.write_active("task.txt", "Active +Work\n")
        store = self.load_store()

        outcome = complete_task_by_ref(
            store,
            store.tasks[0].ref,
            completion_date=date(2026, 3, 24),
        )

        self.assertTrue(outcome.changed)
        assert outcome.task is not None
        self.assertTrue(outcome.task.done)
        self.assertEqual(outcome.task.ref.relative_path, "done.txt.d/task.txt")  # type: ignore[union-attr]

    def test_returns_missing_for_done_source(self) -> None:
        self.write_done("done-task.txt", "x 2026-03-24 Done task\n")
        store = self.load_store()

        outcome = complete_task_by_ref(
            store,
            store.tasks[0].ref,
            completion_date=date(2026, 3, 24),
        )

        self.assertEqual(outcome.status, "missing")


class TestDeleteTaskByRef(TodoDirectoryCase):
    def test_deletes_done_task(self) -> None:
        self.write_done("done-task.txt", "x 2026-03-24 Done task\n")
        store = self.load_store()

        outcome = delete_task_by_ref(store, store.tasks[0].ref)

        self.assertTrue(outcome.changed)
        self.assertEqual(store.tasks, [])


class TestAddTagToTask(TodoDirectoryCase):
    def test_skips_duplicate_project_tag(self) -> None:
        self.write_active("task.txt", "Task +Work\n")
        store = self.load_store()

        outcome = add_tag_to_task(
            store,
            store.tasks[0].ref,
            tag_name="Work",
            tag_kind="project",
        )

        self.assertEqual(outcome.status, "noop")

    def test_adds_context_and_preserves_creation_date(self) -> None:
        self.write_active("task.txt", "2026-03-20 Task +Work\n")
        store = self.load_store()

        outcome = add_tag_to_task(
            store,
            store.tasks[0].ref,
            tag_name="desk",
            tag_kind="context",
        )

        self.assertTrue(outcome.changed)
        assert outcome.task is not None
        self.assertEqual(outcome.task.raw, "2026-03-20 Task +Work @desk")
        self.assertEqual(outcome.task.creation_date, date(2026, 3, 20))


class TestUpdateTaskFromDetail(TodoDirectoryCase):
    def test_updates_priority_for_active_task(self) -> None:
        self.write_active("task.txt", "2026-03-20 Call Mom\n")
        store = self.load_store()

        outcome = update_task_from_detail(store, store.tasks[0].ref, "__priority__:A")

        self.assertTrue(outcome.changed)
        assert outcome.task is not None
        self.assertEqual(outcome.task.raw, "(A) 2026-03-20 Call Mom")

    def test_priority_update_on_done_task_is_noop(self) -> None:
        self.write_done("done-task.txt", "x 2026-03-24 Done task\n")
        store = self.load_store()

        outcome = update_task_from_detail(
            store,
            store.tasks[0].ref,
            "__priority__:A",
        )

        self.assertEqual(outcome.status, "noop")

    def test_text_update_preserves_prefix_fields(self) -> None:
        self.write_active("task.txt", "(B) 2026-03-20 Call Mom +Home\n")
        store = self.load_store()

        outcome = update_task_from_detail(
            store,
            store.tasks[0].ref,
            "Call Dad +Home due:2026-03-30",
        )

        self.assertTrue(outcome.changed)
        assert outcome.task is not None
        self.assertEqual(
            outcome.task.raw,
            "(B) 2026-03-20 Call Dad +Home due:2026-03-30",
        )
        self.assertEqual(outcome.task.creation_date, date(2026, 3, 20))


class TestUncompleteTaskByRef(TodoDirectoryCase):
    def test_moves_done_task_back_to_todo_root(self) -> None:
        self.write_done("done-task.txt", "x 2026-03-24 2026-03-20 Done task +Work\n")
        store = self.load_store()

        outcome = uncomplete_task_by_ref(store, store.tasks[0].ref)

        self.assertTrue(outcome.changed)
        assert outcome.task is not None
        self.assertEqual(outcome.task.raw, "2026-03-20 Done task +Work")
        self.assertEqual(outcome.task.ref.relative_path, "done-task.txt")  # type: ignore[union-attr]


if __name__ == "__main__":
    unittest.main()
