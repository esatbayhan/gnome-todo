"""Non-GTK helpers for task mutation workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from .operations import (
    add_task,
    complete_task,
    delete_task,
    deprioritize,
    replace_task,
    set_priority,
    uncomplete_task,
)
from .task import Priority, Task
from .text_editing import rebuild_task_line
from .todo_file import TodoFile

SourceKind = Literal["todo", "done"]
MutationStatus = Literal["changed", "missing", "noop"]
TagKind = Literal["project", "context"]


@dataclass(frozen=True)
class TaskLocation:
    """Task located in one of the backing files."""

    task: Task
    source_kind: SourceKind


@dataclass(frozen=True)
class MutationOutcome:
    """Result of a task mutation attempt."""

    status: MutationStatus
    task: Task | None = None
    save_todo: bool = False
    save_done: bool = False

    @property
    def changed(self) -> bool:
        """Return whether the mutation changed any task data."""
        return self.status == "changed"


def find_task_by_raw(
    todo_file: TodoFile,
    done_file: TodoFile,
    raw: str,
) -> TaskLocation | None:
    """Locate a task by raw line in either backing file."""
    for task in todo_file.tasks:
        if task.raw == raw:
            return TaskLocation(task=task, source_kind="todo")
    for task in done_file.tasks:
        if task.raw == raw:
            return TaskLocation(task=task, source_kind="done")
    return None


def add_task_with_priority(
    todo_file: TodoFile,
    text: str,
    *,
    creation_date: date,
    priority: Priority | None = None,
) -> MutationOutcome:
    """Add a new task and optional priority in the todo file."""
    new_task = add_task(todo_file, text, creation_date)
    if priority is not None:
        new_task = set_priority(todo_file, new_task, priority)
    return MutationOutcome(
        status="changed",
        task=new_task,
        save_todo=True,
    )


def complete_task_by_raw(
    todo_file: TodoFile,
    done_file: TodoFile,
    raw: str,
    *,
    completion_date: date,
) -> MutationOutcome:
    """Complete an active todo task if it still exists."""
    located = find_task_by_raw(todo_file, done_file, raw)
    if located is None or located.source_kind != "todo":
        return MutationOutcome(status="missing")

    new_task = complete_task(todo_file, located.task, completion_date)
    return MutationOutcome(
        status="changed",
        task=new_task,
        save_todo=True,
    )


def delete_task_by_raw(
    todo_file: TodoFile,
    done_file: TodoFile,
    raw: str,
) -> MutationOutcome:
    """Delete a task from whichever file currently owns it."""
    located = find_task_by_raw(todo_file, done_file, raw)
    if located is None:
        return MutationOutcome(status="missing")

    target_file = todo_file if located.source_kind == "todo" else done_file
    delete_task(target_file, located.task)
    return MutationOutcome(
        status="changed",
        save_todo=located.source_kind == "todo",
        save_done=located.source_kind == "done",
    )


def add_tag_to_task(
    todo_file: TodoFile,
    done_file: TodoFile,
    raw: str,
    *,
    tag_name: str,
    tag_kind: TagKind,
) -> MutationOutcome:
    """Add a context/project to a task unless it is already present."""
    located = find_task_by_raw(todo_file, done_file, raw)
    if located is None:
        return MutationOutcome(status="missing")

    if tag_kind == "project" and tag_name in located.task.projects:
        return MutationOutcome(status="noop")
    if tag_kind == "context" and tag_name in located.task.contexts:
        return MutationOutcome(status="noop")

    new_line = (
        rebuild_task_line(located.task, add_project=tag_name)
        if tag_kind == "project"
        else rebuild_task_line(located.task, add_context=tag_name)
    )
    target_file = todo_file if located.source_kind == "todo" else done_file
    new_task = replace_task(target_file, located.task, new_line)
    return MutationOutcome(
        status="changed",
        task=new_task,
        save_todo=located.source_kind == "todo",
        save_done=located.source_kind == "done",
    )


def update_task_from_detail(
    todo_file: TodoFile,
    done_file: TodoFile,
    raw: str,
    new_line: str,
) -> MutationOutcome:
    """Apply a detail-panel task update or priority change."""
    located = find_task_by_raw(todo_file, done_file, raw)
    if located is None:
        return MutationOutcome(status="missing")

    if new_line.startswith("__priority__:"):
        if located.source_kind != "todo":
            return MutationOutcome(status="noop")
        pri_str = new_line.split(":", 1)[1]
        new_task = (
            set_priority(todo_file, located.task, Priority(pri_str))
            if pri_str
            else deprioritize(todo_file, located.task)
        )
        return MutationOutcome(
            status="changed",
            task=new_task,
            save_todo=True,
        )

    target_file = todo_file if located.source_kind == "todo" else done_file
    new_task = replace_task(target_file, located.task, new_line)
    return MutationOutcome(
        status="changed",
        task=new_task,
        save_todo=located.source_kind == "todo",
        save_done=located.source_kind == "done",
    )


def uncomplete_task_by_raw(
    todo_file: TodoFile,
    done_file: TodoFile,
    raw: str,
) -> MutationOutcome:
    """Uncomplete a task from either backing file."""
    located = find_task_by_raw(todo_file, done_file, raw)
    if located is None:
        return MutationOutcome(status="missing")

    if located.source_kind == "done":
        new_task = uncomplete_task(done_file, located.task)
        delete_task(done_file, new_task)
        todo_file.tasks.append(new_task)
        return MutationOutcome(
            status="changed",
            task=new_task,
            save_todo=True,
            save_done=True,
        )

    new_task = uncomplete_task(todo_file, located.task)
    return MutationOutcome(
        status="changed",
        task=new_task,
        save_todo=True,
    )
