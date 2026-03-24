"""Window presentation state helpers (GUI-specific parts)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from todotxt_lib import (
    SidebarSelection,
    SmartFilterCounts,
    Task,
    filter_tasks_for_selection,
)


@dataclass(frozen=True)
class EmptyState:
    """Empty-state content for the main task list."""

    title: str
    description: str
    icon_name: str


@dataclass(frozen=True)
class ContentState:
    """Derived content/header state for the current selection."""

    title: str
    icon_name: str | None
    display_tasks: tuple[Task, ...]
    done_tasks: tuple[Task, ...]
    show_project: bool
    show_completed_section: bool
    empty_state: EmptyState | None

    @property
    def count(self) -> int:
        """Number shown in the content header."""
        return len(self.display_tasks)


def smart_filter_row_counts(counts: SmartFilterCounts) -> dict[str, int]:
    """Return counts keyed by smart-filter row name."""
    return {
        "Inbox": counts.inbox,
        "Today": counts.today,
        "Scheduled": counts.scheduled,
        "Starting": counts.starting,
        "All": counts.all_active,
        "Completed": counts.completed,
    }


def build_content_state(
    tasks: list[Task],
    *,
    selection: SidebarSelection,
    search_text: str,
    grouping_mode: str,
    today: date,
    filter_icons: dict[str, str],
) -> ContentState:
    """Compute header and content state without touching GTK widgets."""
    filtered_tasks = filter_tasks_for_selection(tasks, selection, today=today)
    normalized_search = search_text.strip().lower()
    if normalized_search:
        filtered_tasks = [
            task for task in filtered_tasks if normalized_search in task.text.lower()
        ]

    done_tasks = tuple(task for task in filtered_tasks if task.done)
    is_completed_view = selection.kind == "smart" and selection.value == "Completed"
    display_tasks = (
        done_tasks
        if is_completed_view
        else tuple(task for task in filtered_tasks if not task.done)
    )
    empty_state = None
    if not display_tasks and not done_tasks:
        empty_state = _build_empty_state(has_search=bool(normalized_search))

    title, icon_name = current_title_icon(selection, filter_icons)
    return ContentState(
        title=title,
        icon_name=icon_name,
        display_tasks=display_tasks,
        done_tasks=done_tasks,
        show_project=should_show_project_labels(grouping_mode, selection),
        show_completed_section=bool(done_tasks) and not is_completed_view,
        empty_state=empty_state,
    )


def current_title_icon(
    selection: SidebarSelection,
    filter_icons: dict[str, str],
) -> tuple[str, str | None]:
    """Return the content header title and optional icon name."""
    if selection.kind == "smart":
        return selection.value, filter_icons.get(selection.value)
    if selection.kind == "context":
        return f"@{selection.value}", None
    return selection.value, None


def should_show_project_labels(
    grouping_mode: str,
    selection: SidebarSelection,
) -> bool:
    """Return whether task rows should render project labels."""
    return grouping_mode != "project" and selection.kind != "project"


def _build_empty_state(*, has_search: bool) -> EmptyState:
    if has_search:
        return EmptyState(
            title="No Results",
            description="Try a different search term.",
            icon_name="edit-find-symbolic",
        )

    return EmptyState(
        title="No Tasks",
        description='Press "+" to get started.',
        icon_name="checkbox-checked-symbolic",
    )
