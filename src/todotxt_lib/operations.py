from __future__ import annotations

from datetime import date

from .parser import parse_task, serialize_fields
from .task import Priority, Task
from .todo_file import TodoFile


def _replace_in_file(file: TodoFile, old_task: Task, new_task: Task) -> None:
    """Replace old_task with new_task in the file's task list."""
    idx = file.tasks.index(old_task)
    file.tasks[idx] = new_task


def add_task(
    file: TodoFile,
    text: str,
    creation_date: date | None = None,
) -> Task:
    """Add a new task with an auto-prepended creation date."""
    effective_date = creation_date if creation_date is not None else date.today()
    task = parse_task(f"{effective_date} {text}")
    file.tasks.append(task)
    return task


def complete_task(
    file: TodoFile,
    task: Task,
    completion_date: date | None = None,
) -> Task:
    """Mark a task as done in the file. Priority is discarded on completion."""
    effective_date = completion_date if completion_date is not None else date.today()
    raw = serialize_fields(True, None, effective_date, task.creation_date, task.text)
    new_task = Task(
        raw=raw,
        done=True,
        priority=None,
        completion_date=effective_date,
        creation_date=task.creation_date,
        text=task.text,
        projects=task.projects,
        contexts=task.contexts,
        keyvalues=task.keyvalues,
    )
    _replace_in_file(file, task, new_task)
    return new_task


def uncomplete_task(file: TodoFile, task: Task) -> Task:
    """Mark a completed task as not done. Completion date is removed."""
    if not task.done:
        raise ValueError("Task is not completed")
    raw = serialize_fields(False, None, None, task.creation_date, task.text)
    new_task = Task(
        raw=raw,
        done=False,
        priority=None,
        completion_date=None,
        creation_date=task.creation_date,
        text=task.text,
        projects=task.projects,
        contexts=task.contexts,
        keyvalues=task.keyvalues,
    )
    _replace_in_file(file, task, new_task)
    return new_task


def delete_task(file: TodoFile, task: Task) -> None:
    """Remove a task from the file's task list."""
    file.tasks.remove(task)


def set_priority(file: TodoFile, task: Task, priority: Priority) -> Task:
    """Set priority on a task in the file.

    Raises ValueError if the task is already completed (completed tasks have
    no priority field).
    """
    if task.done:
        raise ValueError("Cannot set priority on a completed task")
    raw = serialize_fields(
        False, priority, task.completion_date, task.creation_date, task.text
    )
    new_task = Task(
        raw=raw,
        done=task.done,
        priority=priority,
        completion_date=task.completion_date,
        creation_date=task.creation_date,
        text=task.text,
        projects=task.projects,
        contexts=task.contexts,
        keyvalues=task.keyvalues,
    )
    _replace_in_file(file, task, new_task)
    return new_task


def deprioritize(file: TodoFile, task: Task) -> Task:
    """Remove priority from a task in the file."""
    raw = serialize_fields(
        task.done, None, task.completion_date, task.creation_date, task.text
    )
    new_task = Task(
        raw=raw,
        done=task.done,
        priority=None,
        completion_date=task.completion_date,
        creation_date=task.creation_date,
        text=task.text,
        projects=task.projects,
        contexts=task.contexts,
        keyvalues=task.keyvalues,
    )
    _replace_in_file(file, task, new_task)
    return new_task


def replace_task(file: TodoFile, old_task: Task, new_line: str) -> Task:
    """Replace old_task in the file with a task parsed from new_line."""
    new_task = parse_task(new_line)
    _replace_in_file(file, old_task, new_task)
    return new_task


def archive(todo: TodoFile, done: TodoFile) -> int:
    """Move all completed tasks from todo to done. Returns the count moved."""
    completed = [t for t in todo.tasks if t.done]
    done.tasks.extend(completed)
    todo.tasks = [t for t in todo.tasks if not t.done]
    return len(completed)


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
    for t in tasks:
        seen.update(t.projects)
    return sorted(seen)


def all_contexts(tasks: list[Task]) -> list[str]:
    """Return a sorted list of all unique context names across tasks."""
    seen: set[str] = set()
    for t in tasks:
        seen.update(t.contexts)
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
    """Filter tasks by any combination of text, project, context, completion, priority.

    text: case-insensitive substring match against the task description.
    Multiple text terms can be applied by calling filter_tasks in a chain.
    """
    result = tasks
    if text is not None:
        lower = text.lower()
        result = [t for t in result if lower in t.text.lower()]
    if project is not None:
        result = [t for t in result if project in t.projects]
    if context is not None:
        result = [t for t in result if context in t.contexts]
    if done is not None:
        result = [t for t in result if t.done == done]
    if priority is not None:
        result = [t for t in result if t.priority == priority]
    return result
