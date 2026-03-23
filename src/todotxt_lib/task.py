from __future__ import annotations

import dataclasses
import enum
from datetime import date
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


@dataclasses.dataclass(frozen=True)
class Task:
    """Immutable value object representing a single line in todo.txt."""

    raw: str
    done: bool
    priority: Priority | None
    completion_date: date | None
    creation_date: date | None
    text: str  # Full task description including inline @context and +project markers
    projects: tuple[str, ...] = dataclasses.field(default_factory=tuple)
    contexts: tuple[str, ...] = dataclasses.field(default_factory=tuple)
    # MappingProxyType enforces true immutability: mutation raises TypeError at runtime.
    # hash=False because MappingProxyType is not hashable; compare=True (default) so
    # two tasks with different keyvalues are correctly considered unequal.
    keyvalues: MappingProxyType[str, str] = dataclasses.field(
        default_factory=_empty_kv, hash=False
    )
