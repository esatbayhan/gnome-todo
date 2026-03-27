"""Non-GTK helper CLI for the GNOME Shell panel extension."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from todotxt_lib import Task, TodoDirectory, add_task, classify_task, clean_task_text
from todotxt_lib.env import todo_dir_path as resolve_todo_dir_path

from ._config import get_auto_normalize_multi_task_files, get_todo_dir


SECTION_ORDER = ("overdue", "due_today", "scheduled_today")


@dataclass(frozen=True)
class AgendaSummary:
    """Structured summary returned to the panel extension."""

    configured: bool
    sections: dict[str, list[dict[str, object]]]
    counts: dict[str, int]


@dataclass(frozen=True)
class ResolvedPaths:
    """Resolved panel storage directory and configuration state."""

    configured: bool
    todo_dir: Path


def _task_to_payload(task: Task) -> dict[str, object]:
    """Serialize a task into a JSON-friendly payload."""
    return {
        "raw": task.raw,
        "text": task.text,
        "display_text": clean_task_text(task.text),
        "priority": str(task.priority) if task.priority is not None else None,
        "due": task.keyvalues.get("due"),
        "scheduled": task.keyvalues.get("scheduled"),
        "projects": list(task.projects),
        "contexts": list(task.contexts),
        "keyvalues": dict(task.keyvalues),
    }


def build_agenda_summary(tasks: list[Task], *, today: date | None = None) -> AgendaSummary:
    """Group active tasks into panel agenda sections."""
    effective_today = date.today() if today is None else today
    sections = {name: [] for name in SECTION_ORDER}

    for task in tasks:
        if task.done:
            continue
        bucket = classify_task(task, effective_today)
        if bucket is None:
            continue
        sections[bucket].append(_task_to_payload(task))

    counts = {name: len(items) for name, items in sections.items()}
    counts["total"] = sum(counts[name] for name in SECTION_ORDER)
    return AgendaSummary(
        configured=True,
        sections=sections,
        counts=counts,
    )


def _empty_summary(*, configured: bool) -> AgendaSummary:
    """Return an empty agenda response."""
    sections = {name: [] for name in SECTION_ORDER}
    counts = {name: 0 for name in SECTION_ORDER}
    counts["total"] = 0
    return AgendaSummary(configured=configured, sections=sections, counts=counts)


def _resolve_paths() -> ResolvedPaths:
    """Resolve the todo.txt.d root once per CLI request."""
    config_dir = get_todo_dir()
    configured = bool(os.environ.get("TODO_DIR") or config_dir)
    return ResolvedPaths(
        configured=configured,
        todo_dir=resolve_todo_dir_path(config_dir=config_dir),
    )


def _load_active_tasks(todo_dir: Path) -> list[Task]:
    """Load active tasks from the todo.txt.d root directory."""
    store = TodoDirectory(
        todo_dir,
        auto_normalize_multi_task_files=get_auto_normalize_multi_task_files(),
    )
    store.load()
    return [
        task
        for task in store.tasks
        if not task.done and (task.ref is None or not task.ref.is_done)
    ]


def summary_payload(*, today: date | None = None) -> dict[str, object]:
    """Build the JSON payload for ``summary``."""
    paths = _resolve_paths()
    if not paths.configured:
        return asdict(_empty_summary(configured=False))
    return asdict(build_agenda_summary(_load_active_tasks(paths.todo_dir), today=today))


def add_payload(text: str, *, today: date | None = None) -> dict[str, object]:
    """Append a new task and return a JSON-friendly result."""
    paths = _resolve_paths()
    if not paths.configured:
        return {
            "ok": False,
            "error": "Todo directory is not configured",
        }

    stripped = text.strip()
    if not stripped:
        return {
            "ok": False,
            "error": "Task text must not be empty",
        }

    store = TodoDirectory(
        paths.todo_dir,
        auto_normalize_multi_task_files=get_auto_normalize_multi_task_files(),
    )
    store.load()

    try:
        created = add_task(store, stripped, creation_date=today)
    except OSError as exc:
        return {
            "ok": False,
            "error": str(exc),
        }

    return {
        "ok": True,
        "error": None,
        "task": _task_to_payload(created),
    }


def _build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""
    parser = argparse.ArgumentParser(prog="todogui-panel")
    subparsers = parser.add_subparsers(dest="command", required=True)

    summary = subparsers.add_parser("summary")
    summary.add_argument("--json", action="store_true")

    add = subparsers.add_parser("add")
    add.add_argument("--text", required=True)
    add.add_argument("--json", action="store_true")

    return parser


def _print_json(payload: dict[str, object]) -> int:
    """Emit a JSON payload and return the intended exit code."""
    print(json.dumps(payload, ensure_ascii=True))
    return 0


def run(argv: list[str] | None = None) -> int:
    """Entry point for the panel helper CLI."""
    args = _build_parser().parse_args(sys.argv[1:] if argv is None else argv)

    if args.command == "summary":
        return _print_json(summary_payload())

    payload = add_payload(args.text)
    return _print_json(payload)


if __name__ == "__main__":
    raise SystemExit(run())
