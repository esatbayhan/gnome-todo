"""Tests for parse_task and serialize_task.

All example tasks are taken directly from the todo.txt specification (https://github.com/todotxt/todo.txt).
"""

import unittest
from datetime import date
from types import MappingProxyType

from todotxt_lib.parser import parse_task, serialize_task
from todotxt_lib.task import Priority


class TestParseIncompleteTask(unittest.TestCase):
    def test_plain_task(self) -> None:
        task = parse_task("Post signs around the neighborhood +GarageSale")
        self.assertFalse(task.done)
        self.assertIsNone(task.priority)
        self.assertIsNone(task.creation_date)
        self.assertEqual(task.projects, ("GarageSale",))
        self.assertEqual(task.contexts, ())

    def test_priority_a(self) -> None:
        task = parse_task("(A) Thank Mom for the meatballs @phone")
        self.assertFalse(task.done)
        self.assertEqual(task.priority, Priority.A)
        self.assertEqual(task.contexts, ("phone",))

    def test_priority_b_with_project_and_context(self) -> None:
        task = parse_task("(B) Schedule Goodwill pickup +GarageSale @phone")
        self.assertEqual(task.priority, Priority.B)
        self.assertEqual(task.projects, ("GarageSale",))
        self.assertEqual(task.contexts, ("phone",))

    def test_priority_with_creation_date(self) -> None:
        task = parse_task("(A) 2011-03-02 Call Mom")
        self.assertEqual(task.priority, Priority.A)
        self.assertEqual(task.creation_date, date(2011, 3, 2))
        self.assertEqual(task.text, "Call Mom")

    def test_creation_date_without_priority(self) -> None:
        task = parse_task("2011-03-02 Document +TodoTxt task format")
        self.assertIsNone(task.priority)
        self.assertEqual(task.creation_date, date(2011, 3, 2))
        self.assertEqual(task.projects, ("TodoTxt",))

    def test_multiple_projects_and_contexts(self) -> None:
        task = parse_task("(A) Call Mom +Family +PeaceLoveAndHappiness @iphone @phone")
        self.assertEqual(task.priority, Priority.A)
        self.assertEqual(task.projects, ("Family", "PeaceLoveAndHappiness"))
        self.assertEqual(task.contexts, ("iphone", "phone"))

    def test_no_contexts(self) -> None:
        task = parse_task("Email SoAndSo at soandso@example.com")
        # soandso@example.com is not a context — no leading space before @
        self.assertEqual(task.contexts, ())

    def test_no_projects(self) -> None:
        task = parse_task("Learn how to add 2+2")
        # 2+2 is not a project — no leading space before +
        self.assertEqual(task.projects, ())

    def test_context_at_start_of_text(self) -> None:
        task = parse_task("@GroceryStore pies")
        self.assertEqual(task.contexts, ("GroceryStore",))

    def test_keyvalue_metadata(self) -> None:
        task = parse_task("Submit report due:2010-01-02")
        self.assertEqual(task.keyvalues["due"], "2010-01-02")

    def test_multiple_keyvalues(self) -> None:
        task = parse_task("Task with due:2025-01-01 t:2024-12-01")
        self.assertEqual(task.keyvalues["due"], "2025-01-01")
        self.assertEqual(task.keyvalues["t"], "2024-12-01")

    def test_url_not_treated_as_keyvalue(self) -> None:
        task = parse_task("Visit http://example.com for details")
        self.assertNotIn("http", task.keyvalues)

    def test_keyvalues_is_immutable(self) -> None:
        task = parse_task("Task due:2025-01-01")
        self.assertIsInstance(task.keyvalues, MappingProxyType)
        with self.assertRaises(TypeError):
            task.keyvalues["due"] = "2099-01-01"  # type: ignore[index]


class TestPriorityNotRecognised(unittest.TestCase):
    """Spec: priority must be first token, uppercase, followed by a space."""

    def test_priority_not_first(self) -> None:
        task = parse_task("Really gotta call Mom (A) @phone @someday")
        self.assertIsNone(task.priority)

    def test_priority_lowercase(self) -> None:
        task = parse_task("(b) Get back to the boss")
        self.assertIsNone(task.priority)

    def test_priority_no_trailing_space(self) -> None:
        task = parse_task("(B)->Submit TPS report")
        self.assertIsNone(task.priority)

    def test_date_not_treated_as_priority(self) -> None:
        task = parse_task("(A) Call Mom 2011-03-02")
        # date appears after text — not a creation date
        self.assertIsNone(task.creation_date)
        self.assertEqual(task.text, "Call Mom 2011-03-02")


