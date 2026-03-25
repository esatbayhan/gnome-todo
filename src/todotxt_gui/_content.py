"""Collapsible task section widget."""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk
from todotxt_lib import Task

from ._core import sort_key
from ._task_row import TaskRow


class TaskSection(Gtk.Box):
    """A collapsible group of tasks under a section header."""

    def __init__(
        self,
        title: str,
        tasks: list[Task],
        on_complete: Callable[[Task], None],
        on_delete: Callable[[Task], None],
        *,
        on_task_selected: Callable[[Task], None] | None = None,
        show_project: bool = False,
        show_raw_text: bool = True,
        initially_expanded: bool = True,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._expanded = initially_expanded
        self._on_task_selected = on_task_selected
        self._build(
            title,
            tasks,
            on_complete,
            on_delete,
            show_project,
            show_raw_text,
        )

    def _build(
        self,
        title: str,
        tasks: list[Task],
        on_complete: Callable[[Task], None],
        on_delete: Callable[[Task], None],
        show_project: bool,
        show_raw_text: bool,
    ) -> None:
        # Section header button (hidden when title is empty)
        self._chevron = Gtk.Image.new_from_icon_name("pan-down-symbolic")
        if title:
            header_btn = Gtk.Button()
            header_btn.add_css_class("flat")
            header_btn.connect("clicked", self._toggle)

            header_box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=8,
            )
            header_btn.set_child(header_box)

            label = Gtk.Label(label=title, xalign=0.0)
            label.add_css_class("heading")
            label.set_hexpand(True)
            header_box.append(label)

            header_box.append(self._chevron)

            self.append(header_btn)

        # Revealer wrapping the task list
        self._revealer = Gtk.Revealer()
        self._revealer.set_reveal_child(self._expanded)
        self._revealer.set_transition_type(
            Gtk.RevealerTransitionType.SLIDE_DOWN,
        )

        list_box = Gtk.ListBox()
        list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        list_box.add_css_class("task-list")
        if self._on_task_selected is not None:
            list_box.connect("row-activated", self._on_row_activated)

        sorted_tasks = sorted(tasks, key=sort_key)
        for task in sorted_tasks:
            list_box.append(
                TaskRow(
                    task,
                    on_complete,
                    on_delete,
                    show_project=show_project,
                    show_raw_text=show_raw_text,
                ),
            )

        self._revealer.set_child(list_box)
        self.append(self._revealer)

        if not self._expanded:
            self._chevron.set_from_icon_name("pan-end-symbolic")

    def _toggle(self, _btn: object) -> None:
        self._expanded = not self._expanded
        self._revealer.set_reveal_child(self._expanded)
        icon = "pan-down-symbolic" if self._expanded else "pan-end-symbolic"
        self._chevron.set_from_icon_name(icon)

    def _on_row_activated(
        self,
        _listbox: object,
        row: object,
    ) -> None:
        if isinstance(row, TaskRow) and self._on_task_selected is not None:
            self._on_task_selected(row.task)
