"""Tests for GUI-specific window presentation helpers."""

from __future__ import annotations

import unittest
from datetime import date

from todotxt_lib import SidebarSelection, parse_task

from todotxt_gui._window_state import (
    build_content_state,
    current_title_icon,
    should_show_project_labels,
    smart_filter_row_counts,
)


FILTER_ICONS = {
    "Inbox": "mail-unread-symbolic",
    "Today": "x-office-calendar-symbolic",
    "Scheduled": "alarm-symbolic",
    "Starting": "media-playback-start-symbolic",
    "All": "view-list-symbolic",
    "Completed": "object-select-symbolic",
}


class TestContentState(unittest.TestCase):
    def test_completed_view_uses_done_tasks_for_display(self) -> None:
        tasks = [
            parse_task("Active +Work"),
            parse_task("x 2026-03-24 Done +Work"),
        ]

        state = build_content_state(
            tasks,
            selection=SidebarSelection(kind="smart", value="Completed"),
            search_text="",
            grouping_mode="context",
            today=date(2026, 3, 24),
            filter_icons=FILTER_ICONS,
        )

        self.assertEqual(state.title, "Completed")
        self.assertEqual(state.icon_name, "object-select-symbolic")
        self.assertEqual(
            [task.raw for task in state.display_tasks],
            ["x 2026-03-24 Done +Work"],
        )
        self.assertFalse(state.show_completed_section)
        self.assertIsNone(state.empty_state)

    def test_empty_tag_selection_uses_empty_state(self) -> None:
        tasks = [
            parse_task("Inbox task"),
            parse_task("x 2026-03-24 Done task"),
        ]

        state = build_content_state(
            tasks,
            selection=SidebarSelection(kind="context", value="desk"),
            search_text="",
            grouping_mode="none",
            today=date(2026, 3, 24),
            filter_icons=FILTER_ICONS,
        )

        self.assertEqual(state.title, "@desk")
        self.assertEqual(state.icon_name, None)
        self.assertEqual(state.display_tasks, ())
        self.assertEqual(state.done_tasks, ())
        self.assertIsNotNone(state.empty_state)

    def test_project_selection_hides_project_labels(self) -> None:
        tasks = [
            parse_task("Project task +Work"),
            parse_task("x 2026-03-24 Done task +Work"),
        ]

        state = build_content_state(
            tasks,
            selection=SidebarSelection(kind="project", value="Work"),
            search_text="",
            grouping_mode="context",
            today=date(2026, 3, 24),
            filter_icons=FILTER_ICONS,
        )

        self.assertFalse(state.show_project)
        self.assertTrue(state.show_completed_section)
        self.assertEqual(
            [task.raw for task in state.display_tasks],
            ["Project task +Work"],
        )

    def test_search_results_empty_state_is_distinct(self) -> None:
        tasks = [parse_task("Plan launch +Work")]

        state = build_content_state(
            tasks,
            selection=SidebarSelection(kind="smart", value="All"),
            search_text="missing",
            grouping_mode="none",
            today=date(2026, 3, 24),
            filter_icons=FILTER_ICONS,
        )

        assert state.empty_state is not None
        self.assertEqual(state.empty_state.title, "No Results")
        self.assertEqual(state.empty_state.icon_name, "edit-find-symbolic")


class TestWindowPresentationHelpers(unittest.TestCase):
    def test_current_title_icon_for_context_selection(self) -> None:
        self.assertEqual(
            current_title_icon(
                SidebarSelection(kind="context", value="desk"),
                FILTER_ICONS,
            ),
            ("@desk", None),
        )

    def test_should_show_project_labels_only_when_not_project_focused(self) -> None:
        self.assertTrue(
            should_show_project_labels(
                "context",
                SidebarSelection(kind="smart", value="All"),
            )
        )
        self.assertFalse(
            should_show_project_labels(
                "project",
                SidebarSelection(kind="smart", value="All"),
            )
        )
        self.assertFalse(
            should_show_project_labels(
                "context",
                SidebarSelection(kind="project", value="Work"),
            )
        )

    def test_smart_filter_row_counts_keys(self) -> None:
        from todotxt_lib import SmartFilterCounts

        counts = SmartFilterCounts(
            inbox=1, today=2, scheduled=3, starting=4, all_active=5, completed=6
        )
        row_counts = smart_filter_row_counts(counts)
        self.assertEqual(row_counts["Inbox"], 1)
        self.assertEqual(row_counts["Today"], 2)
        self.assertEqual(row_counts["Completed"], 6)


if __name__ == "__main__":
    unittest.main()
