"""Tests for todotxt_lib.grouping helpers."""

from __future__ import annotations

import unittest
from datetime import date

from todotxt_lib import parse_task
from todotxt_lib.grouping import (
    group_by_context,
    group_by_due,
    group_by_priority,
    group_by_project,
    group_tasks,
)


class TestGroupByContext(unittest.TestCase):
    def test_groups_by_first_context(self) -> None:
        tasks = [
            parse_task("Task A @home"),
            parse_task("Task B @work"),
            parse_task("Task C @home"),
        ]
        groups = group_by_context(tasks)
        names = [g[0] for g in groups]
        self.assertEqual(names, ["home", "work"])
        self.assertEqual(len(groups[0][1]), 2)
        self.assertEqual(len(groups[1][1]), 1)

    def test_tasks_without_context_go_to_uncategorized(self) -> None:
        tasks = [parse_task("Task A"), parse_task("Task B @work")]
        groups = group_by_context(tasks)
        names = [g[0] for g in groups]
        self.assertEqual(names, ["work", "Uncategorized"])


class TestGroupByProject(unittest.TestCase):
    def test_groups_by_first_project(self) -> None:
        tasks = [
            parse_task("Task A +Alpha"),
            parse_task("Task B +Beta"),
            parse_task("Task C +Alpha"),
        ]
        groups = group_by_project(tasks)
        names = [g[0] for g in groups]
        self.assertEqual(names, ["Alpha", "Beta"])

    def test_tasks_without_project_go_to_fallback(self) -> None:
        tasks = [parse_task("Task A"), parse_task("Task B +Beta")]
        groups = group_by_project(tasks)
        names = [g[0] for g in groups]
        self.assertEqual(names, ["Beta", "No Project"])


class TestGroupByDue(unittest.TestCase):
    def test_separates_overdue_today_and_upcoming(self) -> None:
        today = date(2026, 3, 24)
        tasks = [
            parse_task("Overdue due:2026-03-20"),
            parse_task("Today due:2026-03-24"),
            parse_task("Future due:2026-04-01"),
            parse_task("No date"),
        ]
        groups = group_by_due(tasks, today=today)
        names = [g[0] for g in groups]
        self.assertEqual(names, ["Overdue", "Today", "2026-04-01", "No Due Date"])


class TestGroupByPriority(unittest.TestCase):
    def test_groups_by_priority_level(self) -> None:
        tasks = [
            parse_task("(A) High"),
            parse_task("(C) Low"),
            parse_task("None"),
        ]
        groups = group_by_priority(tasks)
        names = [g[0] for g in groups]
        self.assertEqual(names, ["Priority A", "Priority C", "No Priority"])


class TestGroupTasks(unittest.TestCase):
    def test_none_mode_returns_single_group(self) -> None:
        tasks = [parse_task("A"), parse_task("B")]
        groups = group_tasks(tasks, "none")
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0][0], "")
        self.assertEqual(len(groups[0][1]), 2)

    def test_unknown_mode_returns_single_group(self) -> None:
        tasks = [parse_task("A")]
        groups = group_tasks(tasks, "unknown")
        self.assertEqual(len(groups), 1)


if __name__ == "__main__":
    unittest.main()
