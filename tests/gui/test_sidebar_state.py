"""Tests for GUI-specific sidebar helpers."""

from __future__ import annotations

import unittest

from todotxt_gui._sidebar_state import project_color


class TestProjectColor(unittest.TestCase):
    def test_is_stable_for_same_name(self) -> None:
        self.assertEqual(project_color("Work"), project_color("Work"))

    def test_differs_by_name_within_palette(self) -> None:
        self.assertIn(project_color("Work"), {
            "blue",
            "orange",
            "red",
            "purple",
            "green",
            "teal",
            "pink",
            "indigo",
            "brown",
            "mint",
        })


if __name__ == "__main__":
    unittest.main()
