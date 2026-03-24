"""Tests for the GNOME Shell panel helper CLI."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from todotxt_gui.panel_cli import add_payload, build_agenda_summary, summary_payload
from todotxt_lib.parser import parse_task


class TestAgendaSummary(unittest.TestCase):
    def test_includes_overdue_due_today_and_scheduled_today(self) -> None:
        tasks = [
            parse_task("Pay rent due:2026-03-22"),
            parse_task("Call Alex due:2026-03-23"),
            parse_task("Prep meeting scheduled:2026-03-23"),
        ]

        result = build_agenda_summary(tasks, today=date(2026, 3, 23))

        self.assertEqual(result.counts["overdue"], 1)
        self.assertEqual(result.counts["due_today"], 1)
        self.assertEqual(result.counts["scheduled_today"], 1)
        self.assertEqual(result.counts["total"], 3)

    def test_excludes_completed_tasks(self) -> None:
        tasks = [
            parse_task("x 2026-03-23 2026-03-20 Done due:2026-03-22"),
            parse_task("Open due:2026-03-22"),
        ]

        result = build_agenda_summary(tasks, today=date(2026, 3, 23))

        self.assertEqual(result.counts["overdue"], 1)
        self.assertEqual(result.counts["total"], 1)

    def test_deduplicates_by_precedence(self) -> None:
        tasks = [
            parse_task("Ship package due:2026-03-23 scheduled:2026-03-23"),
            parse_task("Missed bill due:2026-03-22 scheduled:2026-03-23"),
        ]

        result = build_agenda_summary(tasks, today=date(2026, 3, 23))

        self.assertEqual(result.counts["due_today"], 1)
        self.assertEqual(result.counts["scheduled_today"], 0)
        self.assertEqual(result.counts["overdue"], 1)
        self.assertEqual(
            result.sections["due_today"][0]["scheduled"],
            "2026-03-23",
        )
        self.assertEqual(
            result.sections["overdue"][0]["scheduled"],
            "2026-03-23",
        )

    def test_ignores_malformed_dates_without_crashing(self) -> None:
        tasks = [
            parse_task("Odd due:2026-99-99"),
            parse_task("Still scheduled scheduled:2026-03-23"),
        ]

        result = build_agenda_summary(tasks, today=date(2026, 3, 23))

        self.assertEqual(result.counts["overdue"], 0)
        self.assertEqual(result.counts["due_today"], 0)
        self.assertEqual(result.counts["scheduled_today"], 1)


class TestAddPayload(unittest.TestCase):
    def test_missing_configuration_returns_error(self) -> None:
        env = {k: v for k, v in os.environ.items() if k not in {"TODO_FILE", "TODO_DIR", "TODO_DONE_FILE"}}
        with patch.dict(os.environ, env, clear=True):
            with patch("todotxt_gui.panel_cli.get_todo_dir", return_value=None):
                result = add_payload("Write tests")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "Todo directory is not configured")

    def test_adds_plain_text_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self._add_in_tempdir(tmpdir, "Write tests", today=date(2026, 3, 23))
            todo_path = Path(tmpdir) / "todo.txt"

            self.assertTrue(result["ok"])
            self.assertEqual(
                todo_path.read_text(encoding="utf-8"),
                "2026-03-23 Write tests\n",
            )

    def test_preserves_raw_todotxt_syntax(self) -> None:
        text = "Plan launch +Work @desk due:2026-03-24 scheduled:2026-03-25"
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self._add_in_tempdir(tmpdir, text, today=date(2026, 3, 23))

            self.assertTrue(result["ok"])
            task = result["task"]
            assert isinstance(task, dict)
            self.assertEqual(task["projects"], ["Work"])
            self.assertEqual(task["contexts"], ["desk"])
            self.assertEqual(task["due"], "2026-03-24")
            self.assertEqual(task["scheduled"], "2026-03-25")

    def _add_in_tempdir(self, tmpdir: str, text: str, *, today: date) -> dict[str, object]:
        env = os.environ.copy()
        env["TODO_DIR"] = tmpdir
        with patch.dict(os.environ, env, clear=True):
            return add_payload(text, today=today)


class TestSummaryPayload(unittest.TestCase):
    def test_summary_reports_missing_configuration(self) -> None:
        env = {k: v for k, v in os.environ.items() if k not in {"TODO_FILE", "TODO_DIR", "TODO_DONE_FILE"}}
        with patch.dict(os.environ, env, clear=True):
            with patch("todotxt_gui.panel_cli.get_todo_dir", return_value=None):
                result = summary_payload(today=date(2026, 3, 23))

        self.assertFalse(result["configured"])
        self.assertEqual(result["counts"]["total"], 0)

    def test_summary_ignores_active_tasks_in_done_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            todo_path = Path(tmpdir) / "todo.txt"
            done_path = Path(tmpdir) / "done.txt"
            todo_path.write_text("", encoding="utf-8")
            done_path.write_text("Unexpected active task due:2026-03-23\n", encoding="utf-8")

            env = os.environ.copy()
            env["TODO_DIR"] = tmpdir
            with patch.dict(os.environ, env, clear=True):
                result = summary_payload(today=date(2026, 3, 23))

        self.assertTrue(result["configured"])
        self.assertEqual(result["counts"]["total"], 0)
        self.assertEqual(result["sections"]["due_today"], [])

    def test_summary_payload_keeps_expected_task_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            todo_path = Path(tmpdir) / "todo.txt"
            todo_path.write_text(
                "(A) Plan launch +Work @desk due:2026-03-23 scheduled:2026-03-23\n",
                encoding="utf-8",
            )

            env = os.environ.copy()
            env["TODO_DIR"] = tmpdir
            with patch.dict(os.environ, env, clear=True):
                result = summary_payload(today=date(2026, 3, 23))

        self.assertTrue(result["configured"])
        self.assertEqual(result["counts"]["due_today"], 1)
        task = result["sections"]["due_today"][0]
        self.assertEqual(
            set(task.keys()),
            {
                "raw",
                "text",
                "display_text",
                "priority",
                "due",
                "scheduled",
                "projects",
                "contexts",
                "keyvalues",
            },
        )
        self.assertEqual(task["display_text"], "Plan launch")
        self.assertEqual(task["priority"], "A")
        self.assertEqual(task["projects"], ["Work"])
        self.assertEqual(task["contexts"], ["desk"])
        self.assertEqual(task["due"], "2026-03-23")
        self.assertEqual(task["scheduled"], "2026-03-23")
        self.assertEqual(
            task["keyvalues"],
            {"due": "2026-03-23", "scheduled": "2026-03-23"},
        )


if __name__ == "__main__":
    unittest.main()
