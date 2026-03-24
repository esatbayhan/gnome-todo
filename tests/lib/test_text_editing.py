"""Tests for todotxt_lib.text_editing helpers."""

from __future__ import annotations

import unittest

from todotxt_lib import parse_task
from todotxt_lib.text_editing import (
    append_missing_task_metadata,
    clean_task_text,
    normalize_tag_input,
    rebuild_task_line,
)


class TestRebuildTaskLine(unittest.TestCase):
    def test_updates_text_and_removes_metadata(self) -> None:
        task = parse_task("Plan launch +Work @desk due:2026-03-23")

        self.assertEqual(
            rebuild_task_line(
                task,
                new_text="Plan launch tonight +Work @desk due:2026-03-23",
                remove_context="desk",
                remove_project="Work",
                due=None,
            ),
            "Plan launch tonight",
        )

    def test_adds_missing_context_project_and_dates(self) -> None:
        task = parse_task("Plan launch")

        self.assertEqual(
            rebuild_task_line(
                task,
                add_context="desk",
                add_project="Work",
                due="2026-03-23",
                scheduled="2026-03-24",
                starting="2026-03-22",
            ),
            "Plan launch @desk +Work due:2026-03-23 scheduled:2026-03-24 starting:2026-03-22",
        )

    def test_skips_duplicate_contexts_and_projects(self) -> None:
        task = parse_task("Plan launch +Work @desk")

        self.assertEqual(
            rebuild_task_line(
                task,
                add_context="desk",
                add_project="Work",
            ),
            "Plan launch +Work @desk",
        )


class TestAppendMissingTaskMetadata(unittest.TestCase):
    def test_appends_selected_metadata_in_dialog_order(self) -> None:
        self.assertEqual(
            append_missing_task_metadata(
                "Plan launch",
                contexts=["desk"],
                projects=["Work"],
                due="2026-03-23",
                scheduled="2026-03-24",
                starting="2026-03-22",
            ),
            "Plan launch @desk +Work due:2026-03-23 scheduled:2026-03-24 starting:2026-03-22",
        )

    def test_avoids_duplicate_metadata_already_typed(self) -> None:
        self.assertEqual(
            append_missing_task_metadata(
                "Plan launch @desk +Work due:2026-03-23",
                contexts=["desk", "home"],
                projects=["Work", "Ops"],
                due="2026-03-23",
                scheduled="2026-03-24",
            ),
            "Plan launch @desk +Work due:2026-03-23 @home +Ops scheduled:2026-03-24",
        )


class TestCleanTaskText(unittest.TestCase):
    def test_strips_contexts_projects_and_keyvalues(self) -> None:
        self.assertEqual(
            clean_task_text("Plan launch +Work @desk due:2026-03-23 scheduled:2026-03-24"),
            "Plan launch",
        )

    def test_preserves_urls_while_stripping_metadata(self) -> None:
        self.assertEqual(
            clean_task_text("Review http://example.com +Web @desk due:2026-03-23"),
            "Review http://example.com",
        )


class TestNormalizeTagInput(unittest.TestCase):
    def test_strips_prefix_and_surrounding_whitespace(self) -> None:
        self.assertEqual(normalize_tag_input("  @@desk  ", "@"), "desk")
        self.assertEqual(normalize_tag_input("  ++Work  ", "+"), "Work")


if __name__ == "__main__":
    unittest.main()
