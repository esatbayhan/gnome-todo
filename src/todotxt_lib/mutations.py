"""Non-GTK helpers for task mutation workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from .operations import deprioritize, replace_task, set_priority
from .parser import serialize_fields
from .task import Priority, Task, TaskRef
from .text_editing import rebuild_task_line
from .todo_directory import TodoDirectory

SourceKind = Literal["todo", "done"]
MutationStatus = Literal["changed", "missing", "noop"]
TagKind = Literal["project", "context"]


@dataclass(frozen=True)
class TaskLocation:
    """Task located in one of the backing storage areas."""

    task: Task
    source_kind: SourceKind


@dataclass(frozen=True)
class MutationOutcome:
    """Result of a task mutation attempt."""

    status: MutationStatus
    task: Task | None = None

    @property
    def changed(self) -> bool:
        """Return whether the mutation changed any task data."""
        return self.status == "changed"


def find_task_by_ref(
    directory: TodoDirectory,
    ref: TaskRef,
) -> TaskLocation | None:
    """Locate a task by stable storage reference."""
    task = directory.find_task(ref)
    if task is None or task.ref is None:
        return None
    return TaskLocation(
        task=task,
        source_kind="done" if task.ref.is_done else "todo",
    )


def add_task_with_priority(
    directory: TodoDirectory,
    text: str,
    *,
    creation_date: date,
    priority: Priority | None = None,
) -> MutationOutcome:
    """Add a new task and optional priority in the active directory."""
    new_task = directory.add_task(
        text,
        creation_date=creation_date,
        priority=priority,
    )
    return MutationOutcome(status="changed", task=new_task)


def complete_task_by_ref(
    directory: TodoDirectory,
    ref: TaskRef,
    *,
    completion_date: date,
) -> MutationOutcome:
    """Complete an active task if it still exists."""
    located = find_task_by_ref(directory, ref)
    if located is None or located.source_kind != "todo":
        return MutationOutcome(status="missing")

    new_task = directory.complete_task(ref, completion_date=completion_date)
    if new_task is None:
        return MutationOutcome(status="missing")
    return MutationOutcome(status="changed", task=new_task)


def delete_task_by_ref(
    directory: TodoDirectory,
    ref: TaskRef,
) -> MutationOutcome:
    """Delete a task from whichever area currently owns it."""
    if not directory.delete_task(ref):
        return MutationOutcome(status="missing")
    return MutationOutcome(status="changed")


def add_tag_to_task(
    directory: TodoDirectory,
    ref: TaskRef,
    *,
    tag_name: str,
    tag_kind: TagKind,
) -> MutationOutcome:
    """Add a context/project to a task unless it is already present."""
    located = find_task_by_ref(directory, ref)
    if located is None:
        return MutationOutcome(status="missing")

    if tag_kind == "project" and tag_name in located.task.projects:
        return MutationOutcome(status="noop")
    if tag_kind == "context" and tag_name in located.task.contexts:
        return MutationOutcome(status="noop")

    new_text = (
        rebuild_task_line(located.task, add_project=tag_name)
        if tag_kind == "project"
        else rebuild_task_line(located.task, add_context=tag_name)
    )
    new_raw = _serialize_with_existing_prefix(located.task, new_text)
    new_task = replace_task(directory, located.task, new_raw)
    return MutationOutcome(status="changed", task=new_task)


def update_task_from_detail(
    directory: TodoDirectory,
    ref: TaskRef,
    new_line: str,
) -> MutationOutcome:
    """Apply a detail-panel task update or priority change."""
    located = find_task_by_ref(directory, ref)
    if located is None:
        return MutationOutcome(status="missing")

    if new_line.startswith("__priority__:"):
        if located.source_kind != "todo":
            return MutationOutcome(status="noop")
        pri_str = new_line.split(":", 1)[1]
        new_task = (
            set_priority(directory, located.task, Priority(pri_str))
            if pri_str
            else deprioritize(directory, located.task)
        )
        return MutationOutcome(status="changed", task=new_task)

    new_raw = _serialize_with_existing_prefix(located.task, new_line)
    new_task = replace_task(directory, located.task, new_raw)
    return MutationOutcome(status="changed", task=new_task)


def uncomplete_task_by_ref(
    directory: TodoDirectory,
    ref: TaskRef,
) -> MutationOutcome:
    """Uncomplete a task if it still exists."""
    located = find_task_by_ref(directory, ref)
    if located is None:
        return MutationOutcome(status="missing")

    new_task = directory.uncomplete_task(ref)
    if new_task is None:
        return MutationOutcome(status="missing")
    return MutationOutcome(status="changed", task=new_task)


def _serialize_with_existing_prefix(task: Task, new_text: str) -> str:
    return serialize_fields(
        task.done,
        None if task.done else task.priority,
        task.completion_date,
        task.creation_date,
        new_text,
    )
