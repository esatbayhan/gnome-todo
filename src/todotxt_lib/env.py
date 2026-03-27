"""Centralized path resolution for todo.txt.d directories.

All frontends (CLI, TUI, GUI) share this logic.  The optional *config_dir*
parameter lets the GUI inject its persistent configuration directory so that
the precedence chain becomes:

    $TODO_DIR > config_dir > ~/todo.txt.d
"""

from __future__ import annotations

import os
from pathlib import Path


def todo_dir_path(*, config_dir: Path | None = None) -> Path:
    """Resolve the path to the todo.txt.d root directory."""
    if todo_dir := os.environ.get("TODO_DIR"):
        return Path(todo_dir)
    if config_dir is not None:
        return config_dir
    return Path.home() / "todo.txt.d"
