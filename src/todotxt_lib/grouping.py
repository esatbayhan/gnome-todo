"""Task grouping functions for the content pane."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from .task import Priority, Task

# ── Constants ────────────────────────────────────────────────────────

GROUPING_MODES = (
    "context",
    "project",
    "due",
    "scheduled",
    "starting",
    "priority",
    "none",
)
FALLBACK_GROUPS = frozenset(
    {
        "Uncategorized",
        "No Project",
        "No Due Date",
        "Not Scheduled",
        "No Start Date",
        "No Priority",
    }
)

# ── Tag-based grouping ──────────────────────────────────────────────


def group_by_context(tasks: list[Task]) -> list[tuple[str, list[Task]]]:
    """Group tasks by their first @context."""
    return _group_by_tag(
        tasks,
        lambda t: t.contexts[0] if t.contexts else "Uncategorized",
    )


def group_by_project(tasks: list[Task]) -> list[tuple[str, list[Task]]]:
    """Group tasks by their first +project."""
    return _group_by_tag(
        tasks,
        lambda t: t.projects[0] if t.projects else "No Project",
    )


def _group_by_tag(
    tasks: list[Task],
    key_fn: Callable[[Task], str],
) -> list[tuple[str, list[Task]]]:
    """Named groups sorted alphabetically, fallback group last."""
    groups: dict[str, list[Task]] = {}
    for task in tasks:
        groups.setdefault(key_fn(task), []).append(task)

    fallback_key: str | None = None
    result: list[tuple[str, list[Task]]] = []
    for key in sorted(groups):
        if key in FALLBACK_GROUPS:
            fallback_key = key
        else:
            result.append((key, groups[key]))
    if fallback_key is not None:
        result.append((fallback_key, groups[fallback_key]))
    return result


# ── Date-based grouping ─────────────────────────────────────────────


def group_by_due(
    tasks: list[Task],
    *,
    today: date | None = None,
) -> list[tuple[str, list[Task]]]:
    """Group tasks by due date: Overdue, Today, future dates, No Due Date."""
    return _group_by_date_key(tasks, "due", "No Due Date", today=today)


def group_by_scheduled(
    tasks: list[Task],
    *,
    today: date | None = None,
) -> list[tuple[str, list[Task]]]:
    """Group tasks by scheduled date."""
    return _group_by_date_key(tasks, "scheduled", "Not Scheduled", today=today)


def group_by_starting(
    tasks: list[Task],
    *,
    today: date | None = None,
) -> list[tuple[str, list[Task]]]:
    """Group tasks by starting date."""
    return _group_by_date_key(tasks, "starting", "No Start Date", today=today)


def _group_by_date_key(
    tasks: list[Task],
    key: str,
    fallback_label: str,
    *,
    today: date | None = None,
) -> list[tuple[str, list[Task]]]:
    """Generic date grouping: Overdue, Today, upcoming dates, then fallback."""
    if today is None:
        today = date.today()

    overdue: list[Task] = []
    today_tasks: list[Task] = []
    upcoming: dict[str, list[Task]] = {}
    no_date: list[Task] = []

    for task in tasks:
        date_str = task.keyvalues.get(key)
        if not date_str:
            no_date.append(task)
            continue
        try:
            d = date.fromisoformat(date_str)
        except ValueError:
            no_date.append(task)
            continue
        if d < today:
            overdue.append(task)
        elif d == today:
            today_tasks.append(task)
        else:
            upcoming.setdefault(date_str, []).append(task)

    result: list[tuple[str, list[Task]]] = []
    if overdue:
        result.append(("Overdue", overdue))
    if today_tasks:
        result.append(("Today", today_tasks))
    for d in sorted(upcoming):
        result.append((d, upcoming[d]))
    if no_date:
        result.append((fallback_label, no_date))
    return result


# ── Priority grouping ───────────────────────────────────────────────


def group_by_priority(tasks: list[Task]) -> list[tuple[str, list[Task]]]:
    """Group tasks by priority level."""
    groups: dict[str, list[Task]] = {}
    for task in tasks:
        if task.priority is not None:
            key = f"Priority {task.priority.value}"
        else:
            key = "No Priority"
        groups.setdefault(key, []).append(task)

    result: list[tuple[str, list[Task]]] = []
    for pri in Priority:
        key = f"Priority {pri.value}"
        if key in groups:
            result.append((key, groups[key]))
    if "No Priority" in groups:
        result.append(("No Priority", groups["No Priority"]))
    return result


# ── Dispatch ────────────────────────────────────────────────────────

_DISPATCH: dict[str, Callable[[list[Task]], list[tuple[str, list[Task]]]]] = {
    "context": group_by_context,
    "project": group_by_project,
    "due": group_by_due,
    "scheduled": group_by_scheduled,
    "starting": group_by_starting,
    "priority": group_by_priority,
}


def group_tasks(tasks: list[Task], mode: str) -> list[tuple[str, list[Task]]]:
    """Group tasks using the specified mode."""
    fn = _DISPATCH.get(mode)
    if fn is not None:
        return fn(tasks)
    return [("", tasks)]
