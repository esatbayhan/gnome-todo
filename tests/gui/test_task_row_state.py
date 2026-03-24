"""Tests for pure task-row presentation helpers."""

from __future__ import annotations

import unittest

from todotxt_gui._task_row_state import build_task_row_display
from todotxt_lib import parse_task


class TestBuildTaskRowDisplay(unittest.TestCase):
    def test_done_task_uses_strikethrough_markup_and_hides_metadata(self) -> None:
        task = parse_task("x 2026-03-24 Done +Work @desk")

        display = build_task_row_display(
            task,
            show_project=True,
            show_raw_text=True,
        )

        self.assertTrue(display.use_markup)
        self.assertTrue(display.dimmed)
        self.assertIn("<s>", display.label_text)
        self.assertIsNone(display.metadata)

    def test_hidden_raw_text_uses_cleaned_text(self) -> None:
        task = parse_task("Plan launch +Work @desk due:2026-03-24")

        display = build_task_row_display(
            task,
            show_project=True,
            show_raw_text=False,
        )

        self.assertEqual(display.label_text, "Plan launch")
        assert display.metadata is not None
        self.assertEqual(display.metadata.due, "2026-03-24")

    def test_limits_visible_contexts_and_projects(self) -> None:
        task = parse_task("Task +A +B +C @one @two @three @four")

        display = build_task_row_display(
            task,
            show_project=True,
            show_raw_text=True,
        )

        assert display.metadata is not None
        self.assertEqual(display.metadata.contexts, ("one", "two", "three"))
        self.assertEqual(display.metadata.projects, ("A", "B"))

    def test_hides_projects_when_project_labels_disabled(self) -> None:
        task = parse_task("Task +A +B @one")

        display = build_task_row_display(
            task,
            show_project=False,
            show_raw_text=True,
        )

        assert display.metadata is not None
        self.assertEqual(display.metadata.projects, ())


if __name__ == "__main__":
    unittest.main()
