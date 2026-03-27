from __future__ import annotations

import os
import tempfile
from datetime import date
from pathlib import Path, PurePosixPath

from .parser import parse_task, serialize_fields
from .task import Priority, Task, TaskRef


class TodoDirectory:
    """Manage tasks stored inside a todo.txt.d directory."""

    def __init__(
        self,
        root_dir: Path,
        *,
        auto_normalize_multi_task_files: bool = True,
    ) -> None:
        self.root_dir = root_dir
        self.auto_normalize_multi_task_files = auto_normalize_multi_task_files
        self.tasks: list[Task] = []
        self._last_snapshot: dict[str, tuple[bool, bool, int, int]] = {}

    @property
    def done_dir(self) -> Path:
        """Return the done.txt.d subdirectory path."""
        return self.root_dir / "done.txt.d"

    def load(self) -> None:
        """Reload every active and archived task from disk."""
        active_paths = self._task_files(self.root_dir)
        done_paths = self._task_files(self.done_dir)

        tasks: list[Task] = []
        for path in [*active_paths, *done_paths]:
            relative_path = path.relative_to(self.root_dir).as_posix()
            for line_index, line in enumerate(self._read_task_lines(path)):
                tasks.append(
                    parse_task(
                        line,
                        ref=TaskRef(relative_path=relative_path, line_index=line_index),
                    )
                )

        self.tasks = tasks
        self._last_snapshot = self._snapshot()

    def has_external_changes(self) -> bool:
        """Return whether the root directory contents changed since the last load."""
        return self._snapshot() != self._last_snapshot

    def find_task(self, ref: TaskRef) -> Task | None:
        """Return the task matching *ref*, if it still exists."""
        return next((task for task in self.tasks if task.ref == ref), None)

    def find_task_fuzzy(self, ref: TaskRef, *, raw: str | None = None) -> Task | None:
        """Best-effort fallback lookup for task selections after line shifts."""
        task = self.find_task(ref)
        if task is not None or raw is None:
            return task

        siblings = [
            item
            for item in self.tasks
            if item.ref is not None and item.ref.relative_path == ref.relative_path
        ]
        matches = [item for item in siblings if item.raw == raw]
        if len(matches) == 1:
            return matches[0]
        return None

    def add_task(
        self,
        text: str,
        *,
        creation_date: date | None = None,
        priority: Priority | None = None,
    ) -> Task:
        """Create and persist a new active task in its own file."""
        self._ensure_directories()
        effective_date = date.today() if creation_date is None else creation_date
        raw = serialize_fields(
            False,
            priority,
            None,
            effective_date,
            text,
        )
        created_path = self._create_single_task_file(self.root_dir, raw)
        created_ref = self._ref_for_path(created_path)
        self.load()
        task = self.find_task(created_ref)
        assert task is not None
        return task

    def update_task(self, ref: TaskRef, new_raw: str) -> Task | None:
        """Replace one task line, normalizing multi-task files when configured."""
        working_ref = self._normalize_ref_if_needed(ref)
        if working_ref is None:
            return None

        path = self._task_path_from_ref(working_ref)
        if path is None:
            return None
        lines = self._read_task_lines(path)
        if working_ref.line_index >= len(lines):
            return None

        lines[working_ref.line_index] = new_raw
        self._write_task_lines(path, lines)
        self.load()
        return self.find_task(working_ref)

    def delete_task(self, ref: TaskRef) -> bool:
        """Delete the task referenced by *ref*."""
        working_ref = self._normalize_ref_if_needed(ref)
        if working_ref is None:
            return False

        path = self._task_path_from_ref(working_ref)
        if path is None:
            return False
        lines = self._read_task_lines(path)
        if working_ref.line_index >= len(lines):
            return False

        del lines[working_ref.line_index]
        self._write_task_lines(path, lines)
        self.load()
        return True

    def complete_task(
        self,
        ref: TaskRef,
        *,
        completion_date: date | None = None,
    ) -> Task | None:
        """Archive an active task into done.txt.d with a completion marker."""
        working_ref = self._normalize_ref_if_needed(ref)
        if working_ref is None:
            return None

        task = self.find_task(working_ref)
        if task is None or task.done:
            return None

        source_path = self._task_path_from_ref(working_ref)
        if source_path is None:
            return None
        lines = self._read_task_lines(source_path)
        if working_ref.line_index >= len(lines):
            return None

        effective_date = date.today() if completion_date is None else completion_date
        archived_raw = serialize_fields(
            True,
            None,
            effective_date,
            task.creation_date,
            task.text,
        )

        if len(lines) == 1:
            destination_path = self.done_dir / source_path.name
            self._move_single_task_file(source_path, destination_path, archived_raw)
            target_ref = self._ref_for_path(destination_path)
        else:
            del lines[working_ref.line_index]
            self._write_task_lines(source_path, lines)
            destination_path = self._create_single_task_file(self.done_dir, archived_raw)
            target_ref = self._ref_for_path(destination_path)

        self.load()
        return self.find_task(target_ref)

    def uncomplete_task(self, ref: TaskRef) -> Task | None:
        """Move a completed task back into the active directory."""
        working_ref = self._normalize_ref_if_needed(ref)
        if working_ref is None:
            return None

        task = self.find_task(working_ref)
        if task is None or not task.done:
            return None

        source_path = self._task_path_from_ref(working_ref)
        if source_path is None:
            return None
        lines = self._read_task_lines(source_path)
        if working_ref.line_index >= len(lines):
            return None

        active_raw = serialize_fields(
            False,
            None,
            None,
            task.creation_date,
            task.text,
        )

        if len(lines) == 1 and working_ref.is_done:
            destination_path = self.root_dir / source_path.name
            self._move_single_task_file(source_path, destination_path, active_raw)
            target_ref = self._ref_for_path(destination_path)
        else:
            del lines[working_ref.line_index]
            self._write_task_lines(source_path, lines)
            destination_path = self._create_single_task_file(self.root_dir, active_raw)
            target_ref = self._ref_for_path(destination_path)

        self.load()
        return self.find_task(target_ref)

    def _normalize_ref_if_needed(self, ref: TaskRef) -> TaskRef | None:
        """Split multi-task files into single-task files when configured."""
        path = self._task_path_from_ref(ref)
        if path is None:
            return None

        lines = self._read_task_lines(path)
        if ref.line_index >= len(lines):
            return None
        if len(lines) <= 1 or not self.auto_normalize_multi_task_files:
            return ref

        mapping = self._normalize_file(path, lines)
        normalized_ref = mapping.get(ref.line_index)
        self.load()
        return normalized_ref

    def _normalize_file(
        self,
        path: Path,
        lines: list[str],
    ) -> dict[int, TaskRef]:
        target_dir = path.parent
        mapping: dict[int, TaskRef] = {}
        for line_index, line in enumerate(lines):
            created_path = self._create_single_task_file(target_dir, line)
            mapping[line_index] = self._ref_for_path(created_path)
        path.unlink()
        return mapping

    def _move_single_task_file(
        self,
        source_path: Path,
        destination_path: Path,
        line: str,
    ) -> None:
        if destination_path.exists():
            raise FileExistsError(f"Destination task file already exists: {destination_path}")
        self._write_task_lines(destination_path, [line])
        source_path.unlink()

    def _create_single_task_file(self, directory: Path, line: str) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        prefix = self._task_filename_prefix(directory)
        next_index = self._next_task_index(directory, prefix)
        while True:
            candidate = directory / f"{prefix}-{next_index:06d}.txt"
            try:
                self._write_new_task_lines(candidate, [line])
                return candidate
            except FileExistsError:
                next_index += 1

    def _task_files(self, directory: Path) -> list[Path]:
        if not directory.exists() or not directory.is_dir():
            return []
        return sorted(path for path in directory.iterdir() if self._is_task_file(path))

    def _task_filename_prefix(self, directory: Path) -> str:
        if directory.resolve(strict=False) == self.done_dir.resolve(strict=False):
            return "done"
        return "task"

    def _next_task_index(self, directory: Path, prefix: str) -> int:
        highest = 0
        for path in directory.glob(f"{prefix}-*.txt"):
            suffix = path.stem.removeprefix(f"{prefix}-")
            if suffix.isdigit():
                highest = max(highest, int(suffix))
        return highest + 1

    def _path_from_relative(self, relative_path: str) -> Path | None:
        pure_path = PurePosixPath(relative_path)
        if str(pure_path) in {"", "."} or pure_path.is_absolute():
            return None
        if any(part in {"", ".", ".."} for part in pure_path.parts):
            return None

        candidate = self.root_dir.joinpath(*pure_path.parts)
        return candidate if self._is_within_root(candidate) else None

    def _ref_for_path(self, path: Path, *, line_index: int = 0) -> TaskRef:
        return TaskRef(
            relative_path=path.relative_to(self.root_dir).as_posix(),
            line_index=line_index,
        )

    def _ensure_directories(self) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.done_dir.mkdir(parents=True, exist_ok=True)

    def _task_path_from_ref(self, ref: TaskRef) -> Path | None:
        if ref.line_index < 0:
            return None
        path = self._path_from_relative(ref.relative_path)
        if path is None or not self._is_task_file(path):
            return None
        return path

    def _is_task_file(self, path: Path) -> bool:
        if path.suffix != ".txt" or path.is_symlink() or not path.is_file():
            return False
        return self._is_within_root(path)

    def _is_within_root(self, path: Path) -> bool:
        try:
            resolved_root = self.root_dir.resolve(strict=False)
            resolved_path = path.resolve(strict=False)
        except OSError:
            return False
        try:
            resolved_path.relative_to(resolved_root)
        except ValueError:
            return False
        return True

    def _read_task_lines(self, path: Path) -> list[str]:
        if not path.exists():
            return []
        return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _write_task_lines(self, path: Path, lines: list[str]) -> None:
        if path.is_symlink() or not self._is_within_root(path):
            raise OSError(f"Refusing to write outside todo directory: {path}")
        if not lines:
            if path.exists():
                path.unlink()
            return

        path.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join(lines) + "\n"
        fd, tmp_path = tempfile.mkstemp(
            dir=path.parent,
            suffix=".tmp",
            prefix=".todo-",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, path)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def _write_new_task_lines(self, path: Path, lines: list[str]) -> None:
        if path.is_symlink() or not self._is_within_root(path):
            raise OSError(f"Refusing to write outside todo directory: {path}")
        if not lines:
            raise ValueError("Expected at least one task line when creating a task file")

        path.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join(lines) + "\n"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            try:
                path.unlink()
            except OSError:
                pass
            raise

    def _snapshot(self) -> dict[str, tuple[bool, bool, int, int]]:
        snapshot: dict[str, tuple[bool, bool, int, int]] = {
            ".": self._path_signature(self.root_dir),
            "done.txt.d": self._path_signature(self.done_dir),
        }
        for path in self._task_files(self.root_dir):
            snapshot[path.relative_to(self.root_dir).as_posix()] = self._path_signature(path)
        for path in self._task_files(self.done_dir):
            snapshot[path.relative_to(self.root_dir).as_posix()] = self._path_signature(path)
        return snapshot

    def _path_signature(self, path: Path) -> tuple[bool, bool, int, int]:
        if not path.exists():
            return (False, False, 0, 0)
        stat = path.stat()
        return (True, path.is_dir(), stat.st_mtime_ns, stat.st_size)
