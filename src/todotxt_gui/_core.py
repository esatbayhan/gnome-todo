"""Pure-Python helpers shared between app.py and tests."""

from __future__ import annotations

import os
from pathlib import Path

from todotxt_lib import sort_key
from todotxt_lib import todo_dir_path as _lib_todo_dir_path

from ._config import get_todo_dir

# Re-export so existing imports from ._core keep working.
__all__ = ["todo_dir_path", "has_configured_dir", "sort_key"]


def todo_dir_path() -> Path:
    """Resolve the configured todo.txt.d directory."""
    return _lib_todo_dir_path(config_dir=get_todo_dir())


def has_configured_dir() -> bool:
    """Return True if a todo directory is configured via env vars or config file."""
    return bool(os.environ.get("TODO_DIR") or get_todo_dir())
