"""Centralized path resolution for todo.txt and done.txt files.

All frontends (CLI, TUI, GUI) share this logic.  The optional *config_dir*
parameter lets the GUI inject its persistent configuration directory so that
the precedence chain becomes:

    $TODO_FILE > $TODO_DIR > config_dir > ~/todo.txt
"""

from __future__ import annotations

import os
from pathlib import Path


def todo_file_path(*, config_dir: Path | None = None) -> Path:
    """Resolve the path to todo.txt.

    Precedence: $TODO_FILE > $TODO_DIR/todo.txt > config_dir/todo.txt > ~/todo.txt
    """
    if todo_file := os.environ.get("TODO_FILE"):
        return Path(todo_file)
    if todo_dir := os.environ.get("TODO_DIR"):
        return Path(todo_dir) / "todo.txt"
    if config_dir is not None:
        return config_dir / "todo.txt"
    return Path.home() / "todo.txt"


def done_file_path(*, config_dir: Path | None = None) -> Path:
    """Resolve the path to done.txt.

    Precedence: $TODO_DONE_FILE > $TODO_DIR/done.txt > config_dir/done.txt > ~/done.txt
    """
    if done_file := os.environ.get("TODO_DONE_FILE"):
        return Path(done_file)
    if todo_dir := os.environ.get("TODO_DIR"):
        return Path(todo_dir) / "done.txt"
    if config_dir is not None:
        return config_dir / "done.txt"
    return Path.home() / "done.txt"
