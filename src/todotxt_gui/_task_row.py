"""Rich two-line task row widget with checkbox, metadata badges, and drag support."""

from __future__ import annotations

import html
import re
from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gdk, GObject, Gtk
from todotxt_lib import Task

from ._ui import RESOURCE_PREFIX
from ._widgets import (
    context_chip,
    due_date_badge,
    priority_dot,
    project_label,
    scheduled_badge,
    starting_badge,
)

# Patterns for stripping metadata tokens from display text
_STRIP_PROJECT_RE = re.compile(r"(?:^|\s)\+\S+")
_STRIP_CONTEXT_RE = re.compile(r"(?:^|\s)@\S+")
_STRIP_KEYVALUE_RE = re.compile(r"(?:^|\s)[a-z]+:[^/\s:][^\s:]*")


def _clean_task_text(text: str) -> str:
    """Strip @contexts, +projects, and key:value pairs from task text."""
    cleaned = _STRIP_KEYVALUE_RE.sub("", text)
    cleaned = _STRIP_PROJECT_RE.sub("", cleaned)
    cleaned = _STRIP_CONTEXT_RE.sub("", cleaned)
    return " ".join(cleaned.split())


@Gtk.Template(resource_path=f"{RESOURCE_PREFIX}/ui/task_row.ui")
class TaskRow(Gtk.ListBoxRow):
    """Rich two-line task row: checkbox + text + metadata badges + delete."""

    __gtype_name__ = "TaskRow"

    check = Gtk.Template.Child()
    text_label = Gtk.Template.Child()
    content_box = Gtk.Template.Child()
    meta_box = Gtk.Template.Child()
    delete_btn = Gtk.Template.Child()

    def __init__(
        self,
        task: Task,
        on_complete: Callable[[Task], None],
        on_delete: Callable[[Task], None],
        *,
        show_project: bool = False,
        show_raw_text: bool = True,
    ) -> None:
        super().__init__()
        self.task = task
        self._on_complete = on_complete
        self._on_delete = on_delete
        self._show_project = show_project
        self._show_raw_text = show_raw_text
        self._populate()

        # Drag source for dropping onto sidebar tags
        drag_source = Gtk.DragSource()
        drag_source.set_actions(Gdk.DragAction.COPY)
        drag_source.connect("prepare", self._on_drag_prepare)
        drag_source.connect("drag-begin", self._on_drag_begin)
        self.add_controller(drag_source)

    def _populate(self) -> None:
        # Checkbox
        self.check.set_active(self.task.done)
        self.check.set_sensitive(not self.task.done)
        if not self.task.done:
            self.check.connect("toggled", self._on_checked)

        # Task text
        display_text = (
            self.task.text if self._show_raw_text else _clean_task_text(self.task.text)
        )
        escaped = html.escape(display_text)
        if self.task.done:
            self.text_label.set_markup(f"<s>{escaped}</s>")
            self.text_label.add_css_class("dim-label")
        else:
            self.text_label.set_label(escaped)
            self.text_label.set_use_markup(True)

        # Metadata row (only for active tasks with metadata)
        if not self.task.done:
            self._populate_metadata()

    def _populate_metadata(self) -> None:
        """Populate the metadata row with priority dot, due badge, context chips."""
        has_priority = self.task.priority is not None
        has_due = "due" in self.task.keyvalues
        has_scheduled = "scheduled" in self.task.keyvalues
        has_starting = "starting" in self.task.keyvalues
        has_contexts = len(self.task.contexts) > 0
        has_projects = self._show_project and len(self.task.projects) > 0

        if not (
            has_priority
            or has_due
            or has_scheduled
            or has_starting
            or has_contexts
            or has_projects
        ):
            return

        self.meta_box.set_visible(True)

        if has_priority and self.task.priority is not None:
            self.meta_box.append(priority_dot(self.task.priority))

        if has_due:
            self.meta_box.append(due_date_badge(self.task.keyvalues["due"]))

        if has_scheduled:
            self.meta_box.append(
                scheduled_badge(self.task.keyvalues["scheduled"]),
            )

        if has_starting:
            self.meta_box.append(
                starting_badge(self.task.keyvalues["starting"]),
            )

        for ctx in self.task.contexts[:3]:
            self.meta_box.append(context_chip(ctx))

        if has_projects:
            for proj in self.task.projects[:2]:
                self.meta_box.append(project_label(proj))

    def _on_drag_prepare(
        self,
        _source: Gtk.DragSource,
        _x: float,
        _y: float,
    ) -> Gdk.ContentProvider | None:
        value = GObject.Value()
        value.init(GObject.TYPE_STRING)
        value.set_string(self.task.raw)
        return Gdk.ContentProvider.new_for_value(value)

    def _on_drag_begin(
        self,
        _source: Gtk.DragSource,
        drag: Gdk.Drag,
    ) -> None:
        icon = Gtk.DragIcon.get_for_drag(drag)
        label = Gtk.Label(label=self.task.text)
        label.add_css_class("drag-icon")
        icon.set_child(label)

    def _on_checked(self, _check: object) -> None:
        self._on_complete(self.task)

    @Gtk.Template.Callback()
    def on_delete_clicked(self, _btn: object) -> None:
        self._on_delete(self.task)
