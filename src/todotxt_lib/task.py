from __future__ import annotations

import dataclasses
import enum
import json
from datetime import date
from pathlib import PurePosixPath
from types import MappingProxyType


class Priority(enum.Enum):
    """Task priority from the todo.txt spec: a single uppercase letter A-Z."""

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    G = "G"
    H = "H"
    I = "I"
    J = "J"
    K = "K"
    L = "L"
    M = "M"
    N = "N"
    O = "O"
    P = "P"
    Q = "Q"
    R = "R"
    S = "S"
    T = "T"
    U = "U"
    V = "V"
    W = "W"
    X = "X"
    Y = "Y"
    Z = "Z"

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Priority):
            return NotImplemented
        return self.value < other.value

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Priority):
            return NotImplemented
        return self.value <= other.value

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Priority):
            return NotImplemented
        return self.value > other.value

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Priority):
            return NotImplemented
        return self.value >= other.value

    def __str__(self) -> str:
        return self.value


def _empty_kv() -> MappingProxyType[str, str]:
    return MappingProxyType({})


def _is_valid_relative_path(relative_path: str) -> bool:
    pure_path = PurePosixPath(relative_path)
    if str(pure_path) in {"", "."} or pure_path.is_absolute():
        return False
    return all(part not in {"", ".", ".."} for part in pure_path.parts)


@dataclasses.dataclass(frozen=True)
class TaskRef:
    """Stable reference to a task stored inside a todo.txt.d directory."""

    relative_path: str
    line_index: int

    @property
    def is_done(self) -> bool:
        """Return whether the referenced task lives inside done.txt.d."""
        return self.relative_path == "done.txt.d" or self.relative_path.startswith(
            "done.txt.d/"
        )

    def to_token(self) -> str:
        """Serialize the ref into a compact string token."""
        return json.dumps(
            {
                "relative_path": self.relative_path,
                "line_index": self.line_index,
            },
            separators=(",", ":"),
        )

    @classmethod
    def from_token(cls, token: str) -> "TaskRef":
        """Parse a serialized ref token."""
        try:
            payload = json.loads(token)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid task token") from exc
        if not isinstance(payload, dict):
            raise ValueError("Invalid task token")
        relative_path = payload.get("relative_path")
        if not isinstance(relative_path, str) or not _is_valid_relative_path(relative_path):
            raise ValueError("Invalid task token")
        try:
            line_index = int(payload["line_index"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Invalid task token") from exc
        if line_index < 0:
            raise ValueError("Invalid task token")
        return cls(
            relative_path=relative_path,
            line_index=line_index,
        )


@dataclasses.dataclass(frozen=True)
class Task:
    """Immutable value object representing a single todo.txt task line."""

    raw: str
    done: bool
    priority: Priority | None
    completion_date: date | None
    creation_date: date | None
    text: str  # Full task description including inline @context and +project markers
    ref: TaskRef | None = None
    projects: tuple[str, ...] = dataclasses.field(default_factory=tuple)
    contexts: tuple[str, ...] = dataclasses.field(default_factory=tuple)
    # MappingProxyType enforces true immutability: mutation raises TypeError at runtime.
    # hash=False because MappingProxyType is not hashable; compare=True (default) so
    # two tasks with different keyvalues are correctly considered unequal.
    keyvalues: MappingProxyType[str, str] = dataclasses.field(
        default_factory=_empty_kv, hash=False
    )
