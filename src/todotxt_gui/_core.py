"""Pure-Python helpers shared between app.py and tests."""

from __future__ import annotations

import os
from pathlib import Path

from todotxt_lib import done_file_path as _lib_done_path
from todotxt_lib import sort_key
from todotxt_lib import todo_file_path as _lib_todo_path

from ._config import get_todo_dir

# Re-export so existing imports from ._core keep working.
__all__ = ["todo_file_path", "done_file_path", "has_configured_dir", "sort_key"]


def todo_file_path() -> Path:
    """Resolve todo.txt path, including the GUI config-file fallback."""
    return _lib_todo_path(config_dir=get_todo_dir())


def done_file_path() -> Path:
    """Resolve done.txt path, including the GUI config-file fallback."""
    return _lib_done_path(config_dir=get_todo_dir())


def has_configured_dir() -> bool:
    """Return True if a todo directory is configured via env vars or config file."""
    return bool(
        os.environ.get("TODO_FILE")
        or os.environ.get("TODO_DIR")
        or os.environ.get("TODO_DONE_FILE")
        or get_todo_dir()
    )
