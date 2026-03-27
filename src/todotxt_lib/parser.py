from __future__ import annotations

import re
from datetime import date
from types import MappingProxyType

from .task import Priority, Task, TaskRef

_PRIORITY_RE = re.compile(r"\(([A-Z])\) ")
_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
_PROJECT_RE = re.compile(r"(?:^|\s)\+(\S+)")
_CONTEXT_RE = re.compile(r"(?:^|\s)@(\S+)")
# Value must not start with '/' to exclude URLs (e.g. http://example.com).
# Neither key nor value may contain whitespace or colons, per the spec.
_KEYVALUE_RE = re.compile(r"(?:^|\s)([a-z]+):([^/\s:][^\s:]*)")


def _parse_date_prefix(text: str) -> tuple[date, str] | None:
    """Parse a leading ISO date token, treating invalid dates as plain text."""
    match = _DATE_RE.match(text)
    if match is None:
        return None
    try:
        parsed = date.fromisoformat(match.group(1))
    except ValueError:
        return None
    return parsed, text[match.end() :].removeprefix(" ")


def serialize_fields(
    done: bool,
    priority: Priority | None,
    completion_date: date | None,
    creation_date: date | None,
    text: str,
) -> str:
    """Build a todo.txt line from individual task fields."""
    parts: list[str] = []
    if done:
        parts.append("x")
    # Priority is only written for incomplete tasks
    if priority and not done:
        parts.append(f"({priority.value})")
    if completion_date:
        parts.append(str(completion_date))
    if creation_date:
        parts.append(str(creation_date))
    if text:
        parts.append(text)
    return " ".join(parts)


def parse_task(line: str, *, ref: TaskRef | None = None) -> Task:
    """Parse a single todo.txt line into a Task.

    Follows the format rules from the todo.txt specification:
    [x] [(A)] [YYYY-MM-DD] [YYYY-MM-DD] task text [@context] [+project] [key:value]
    """
    raw = line
    rest = line
    done = False
    priority: Priority | None = None
    completion_date: date | None = None
    creation_date: date | None = None

    # Completion: must be exactly "x " at the start (lowercase x only)
    if rest.startswith("x "):
        done = True
        rest = rest[2:]

    # Priority: only valid for incomplete tasks, must be the very first token
    if not done:
        m = _PRIORITY_RE.match(rest)
        if m:
            priority = Priority(m.group(1))
            rest = rest[m.end() :]

    # Dates — trailing space is consumed if present, but not required (handles
    # tasks that end with a date and have no description text).
    parsed = _parse_date_prefix(rest)
    if parsed is not None:
        d1, rest = parsed
        if done:
            # For completed tasks: first date is the completion date
            completion_date = d1
            # Optional second date is the creation date
            parsed_second = _parse_date_prefix(rest)
            if parsed_second is not None:
                creation_date, rest = parsed_second
        else:
            creation_date = d1

    text = rest

    projects = tuple(m.group(1) for m in _PROJECT_RE.finditer(text))
    contexts = tuple(m.group(1) for m in _CONTEXT_RE.finditer(text))
    keyvalues = MappingProxyType(
        {m.group(1): m.group(2) for m in _KEYVALUE_RE.finditer(text)}
    )

    return Task(
        raw=raw,
        done=done,
        priority=priority,
        completion_date=completion_date,
        creation_date=creation_date,
        text=text,
        ref=ref,
        projects=projects,
        contexts=contexts,
        keyvalues=keyvalues,
    )


def serialize_task(task: Task) -> str:
    """Serialize a Task back to a todo.txt line."""
    return serialize_fields(
        task.done,
        task.priority,
        task.completion_date,
        task.creation_date,
        task.text,
    )
