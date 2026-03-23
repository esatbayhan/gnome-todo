from __future__ import annotations

import os
import tempfile
from pathlib import Path

from .parser import parse_task, serialize_task
from .task import Task


class TodoFile:
    """Manages an ordered list of tasks backed by a todo.txt file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.tasks: list[Task] = []
        self._last_mtime: float = 0.0

    def load(self) -> None:
        """Load tasks from the file. Clears any existing in-memory tasks."""
        if not self.path.exists():
            self.tasks = []
            self._last_mtime = 0.0
            return
        lines = self.path.read_text(encoding="utf-8").splitlines()
        self.tasks = [parse_task(line) for line in lines if line.strip()]
        self._last_mtime = self.path.stat().st_mtime

    def save(self) -> None:
        """Write current tasks back to the file atomically."""
        lines = [serialize_task(task) for task in self.tasks]
        content = "\n".join(lines)
        if content:
            content += "\n"
        # Atomic write: temp file in same directory + os.replace (single rename syscall)
        fd, tmp_path = tempfile.mkstemp(
            dir=self.path.parent,
            suffix=".tmp",
            prefix=".todo-",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.path)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        self._last_mtime = self.path.stat().st_mtime

    def has_external_changes(self) -> bool:
        """Check if the file was modified externally since the last load/save."""
        if not self.path.exists():
            return self._last_mtime != 0.0
        try:
            return self.path.stat().st_mtime != self._last_mtime
        except OSError:
            return False
