from __future__ import annotations

from datetime import date

from .parser import serialize_fields
from .task import Priority, Task, TaskRef
from .todo_directory import TodoDirectory


def _task_ref(task: Task) -> TaskRef:
    if task.ref is None:
        raise ValueError("Task is not backed by a todo.txt.d file")
    return task.ref


def add_task(
    directory: TodoDirectory,
    text: str,
    creation_date: date | None = None,
) -> Task:
    """Add a new active task to the todo.txt.d root."""
    return directory.add_task(text, creation_date=creation_date)


def complete_task(
    directory: TodoDirectory,
    task: Task,
    completion_date: date | None = None,
) -> Task:
    """Mark a task as done and move it into done.txt.d."""
    completed = directory.complete_task(
        _task_ref(task),
        completion_date=completion_date,
    )
    if completed is None:
        raise ValueError("Task is missing or already completed")
    return completed


def uncomplete_task(directory: TodoDirectory, task: Task) -> Task:
    """Move a completed task back into the active directory."""
    result = directory.uncomplete_task(_task_ref(task))
    if result is None:
        raise ValueError("Task is missing or not completed")
    return result


def delete_task(directory: TodoDirectory, task: Task) -> None:
    """Delete a task from storage."""
    if not directory.delete_task(_task_ref(task)):
        raise ValueError("Task is missing")


def set_priority(
    directory: TodoDirectory,
    task: Task,
    priority: Priority,
) -> Task:
    """Set priority on an active task."""
    if task.done:
        raise ValueError("Cannot set priority on a completed task")
    raw = serialize_fields(
        False,
        priority,
        task.completion_date,
        task.creation_date,
        task.text,
    )
    updated = directory.update_task(_task_ref(task), raw)
    if updated is None:
        raise ValueError("Task is missing")
    return updated


def deprioritize(directory: TodoDirectory, task: Task) -> Task:
    """Remove priority from a task."""
    raw = serialize_fields(
        task.done,
        None,
        task.completion_date,
        task.creation_date,
        task.text,
    )
    updated = directory.update_task(_task_ref(task), raw)
    if updated is None:
        raise ValueError("Task is missing")
    return updated


def replace_task(directory: TodoDirectory, old_task: Task, new_line: str) -> Task:
    """Replace a task with a fully serialized todo.txt line."""
    updated = directory.update_task(_task_ref(old_task), new_line)
    if updated is None:
        raise ValueError("Task is missing")
    return updated


def sort_key(task: Task) -> tuple[int, str, str]:
    """Sort key: active before done, by priority (A first), then alphabetically."""
    pri = task.priority.value if task.priority is not None else "\xff"
    return (1 if task.done else 0, pri, task.text.lower())


def sort_tasks(tasks: list[Task]) -> list[Task]:
    """Return tasks sorted by: active before done, priority, then alphabetically."""
    return sorted(tasks, key=sort_key)


def all_projects(tasks: list[Task]) -> list[str]:
    """Return a sorted list of all unique project names across tasks."""
    seen: set[str] = set()
    for task in tasks:
        seen.update(task.projects)
    return sorted(seen)


def all_contexts(tasks: list[Task]) -> list[str]:
    """Return a sorted list of all unique context names across tasks."""
    seen: set[str] = set()
    for task in tasks:
        seen.update(task.contexts)
    return sorted(seen)


def filter_tasks(
    tasks: list[Task],
    *,
    text: str | None = None,
    project: str | None = None,
    context: str | None = None,
    done: bool | None = None,
    priority: Priority | None = None,
) -> list[Task]:
    """Filter tasks by any combination of text, project, context, completion, priority."""
    result = tasks
    if text is not None:
        lower = text.lower()
        result = [task for task in result if lower in task.text.lower()]
    if project is not None:
        result = [task for task in result if project in task.projects]
    if context is not None:
        result = [task for task in result if context in task.contexts]
    if done is not None:
        result = [task for task in result if task.done == done]
    if priority is not None:
        result = [task for task in result if task.priority == priority]
    return result
