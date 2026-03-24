"""Pure helpers for task-row display and metadata decisions."""

from __future__ import annotations

import html
from dataclasses import dataclass

from todotxt_lib import Priority, Task, clean_task_text


@dataclass(frozen=True)
class TaskRowMetadata:
    """Visible metadata for a task row."""

    priority: Priority | None
    due: str | None
    scheduled: str | None
    starting: str | None
    contexts: tuple[str, ...]
    projects: tuple[str, ...]

    @property
    def is_empty(self) -> bool:
        """Return whether the row has any visible metadata."""
        return not any(
            (
                self.priority is not None,
                self.due is not None,
                self.scheduled is not None,
                self.starting is not None,
                self.contexts,
                self.projects,
            )
        )


@dataclass(frozen=True)
class TaskRowDisplay:
    """Text and metadata rendered by the task row widget."""

    label_text: str
    use_markup: bool
    dimmed: bool
    metadata: TaskRowMetadata | None


def build_task_row_display(
    task: Task,
    *,
    show_project: bool,
    show_raw_text: bool,
) -> TaskRowDisplay:
    """Return the text/metadata state needed to render a task row."""
    display_text = task.text if show_raw_text else clean_task_text(task.text)
    escaped = html.escape(display_text)

    if task.done:
        return TaskRowDisplay(
            label_text=f"<s>{escaped}</s>",
            use_markup=True,
            dimmed=True,
            metadata=None,
        )

    metadata = build_task_row_metadata(task, show_project=show_project)
    return TaskRowDisplay(
        label_text=escaped,
        use_markup=True,
        dimmed=False,
        metadata=metadata,
    )


def build_task_row_metadata(
    task: Task,
    *,
    show_project: bool,
) -> TaskRowMetadata | None:
    """Return the active-task metadata shown beneath the main row text."""
    metadata = TaskRowMetadata(
        priority=task.priority,
        due=task.keyvalues.get("due"),
        scheduled=task.keyvalues.get("scheduled"),
        starting=task.keyvalues.get("starting"),
        contexts=task.contexts[:3],
        projects=task.projects[:2] if show_project else (),
    )
    if metadata.is_empty:
        return None
    return metadata
