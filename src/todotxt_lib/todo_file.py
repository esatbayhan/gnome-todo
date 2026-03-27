"""Compatibility shim for the old todo_file module path."""

from .todo_directory import TodoDirectory

TodoFile = TodoDirectory

__all__ = ["TodoDirectory", "TodoFile"]