class TestParseCompleteTask(unittest.TestCase):
    def test_simple_completed(self) -> None:
        task = parse_task("x 2011-03-03 Call Mom")
        self.assertTrue(task.done)
        self.assertEqual(task.completion_date, date(2011, 3, 3))
        self.assertIsNone(task.creation_date)
        self.assertEqual(task.text, "Call Mom")

    def test_completed_with_creation_date(self) -> None:
        task = parse_task(
            "x 2011-03-02 2011-03-01 Review Tim's pull request +TodoTxtTouch @github"
        )
        self.assertTrue(task.done)
        self.assertEqual(task.completion_date, date(2011, 3, 2))
        self.assertEqual(task.creation_date, date(2011, 3, 1))
        self.assertEqual(task.projects, ("TodoTxtTouch",))
        self.assertEqual(task.contexts, ("github",))

    def test_completed_date_only_no_text(self) -> None:
        # Bug fix: a completed task ending with a date and no description
        # must still have the completion date parsed correctly.
        task = parse_task("x 2024-01-01")
        self.assertTrue(task.done)
        self.assertEqual(task.completion_date, date(2024, 1, 1))
        self.assertEqual(task.text, "")

    def test_completed_no_description(self) -> None:
        task = parse_task("x 2024-06-15 2024-06-01")
        self.assertTrue(task.done)
        self.assertEqual(task.completion_date, date(2024, 6, 15))
        self.assertEqual(task.creation_date, date(2024, 6, 1))
        self.assertEqual(task.text, "")


class TestCompletionNotRecognised(unittest.TestCase):
    """Spec: completion marker must be lowercase x followed by a space, at start."""

    def test_x_no_space(self) -> None:
        task = parse_task("xylophone lesson")
        self.assertFalse(task.done)

    def test_uppercase_x(self) -> None:
        task = parse_task("X 2012-01-01 Make resolutions")
        self.assertFalse(task.done)

    def test_x_not_first(self) -> None:
        task = parse_task("(A) x Find ticket prices")
        self.assertFalse(task.done)
        # The (A) is recognised as priority; "x Find ticket prices" is text
        self.assertEqual(task.priority, Priority.A)


class TestSerializeTask(unittest.TestCase):
    def test_round_trip_plain(self) -> None:
        line = "Post signs around the neighborhood +GarageSale"
        self.assertEqual(serialize_task(parse_task(line)), line)

    def test_round_trip_with_priority(self) -> None:
        line = "(A) Thank Mom for the meatballs @phone"
        self.assertEqual(serialize_task(parse_task(line)), line)

    def test_round_trip_with_priority_and_date(self) -> None:
        line = "(A) 2011-03-02 Call Mom"
        self.assertEqual(serialize_task(parse_task(line)), line)

    def test_round_trip_completed_with_two_dates(self) -> None:
        line = "x 2011-03-02 2011-03-01 Review Tim's pull request +TodoTxtTouch @github"
        self.assertEqual(serialize_task(parse_task(line)), line)

    def test_round_trip_completed_no_creation_date(self) -> None:
        line = "x 2011-03-03 Call Mom"
        self.assertEqual(serialize_task(parse_task(line)), line)

    def test_round_trip_creation_date_only(self) -> None:
        line = "2011-03-02 Document +TodoTxt task format"
        self.assertEqual(serialize_task(parse_task(line)), line)

    def test_round_trip_completed_date_only_no_text(self) -> None:
        line = "x 2024-01-01"
        self.assertEqual(serialize_task(parse_task(line)), line)

    def test_completed_task_drops_priority(self) -> None:
        from pathlib import Path

        from todotxt_lib.operations import complete_task
        from todotxt_lib.todo_file import TodoFile

        task = parse_task("(A) 2011-03-02 Call Mom")
        f = TodoFile(Path("/dev/null"))
        f.tasks = [task]
        done_task = complete_task(f, task, date(2011, 3, 3))
        serialized = serialize_task(done_task)
        self.assertNotIn("(A)", serialized)
        self.assertTrue(serialized.startswith("x "))


if __name__ == "__main__":
    unittest.main()
