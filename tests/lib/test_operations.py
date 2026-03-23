"""Tests for all task-mutating operations."""

import unittest
from datetime import date
from pathlib import Path

from todotxt_lib.operations import (
    add_task,
    all_contexts,
    all_projects,
    archive,
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
from todotxt_lib.todo_file import TodoFile


def _make_file(*lines: str) -> TodoFile:
    """Build an in-memory TodoFile from raw lines (no disk I/O)."""
    f = TodoFile(Path("/dev/null"))
    f.tasks = [parse_task(line) for line in lines]
    return f


class TestAddTask(unittest.TestCase):
    def test_prepends_creation_date(self) -> None:
        f = _make_file()
        task = add_task(f, "Call Mom @phone", creation_date=date(2024, 1, 15))
        self.assertEqual(task.creation_date, date(2024, 1, 15))
        self.assertEqual(task.text, "Call Mom @phone")
        self.assertEqual(task.contexts, ("phone",))
        self.assertIn(task, f.tasks)

    def test_defaults_to_today(self) -> None:
        f = _make_file()
        task = add_task(f, "Some task")
        self.assertEqual(task.creation_date, date.today())

    def test_appends_to_existing_tasks(self) -> None:
        f = _make_file("(A) Existing task")
        add_task(f, "New task", creation_date=date(2024, 1, 1))
        self.assertEqual(len(f.tasks), 2)


class TestCompleteTask(unittest.TestCase):
    def test_marks_done(self) -> None:
        f = _make_file("(A) 2011-03-01 Call Mom")
        task = f.tasks[0]
        done = complete_task(f, task, date(2011, 3, 3))
        self.assertTrue(done.done)

    def test_sets_completion_date(self) -> None:
        f = _make_file("Call Mom")
        task = f.tasks[0]
        done = complete_task(f, task, date(2024, 6, 1))
        self.assertEqual(done.completion_date, date(2024, 6, 1))

    def test_preserves_creation_date(self) -> None:
        f = _make_file("2011-03-01 Call Mom")
        task = f.tasks[0]
        done = complete_task(f, task, date(2011, 3, 3))
        self.assertEqual(done.creation_date, date(2011, 3, 1))

    def test_discards_priority(self) -> None:
        f = _make_file("(A) Call Mom")
        task = f.tasks[0]
        done = complete_task(f, task, date(2024, 1, 1))
        self.assertIsNone(done.priority)

    def test_preserves_projects_and_contexts(self) -> None:
        f = _make_file("(B) Schedule pickup +GarageSale @phone")
        task = f.tasks[0]
        done = complete_task(f, task, date(2024, 1, 1))
        self.assertEqual(done.projects, ("GarageSale",))
        self.assertEqual(done.contexts, ("phone",))

    def test_raw_reflects_serialized_form(self) -> None:
        f = _make_file("2011-03-01 Call Mom")
        task = f.tasks[0]
        done = complete_task(f, task, date(2011, 3, 3))
        self.assertEqual(done.raw, "x 2011-03-03 2011-03-01 Call Mom")

    def test_defaults_completion_date_to_today(self) -> None:
        f = _make_file("Call Mom")
        task = f.tasks[0]
        done = complete_task(f, task)
        self.assertEqual(done.completion_date, date.today())

    def test_replaces_task_in_file(self) -> None:
        f = _make_file("(A) Call Mom", "Task two")
        task = f.tasks[0]
        done = complete_task(f, task, date(2024, 1, 1))
        self.assertIs(f.tasks[0], done)
        self.assertEqual(len(f.tasks), 2)


class TestUncompleteTask(unittest.TestCase):
    def test_marks_not_done(self) -> None:
        f = _make_file("x 2024-01-01 2024-01-01 Call Mom")
        task = f.tasks[0]
        result = uncomplete_task(f, task)
        self.assertFalse(result.done)

    def test_removes_completion_date(self) -> None:
        f = _make_file("x 2024-01-01 Call Mom")
        task = f.tasks[0]
        result = uncomplete_task(f, task)
        self.assertIsNone(result.completion_date)

    def test_preserves_creation_date(self) -> None:
        f = _make_file("x 2024-06-01 2024-01-01 Call Mom")
        task = f.tasks[0]
        result = uncomplete_task(f, task)
        self.assertEqual(result.creation_date, date(2024, 1, 1))

    def test_preserves_text_and_metadata(self) -> None:
        f = _make_file("x 2024-01-01 Buy milk +Groceries @store")
        task = f.tasks[0]
        result = uncomplete_task(f, task)
        self.assertEqual(result.text, "Buy milk +Groceries @store")
        self.assertEqual(result.projects, ("Groceries",))
        self.assertEqual(result.contexts, ("store",))

    def test_replaces_task_in_file(self) -> None:
        f = _make_file("x 2024-01-01 Call Mom")
        task = f.tasks[0]
        result = uncomplete_task(f, task)
        self.assertIs(f.tasks[0], result)

    def test_raises_on_incomplete_task(self) -> None:
        f = _make_file("Call Mom")
        task = f.tasks[0]
        with self.assertRaises(ValueError):
            uncomplete_task(f, task)


class TestDeleteTask(unittest.TestCase):
    def test_removes_task(self) -> None:
        f = _make_file("(A) Task one", "Task two")
        target = f.tasks[0]
        delete_task(f, target)
        self.assertEqual(len(f.tasks), 1)
        self.assertNotIn(target, f.tasks)

    def test_raises_for_unknown_task(self) -> None:
        f = _make_file("Task one")
        stranger = parse_task("Completely different task")
        with self.assertRaises(ValueError):
            delete_task(f, stranger)


class TestSetPriority(unittest.TestCase):
    def test_sets_new_priority(self) -> None:
        f = _make_file("Call Mom")
        task = f.tasks[0]
        updated = set_priority(f, task, Priority.A)
        self.assertEqual(updated.priority, Priority.A)

    def test_replaces_existing_priority(self) -> None:
        f = _make_file("(A) Call Mom")
        task = f.tasks[0]
        updated = set_priority(f, task, Priority.C)
        self.assertEqual(updated.priority, Priority.C)

    def test_raw_updated(self) -> None:
        f = _make_file("Call Mom")
        task = f.tasks[0]
        updated = set_priority(f, task, Priority.B)
        self.assertTrue(updated.raw.startswith("(B)"))

    def test_invalid_priority_enum_raises(self) -> None:
        with self.assertRaises(ValueError):
            Priority("a")  # lowercase
        with self.assertRaises(ValueError):
            Priority("AB")  # two chars
        with self.assertRaises(ValueError):
            Priority("1")  # digit

    def test_raises_on_completed_task(self) -> None:
        f = _make_file("x 2024-01-01 Done task")
        task = f.tasks[0]
        with self.assertRaises(ValueError):
            set_priority(f, task, Priority.A)

    def test_replaces_task_in_file(self) -> None:
        f = _make_file("Call Mom")
        task = f.tasks[0]
        updated = set_priority(f, task, Priority.A)
        self.assertIs(f.tasks[0], updated)


class TestDeprioritize(unittest.TestCase):
    def test_removes_priority(self) -> None:
        f = _make_file("(A) Call Mom")
        task = f.tasks[0]
        updated = deprioritize(f, task)
        self.assertIsNone(updated.priority)

    def test_no_op_on_task_without_priority(self) -> None:
        f = _make_file("Call Mom")
        task = f.tasks[0]
        updated = deprioritize(f, task)
        self.assertIsNone(updated.priority)

    def test_raw_updated(self) -> None:
        f = _make_file("(A) Call Mom")
        task = f.tasks[0]
        updated = deprioritize(f, task)
        self.assertNotIn("(A)", updated.raw)

    def test_replaces_task_in_file(self) -> None:
        f = _make_file("(A) Call Mom")
        task = f.tasks[0]
        updated = deprioritize(f, task)
        self.assertIs(f.tasks[0], updated)


class TestReplaceTask(unittest.TestCase):
    def test_replaces_task_in_file(self) -> None:
        f = _make_file("(A) Old task", "Another task")
        old = f.tasks[0]
        new = replace_task(f, old, "(B) New task")
        self.assertEqual(new.priority, Priority.B)
        self.assertEqual(f.tasks[0].priority, Priority.B)
        self.assertEqual(len(f.tasks), 2)


class TestSortKey(unittest.TestCase):
    def test_active_before_done(self) -> None:
        active = parse_task("Call Mom")
        done = parse_task("x 2024-01-01 Done task")
        self.assertLess(sort_key(active), sort_key(done))

    def test_higher_priority_first(self) -> None:
        a = parse_task("(A) Task A")
        b = parse_task("(B) Task B")
        self.assertLess(sort_key(a), sort_key(b))

    def test_priority_before_no_priority(self) -> None:
        z = parse_task("(Z) Task Z")
        none_ = parse_task("Task no priority")
        self.assertLess(sort_key(z), sort_key(none_))

    def test_alphabetical_within_same_priority(self) -> None:
        apple = parse_task("(A) Apple")
        banana = parse_task("(A) Banana")
        self.assertLess(sort_key(apple), sort_key(banana))

    def test_case_insensitive(self) -> None:
        lower = parse_task("(A) apple")
        upper = parse_task("(A) Banana")
        self.assertLess(sort_key(lower), sort_key(upper))


class TestSortTasks(unittest.TestCase):
    def test_sorts_tasks(self) -> None:
        tasks = [
            parse_task("x 2024-01-01 Done task"),
            parse_task("(B) Task B"),
            parse_task("Task no priority"),
            parse_task("(A) Task A"),
        ]
        result = sort_tasks(tasks)
        self.assertEqual(result[0].priority, Priority.A)
        self.assertEqual(result[1].priority, Priority.B)
        self.assertIsNone(result[2].priority)
        self.assertTrue(result[3].done)

    def test_does_not_mutate_input(self) -> None:
        tasks = [parse_task("(B) Second"), parse_task("(A) First")]
        sort_tasks(tasks)
        self.assertEqual(tasks[0].priority, Priority.B)


class TestAllProjects(unittest.TestCase):
    def test_collects_unique_sorted(self) -> None:
        tasks = [
            parse_task("Task +Beta +Alpha"),
            parse_task("Task +Alpha +Gamma"),
        ]
        self.assertEqual(all_projects(tasks), ["Alpha", "Beta", "Gamma"])

    def test_empty_tasks(self) -> None:
        self.assertEqual(all_projects([]), [])

    def test_no_projects(self) -> None:
        tasks = [parse_task("Plain task")]
        self.assertEqual(all_projects(tasks), [])


class TestAllContexts(unittest.TestCase):
    def test_collects_unique_sorted(self) -> None:
        tasks = [
            parse_task("Task @phone @home"),
            parse_task("Task @phone @work"),
        ]
        self.assertEqual(all_contexts(tasks), ["home", "phone", "work"])

    def test_empty_tasks(self) -> None:
        self.assertEqual(all_contexts([]), [])


class TestFilterTasks(unittest.TestCase):
    def setUp(self) -> None:
        self.tasks = [
            parse_task("(A) Call Mom +Family @phone"),
            parse_task("(B) Schedule Goodwill pickup +GarageSale @phone"),
            parse_task("Post signs +GarageSale"),
            parse_task("x 2011-03-03 Done task +GarageSale"),
        ]

    def test_filter_by_project(self) -> None:
        result = filter_tasks(self.tasks, project="GarageSale")
        self.assertEqual(len(result), 3)

    def test_filter_by_context(self) -> None:
        result = filter_tasks(self.tasks, context="phone")
        self.assertEqual(len(result), 2)

    def test_filter_done_false(self) -> None:
        result = filter_tasks(self.tasks, done=False)
        self.assertEqual(len(result), 3)

    def test_filter_done_true(self) -> None:
        result = filter_tasks(self.tasks, done=True)
        self.assertEqual(len(result), 1)

    def test_filter_by_priority(self) -> None:
        result = filter_tasks(self.tasks, priority=Priority.A)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].priority, Priority.A)

    def test_filter_combined(self) -> None:
        result = filter_tasks(self.tasks, project="GarageSale", done=False)
        self.assertEqual(len(result), 2)

    def test_no_filter_returns_all(self) -> None:
        result = filter_tasks(self.tasks)
        self.assertEqual(len(result), len(self.tasks))

    def test_filter_by_text_case_insensitive(self) -> None:
        result = filter_tasks(self.tasks, text="call")
        self.assertEqual(len(result), 1)
        self.assertIn("Call Mom", result[0].text)

    def test_filter_by_text_no_match(self) -> None:
        result = filter_tasks(self.tasks, text="xyz_not_present")
        self.assertEqual(len(result), 0)

    def test_filter_by_text_multiple_terms_chained(self) -> None:
        # Chaining two filter_tasks calls acts as AND for multiple text terms
        result = filter_tasks(self.tasks, text="goodwill")
        result = filter_tasks(result, text="phone")
        self.assertEqual(len(result), 1)


class TestArchive(unittest.TestCase):
    def test_moves_completed_tasks(self) -> None:
        todo = _make_file(
            "(A) Incomplete task",
            "x 2024-01-01 Done task",
            "Another incomplete",
        )
        done_file = _make_file()
        count = archive(todo, done_file)
        self.assertEqual(count, 1)
        self.assertEqual(len(todo.tasks), 2)
        self.assertEqual(len(done_file.tasks), 1)
        self.assertTrue(done_file.tasks[0].done)

    def test_no_completed_tasks(self) -> None:
        todo = _make_file("Task one", "Task two")
        done_file = _make_file()
        count = archive(todo, done_file)
        self.assertEqual(count, 0)
        self.assertEqual(len(todo.tasks), 2)

    def test_appends_to_existing_done_file(self) -> None:
        todo = _make_file("x 2024-01-01 New done task")
        done_file = _make_file("x 2023-12-31 Old done task")
        archive(todo, done_file)
        self.assertEqual(len(done_file.tasks), 2)


if __name__ == "__main__":
    unittest.main()
