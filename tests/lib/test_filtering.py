"""Tests for todotxt_lib.filtering helpers."""

from __future__ import annotations

import unittest
from datetime import date

from todotxt_lib import parse_task
from todotxt_lib.filtering import (
    SidebarSelection,
    build_tag_flow_state,
    build_tag_list,
    classify_task,
    compute_smart_filter_counts,
    filter_tasks_for_selection,
    safe_date,
)


class TestComputeSmartFilterCounts(unittest.TestCase):
    def test_counts_active_and_completed_buckets(self) -> None:
        tasks = [
            parse_task(
                "Inbox task due:2026-03-24 scheduled:2026-03-25 starting:2026-03-23"
            ),
            parse_task("Project task +Work"),
            parse_task("x 2026-03-24 Done task +Work"),
        ]

        counts = compute_smart_filter_counts(tasks, today=date(2026, 3, 24))

        self.assertEqual(counts.inbox, 1)
        self.assertEqual(counts.today, 1)
        self.assertEqual(counts.scheduled, 1)
        self.assertEqual(counts.starting, 1)
        self.assertEqual(counts.all_active, 2)
        self.assertEqual(counts.completed, 1)


class TestFilterTasksForSelection(unittest.TestCase):
    def setUp(self) -> None:
        self.tasks = [
            parse_task("Inbox task @desk due:2026-03-24"),
            parse_task("Project task +Work @desk scheduled:2026-03-25"),
            parse_task("Another project task +Home starting:2026-03-24"),
            parse_task("x 2026-03-24 Done task +Work @desk"),
        ]
        self.today = date(2026, 3, 24)

    def test_filters_today_smart_selection(self) -> None:
        filtered = filter_tasks_for_selection(
            self.tasks,
            SidebarSelection(kind="smart", value="Today"),
            today=self.today,
        )

        self.assertEqual(
            [task.raw for task in filtered],
            ["Inbox task @desk due:2026-03-24"],
        )

    def test_filters_project_selection(self) -> None:
        filtered = filter_tasks_for_selection(
            self.tasks,
            SidebarSelection(kind="project", value="Work"),
            today=self.today,
        )

        self.assertEqual(
            [task.raw for task in filtered],
            [
                "Project task +Work @desk scheduled:2026-03-25",
                "x 2026-03-24 Done task +Work @desk",
            ],
        )

    def test_filters_context_selection(self) -> None:
        filtered = filter_tasks_for_selection(
            self.tasks,
            SidebarSelection(kind="context", value="desk"),
            today=self.today,
        )

        self.assertEqual(len(filtered), 3)

    def test_filters_completed_selection(self) -> None:
        filtered = filter_tasks_for_selection(
            self.tasks,
            SidebarSelection(kind="smart", value="Completed"),
            today=self.today,
        )

        self.assertEqual(
            [task.raw for task in filtered],
            ["x 2026-03-24 Done task +Work @desk"],
        )


class TestBuildTagList(unittest.TestCase):
    def test_counts_only_active_tasks_but_keeps_done_only_tags(self) -> None:
        tasks = [
            parse_task("Active +Work @desk"),
            parse_task("x 2026-03-24 Done +ArchiveOnly @phone"),
        ]

        self.assertEqual(
            build_tag_list(tasks, "projects"),
            [("ArchiveOnly", 0), ("Work", 1)],
        )
        self.assertEqual(
            build_tag_list(tasks, "contexts"),
            [("desk", 1), ("phone", 0)],
        )


class TestBuildTagFlowState(unittest.TestCase):
    def test_excludes_current_items_from_suggestions(self) -> None:
        state = build_tag_flow_state(
            ["desk", "home", "travel"],
            ("desk",),
        )

        self.assertEqual(state.items, ("desk",))
        self.assertEqual(state.suggestions, ("home", "travel"))

    def test_filters_suggestions_case_insensitively(self) -> None:
        state = build_tag_flow_state(
            ["Desk", "Home", "Travel"],
            (),
            filter_text="ho",
        )

        self.assertEqual(state.suggestions, ("Home",))

    def test_limits_visible_suggestions(self) -> None:
        state = build_tag_flow_state(
            [f"tag{i}" for i in range(10)],
            (),
        )

        self.assertEqual(len(state.suggestions), 8)


class TestSafeDate(unittest.TestCase):
    def test_valid_date(self) -> None:
        self.assertEqual(safe_date("2026-03-24"), date(2026, 3, 24))

    def test_none_input(self) -> None:
        self.assertIsNone(safe_date(None))

    def test_invalid_string(self) -> None:
        self.assertIsNone(safe_date("not-a-date"))


class TestClassifyTask(unittest.TestCase):
    def test_overdue(self) -> None:
        task = parse_task("Overdue due:2026-03-20")
        self.assertEqual(classify_task(task, date(2026, 3, 24)), "overdue")

    def test_due_today(self) -> None:
        task = parse_task("Today due:2026-03-24")
        self.assertEqual(classify_task(task, date(2026, 3, 24)), "due_today")

    def test_scheduled_today(self) -> None:
        task = parse_task("Scheduled scheduled:2026-03-24")
        self.assertEqual(classify_task(task, date(2026, 3, 24)), "scheduled_today")

    def test_no_match(self) -> None:
        task = parse_task("Future due:2026-04-01")
        self.assertIsNone(classify_task(task, date(2026, 3, 24)))


if __name__ == "__main__":
    unittest.main()
