"""Rich two-line task row widget with checkbox, metadata badges, and drag support."""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Pango", "1.0")
from gi.repository import Gdk, GObject, Gtk, Pango
from todotxt_lib import Task

from ._task_row_state import build_task_row_display
from ._ui import RESOURCE_PREFIX
from ._widgets import (
    context_chip,
    due_date_badge,
    priority_dot,
    project_label,
    scheduled_badge,
    starting_badge,
)


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
        self.add_css_class("task-row")
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

        display = build_task_row_display(
            self.task,
            show_project=self._show_project,
            show_raw_text=self._show_raw_text,
        )
        self.text_label.set_label(display.label_text)
        self.text_label.set_use_markup(display.use_markup)
        if display.dimmed:
            self.text_label.add_css_class("dim-label")

        if display.metadata is None:
            return

        self.meta_box.set_visible(True)

        if display.metadata.priority is not None:
            self.meta_box.append(priority_dot(display.metadata.priority))

        if display.metadata.due is not None:
            self.meta_box.append(due_date_badge(display.metadata.due))

        if display.metadata.scheduled is not None:
            self.meta_box.append(scheduled_badge(display.metadata.scheduled))

        if display.metadata.starting is not None:
            self.meta_box.append(starting_badge(display.metadata.starting))

        for ctx in display.metadata.contexts:
            self.meta_box.append(context_chip(ctx))

        for proj in display.metadata.projects:
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
        icon.add_css_class("drag-icon-root")

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        box.add_css_class("drag-icon")
        box.add_css_class("task-row-box")
        box.set_overflow(Gtk.Overflow.HIDDEN)

        label = Gtk.Label(label=self.task.text, xalign=0.0)
        label.add_css_class("drag-icon-label")
        label.add_css_class("task-row-title")
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_max_width_chars(36)
        box.append(label)

        icon.set_child(box)

    def _on_checked(self, _check: object) -> None:
        self._on_complete(self.task)

    @Gtk.Template.Callback()
    def on_delete_clicked(self, _btn: object) -> None:
        self._on_delete(self.task)
