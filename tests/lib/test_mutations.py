"""Tests for todotxt_lib.mutations helpers."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import unittest

from todotxt_lib.mutations import (
    add_tag_to_task,
    add_task_with_priority,
    complete_task_by_raw,
    delete_task_by_raw,
    find_task_by_raw,
    uncomplete_task_by_raw,
    update_task_from_detail,
)
from todotxt_lib import Priority, TodoFile, parse_task


def _make_file(*lines: str) -> TodoFile:
    file = TodoFile(Path("/dev/null"))
    file.tasks = [parse_task(line) for line in lines]
    return file


class TestFindTaskByRaw(unittest.TestCase):
    def test_finds_task_in_done_file(self) -> None:
        todo = _make_file("Active task")
        done = _make_file("x 2026-03-24 Done task")

        located = find_task_by_raw(todo, done, "x 2026-03-24 Done task")

        assert located is not None
        self.assertEqual(located.source_kind, "done")
        self.assertEqual(located.task.raw, "x 2026-03-24 Done task")


class TestAddTaskWithPriority(unittest.TestCase):
    def test_adds_prioritized_task_and_marks_todo_for_save(self) -> None:
        todo = _make_file()

        outcome = add_task_with_priority(
            todo,
            "Plan launch +Work",
            creation_date=date(2026, 3, 24),
            priority=Priority.B,
        )

        self.assertTrue(outcome.changed)
        self.assertTrue(outcome.save_todo)
        assert outcome.task is not None
        self.assertEqual(outcome.task.priority, Priority.B)
        self.assertEqual(todo.tasks[0].raw, "(B) 2026-03-24 Plan launch +Work")


class TestCompleteTaskByRaw(unittest.TestCase):
    def test_completes_active_todo_task(self) -> None:
        todo = _make_file("Active +Work")
        done = _make_file("x 2026-03-24 Archived")

        outcome = complete_task_by_raw(
            todo,
            done,
            "Active +Work",
            completion_date=date(2026, 3, 24),
        )

        self.assertTrue(outcome.changed)
        self.assertTrue(outcome.save_todo)
        self.assertFalse(outcome.save_done)
        assert outcome.task is not None
        self.assertTrue(outcome.task.done)
        self.assertEqual(todo.tasks[0].raw, "x 2026-03-24 Active +Work")

    def test_returns_missing_for_done_source(self) -> None:
        todo = _make_file()
        done = _make_file("x 2026-03-24 Done task")

        outcome = complete_task_by_raw(
            todo,
            done,
            "x 2026-03-24 Done task",
            completion_date=date(2026, 3, 24),
        )

        self.assertEqual(outcome.status, "missing")


class TestDeleteTaskByRaw(unittest.TestCase):
    def test_deletes_done_task_and_marks_done_file_for_save(self) -> None:
        todo = _make_file("Active")
        done = _make_file("x 2026-03-24 Done task")

        outcome = delete_task_by_raw(todo, done, "x 2026-03-24 Done task")

        self.assertTrue(outcome.changed)
        self.assertFalse(outcome.save_todo)
        self.assertTrue(outcome.save_done)
        self.assertEqual(done.tasks, [])


class TestAddTagToTask(unittest.TestCase):
    def test_skips_duplicate_project_tag(self) -> None:
        todo = _make_file("Task +Work")
        done = _make_file()

        outcome = add_tag_to_task(
            todo,
            done,
            "Task +Work",
            tag_name="Work",
            tag_kind="project",
        )

        self.assertEqual(outcome.status, "noop")

    def test_adds_context_and_marks_todo_file_for_save(self) -> None:
        todo = _make_file("Task +Work")
        done = _make_file()

        outcome = add_tag_to_task(
            todo,
            done,
            "Task +Work",
            tag_name="desk",
            tag_kind="context",
        )

        self.assertTrue(outcome.changed)
        self.assertTrue(outcome.save_todo)
        assert outcome.task is not None
        self.assertEqual(outcome.task.raw, "Task +Work @desk")


class TestUpdateTaskFromDetail(unittest.TestCase):
    def test_updates_priority_for_active_todo_task(self) -> None:
        todo = _make_file("Call Mom")
        done = _make_file()

        outcome = update_task_from_detail(todo, done, "Call Mom", "__priority__:A")

        self.assertTrue(outcome.changed)
        self.assertTrue(outcome.save_todo)
        assert outcome.task is not None
        self.assertEqual(outcome.task.raw, "(A) Call Mom")

    def test_priority_update_on_done_task_is_noop(self) -> None:
        todo = _make_file()
        done = _make_file("x 2026-03-24 Done task")

        outcome = update_task_from_detail(
            todo,
            done,
            "x 2026-03-24 Done task",
            "__priority__:A",
        )

        self.assertEqual(outcome.status, "noop")


class TestUncompleteTaskByRaw(unittest.TestCase):
    def test_moves_done_task_back_to_todo(self) -> None:
        todo = _make_file("Active")
        done = _make_file("x 2026-03-24 2026-03-20 Done task +Work")

        outcome = uncomplete_task_by_raw(
            todo,
            done,
            "x 2026-03-24 2026-03-20 Done task +Work",
        )

        self.assertTrue(outcome.changed)
        self.assertTrue(outcome.save_todo)
        self.assertTrue(outcome.save_done)
        self.assertEqual(len(done.tasks), 0)
        self.assertEqual(todo.tasks[-1].raw, "2026-03-20 Done task +Work")


if __name__ == "__main__":
    unittest.main()
