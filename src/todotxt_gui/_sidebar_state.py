"""Stable presentation choices for sidebar tag rows."""

from __future__ import annotations

import hashlib

PALETTE: tuple[str, ...] = (
    "blue",
    "orange",
    "red",
    "purple",
    "green",
    "teal",
    "pink",
    "indigo",
    "brown",
    "mint",
)


def project_color(name: str) -> str:
    """Return a stable palette color for a project/context name."""
    digest = hashlib.md5(name.encode("utf-8"), usedforsecurity=False).digest()
    index = int.from_bytes(digest[:4], "big") % len(PALETTE)
    return PALETTE[index]
