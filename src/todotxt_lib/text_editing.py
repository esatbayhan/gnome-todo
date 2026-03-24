"""Helpers for editing and cleaning todo.txt task text."""

from __future__ import annotations

import enum
import re
from collections.abc import Iterable

from .task import Task


class _Unset(enum.Enum):
    """Sentinel to distinguish 'not provided' from None."""

    TOKEN = 0


_UNSET = _Unset.TOKEN


def rebuild_task_line(
    task: Task,
    *,
    new_text: str | None = None,
    due: str | None | _Unset = _UNSET,
    scheduled: str | None | _Unset = _UNSET,
    starting: str | None | _Unset = _UNSET,
    add_context: str | None = None,
    remove_context: str | None = None,
    add_project: str | None = None,
    remove_project: str | None = None,
) -> str:
    """Reconstruct the task text portion with modifications."""
    text = new_text if new_text is not None else task.text
    text = _remove_prefixed_token(text, "@", remove_context)
    text = _append_missing_prefixed_token(text, "@", add_context)
    text = _remove_prefixed_token(text, "+", remove_project)
    text = _append_missing_prefixed_token(text, "+", add_project)
    text = _replace_keyvalue(text, "due", due)
    text = _replace_keyvalue(text, "scheduled", scheduled)
    text = _replace_keyvalue(text, "starting", starting)
    return text.strip()


def append_missing_task_metadata(
    text: str,
    *,
    contexts: Iterable[str] = (),
    projects: Iterable[str] = (),
    due: str | None = None,
    scheduled: str | None = None,
    starting: str | None = None,
) -> str:
    """Append dialog-selected metadata that is not already present in text."""
    base_text = text.strip()
    parts = [base_text]

    _append_missing_tokens(parts, base_text, "@", contexts)
    _append_missing_tokens(parts, base_text, "+", projects)
    _append_missing_keyvalue(parts, base_text, "due", due)
    _append_missing_keyvalue(parts, base_text, "scheduled", scheduled)
    _append_missing_keyvalue(parts, base_text, "starting", starting)

    return " ".join(part for part in parts if part).strip()


def normalize_tag_input(text: str, prefix: str) -> str:
    """Normalize entry text: strip whitespace and leading prefix characters."""
    return text.strip().lstrip(prefix)


# ── Clean task text ──────────────────────────────────────────────────

_STRIP_PROJECT_RE = re.compile(r"(?:^|\s)\+\S+")
_STRIP_CONTEXT_RE = re.compile(r"(?:^|\s)@\S+")
_STRIP_KEYVALUE_RE = re.compile(r"(?:^|\s)[a-z]+:[^/\s:][^\s:]*")


def clean_task_text(text: str) -> str:
    """Strip @contexts, +projects, and key:value pairs from task text."""
    cleaned = _STRIP_KEYVALUE_RE.sub("", text)
    cleaned = _STRIP_PROJECT_RE.sub("", cleaned)
    cleaned = _STRIP_CONTEXT_RE.sub("", cleaned)
    return " ".join(cleaned.split())


# ── Internal helpers ─────────────────────────────────────────────────


def _remove_prefixed_token(text: str, prefix: str, value: str | None) -> str:
    if not value:
        return text
    return re.sub(rf"\s*{re.escape(prefix)}{re.escape(value)}\b", "", text)


def _append_missing_prefixed_token(text: str, prefix: str, value: str | None) -> str:
    token = f"{prefix}{value}" if value else None
    if token is None or token in text:
        return text
    return f"{text} {token}"


def _replace_keyvalue(
    text: str,
    key: str,
    value: str | None | _Unset,
) -> str:
    if isinstance(value, _Unset):
        return text

    updated = re.sub(rf"\s*{re.escape(key)}:\S+", "", text)
    if value is None:
        return updated
    return f"{updated} {key}:{value}"


def _append_missing_tokens(
    parts: list[str],
    text: str,
    prefix: str,
    items: Iterable[str],
) -> None:
    for item in items:
        token = f"{prefix}{item}"
        if token not in text:
            parts.append(token)


def _append_missing_keyvalue(
    parts: list[str],
    text: str,
    key: str,
    value: str | None,
) -> None:
    if value is None:
        return

    token = f"{key}:{value}"
    if token not in text:
        parts.append(token)
