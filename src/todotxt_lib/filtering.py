"""Task filtering, classification, and tag listing helpers."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Literal

from .operations import filter_tasks
from .task import Task

SelectionKind = Literal["smart", "project", "context"]
TagAttribute = Literal["projects", "contexts"]


@dataclass(frozen=True)
class SidebarSelection:
    """Current sidebar selection in the main window."""

    kind: SelectionKind
    value: str


@dataclass(frozen=True)
class SmartFilterCounts:
    """Task counts for the smart-filter sidebar rows."""

    inbox: int
    today: int
    scheduled: int
    starting: int
    all_active: int
    completed: int


@dataclass(frozen=True)
class TagFlowState:
    """Items and suggestion labels rendered in a tag flow."""

    items: tuple[str, ...]
    suggestions: tuple[str, ...]


# ── Smart filter counts ──────────────────────────────────────────────


def compute_smart_filter_counts(
    tasks: list[Task],
    *,
    today: date,
) -> SmartFilterCounts:
    """Count tasks for the smart-filter sidebar."""
    today_str = today.isoformat()
    inbox = 0
    today_count = 0
    scheduled = 0
    starting = 0
    all_active = 0
    completed = 0

    for task in tasks:
        if task.done:
            completed += 1
            continue

        all_active += 1
        if not task.projects:
            inbox += 1
        if task.keyvalues.get("due") == today_str:
            today_count += 1
        if "scheduled" in task.keyvalues:
            scheduled += 1
        if "starting" in task.keyvalues:
            starting += 1

    return SmartFilterCounts(
        inbox=inbox,
        today=today_count,
        scheduled=scheduled,
        starting=starting,
        all_active=all_active,
        completed=completed,
    )


# ── Task filtering ───────────────────────────────────────────────────


def filter_tasks_for_selection(
    tasks: list[Task],
    selection: SidebarSelection,
    *,
    today: date,
) -> list[Task]:
    """Return tasks matching the current sidebar selection."""
    today_str = today.isoformat()

    if selection.kind == "smart":
        if selection.value == "Inbox":
            return [task for task in tasks if not task.done and not task.projects]
        if selection.value == "Today":
            return [
                task
                for task in tasks
                if not task.done and task.keyvalues.get("due") == today_str
            ]
        if selection.value == "Scheduled":
            return [
                task for task in tasks if not task.done and "scheduled" in task.keyvalues
            ]
        if selection.value == "Starting":
            return [
                task for task in tasks if not task.done and "starting" in task.keyvalues
            ]
        if selection.value == "All":
            return [task for task in tasks if not task.done]
        if selection.value == "Completed":
            return [task for task in tasks if task.done]
        return tasks

    if selection.kind == "project":
        return filter_tasks(tasks, project=selection.value)

    return filter_tasks(tasks, context=selection.value)


# ── Tag listing ──────────────────────────────────────────────────────


def build_tag_list(
    tasks: list[Task],
    attr: TagAttribute,
) -> list[tuple[str, int]]:
    """Return sorted (tag_name, active_count) pairs for sidebar rows."""
    counts: dict[str, int] = {}
    for task in tasks:
        if not task.done:
            for tag in getattr(task, attr):
                counts[tag] = counts.get(tag, 0) + 1

    for task in tasks:
        for tag in getattr(task, attr):
            if tag not in counts:
                counts[tag] = 0

    return sorted(counts.items())


# ── Tag flow state ───────────────────────────────────────────────────


def build_tag_flow_state(
    all_items: Iterable[str],
    current_items: tuple[str, ...],
    *,
    filter_text: str = "",
    suggestion_limit: int = 8,
) -> TagFlowState:
    """Return the visible items and suggestion labels for a tag flow."""
    lowered_filter = filter_text.strip().lower()
    suggestions = tuple(
        item
        for item in all_items
        if item not in current_items
        and (not lowered_filter or lowered_filter in item.lower())
    )[:suggestion_limit]
    return TagFlowState(items=current_items, suggestions=suggestions)


# ── Date helpers ─────────────────────────────────────────────────────


def safe_date(value: str | None) -> date | None:
    """Return an ISO date or ``None`` for invalid/missing values."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def classify_task(task: Task, today: date) -> str | None:
    """Return the highest-priority agenda bucket for *task*."""
    due = safe_date(task.keyvalues.get("due"))
    scheduled = safe_date(task.keyvalues.get("scheduled"))

    if due is not None and due < today:
        return "overdue"
    if due == today:
        return "due_today"
    if scheduled == today:
        return "scheduled_today"
    return None
