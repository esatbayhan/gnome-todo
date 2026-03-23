"""Dialog widgets for the todo.txt GUI: enhanced quick-add with property pickers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk
from todotxt_lib import Priority

from ._ui import RESOURCE_PREFIX
from ._widgets import (
    context_chip,
    due_date_badge,
    priority_dot,
    project_label,
    scheduled_badge,
    starting_badge,
)


@dataclass
class AddTaskResult:
    """Result from the add-task dialog."""

    text: str
    priority: Priority | None = None


@Gtk.Template(resource_path=f"{RESOURCE_PREFIX}/ui/add_task_dialog.ui")
class AddTaskDialog(Adw.Dialog):
    """Enhanced quick-add dialog with property picker buttons."""

    __gtype_name__ = "AddTaskDialog"

    entry_row = Gtk.Template.Child()
    date_btn = Gtk.Template.Child()
    calendar = Gtk.Template.Child()
    scheduled_btn = Gtk.Template.Child()
    scheduled_calendar = Gtk.Template.Child()
    starting_btn = Gtk.Template.Child()
    starting_calendar = Gtk.Template.Child()
    priority_btn = Gtk.Template.Child()
    context_btn = Gtk.Template.Child()
    context_listbox = Gtk.Template.Child()
    context_entry = Gtk.Template.Child()
    project_btn = Gtk.Template.Child()
    project_listbox = Gtk.Template.Child()
    project_entry = Gtk.Template.Child()
    preview_box = Gtk.Template.Child()

    def __init__(self) -> None:
        super().__init__()
        self._callback: Callable[[AddTaskResult | None], None] | None = None
        self._project: str | None = None
        self._due_date: str | None = None
        self._scheduled_date: str | None = None
        self._starting_date: str | None = None
        self._priority: Priority | None = None
        self._contexts: list[str] = []
        self._projects: list[str] = []
        self._all_contexts: list[str] = []
        self._all_projects: list[str] = []

    # ── Template callbacks ────────────────────────────────────────────────

    def _select_date(self, calendar: Gtk.Calendar, attr: str) -> None:
        dt = calendar.get_date()
        date_str = f"{dt.get_year()}-{dt.get_month():02d}-{dt.get_day_of_month():02d}"
        setattr(self, attr, date_str)
        self._refresh_preview()

    def _clear_date(self, btn_attr: str, date_attr: str) -> None:
        setattr(self, date_attr, None)
        popover = getattr(self, btn_attr).get_popover()
        if popover is not None:
            popover.popdown()
        self._refresh_preview()

    @Gtk.Template.Callback()
    def on_date_selected(self, calendar: Gtk.Calendar) -> None:
        self._select_date(calendar, "_due_date")

    @Gtk.Template.Callback()
    def on_date_cleared(self, _btn: object) -> None:
        self._clear_date("date_btn", "_due_date")

    @Gtk.Template.Callback()
    def on_scheduled_selected(self, calendar: Gtk.Calendar) -> None:
        self._select_date(calendar, "_scheduled_date")

    @Gtk.Template.Callback()
    def on_scheduled_cleared(self, _btn: object) -> None:
        self._clear_date("scheduled_btn", "_scheduled_date")

    @Gtk.Template.Callback()
    def on_starting_selected(self, calendar: Gtk.Calendar) -> None:
        self._select_date(calendar, "_starting_date")

    @Gtk.Template.Callback()
    def on_starting_cleared(self, _btn: object) -> None:
        self._clear_date("starting_btn", "_starting_date")

    @Gtk.Template.Callback()
    def on_priority_none(self, _btn: object) -> None:
        self._set_priority(None)

    @Gtk.Template.Callback()
    def on_priority_a(self, _btn: object) -> None:
        self._set_priority(Priority.A)

    @Gtk.Template.Callback()
    def on_priority_b(self, _btn: object) -> None:
        self._set_priority(Priority.B)

    @Gtk.Template.Callback()
    def on_priority_c(self, _btn: object) -> None:
        self._set_priority(Priority.C)

    @Gtk.Template.Callback()
    def on_priority_d(self, _btn: object) -> None:
        self._set_priority(Priority.D)

    def _set_priority(self, pri: Priority | None) -> None:
        self._priority = pri
        popover = self.priority_btn.get_popover()
        if popover is not None:
            popover.popdown()
        self._refresh_preview()

    @Gtk.Template.Callback()
    def on_context_entry_activated(self, entry: Adw.EntryRow) -> None:
        text = entry.get_text().strip().lstrip("@")
        if text and text not in self._contexts:
            self._contexts.append(text)
            entry.set_text("")
            self._refresh_preview()

    @Gtk.Template.Callback()
    def on_project_entry_activated(self, entry: Adw.EntryRow) -> None:
        text = entry.get_text().strip().lstrip("+")
        if text and text not in self._projects:
            self._projects.append(text)
            entry.set_text("")
            self._refresh_preview()

    @Gtk.Template.Callback()
    def on_confirm(self, *_args: object) -> None:
        text = self.entry_row.get_text().strip()
        if not text:
            self._finish(None)
            return

        # Append metadata to text
        parts = [text]
        for ctx in self._contexts:
            tag = f"@{ctx}"
            if tag not in text:
                parts.append(tag)
        for proj in self._projects:
            tag = f"+{proj}"
            if tag not in text:
                parts.append(tag)
        if self._due_date:
            if f"due:{self._due_date}" not in text:
                parts.append(f"due:{self._due_date}")
        if self._scheduled_date:
            if f"scheduled:{self._scheduled_date}" not in text:
                parts.append(f"scheduled:{self._scheduled_date}")
        if self._starting_date:
            if f"starting:{self._starting_date}" not in text:
                parts.append(f"starting:{self._starting_date}")

        result = AddTaskResult(
            text=" ".join(parts),
            priority=self._priority,
        )
        self._finish(result)

    @Gtk.Template.Callback()
    def on_cancel(self, *_args: object) -> None:
        self._finish(None)

    # ── Context/project popover rebuilds ──────────────────────────────────

    def _rebuild_context_popover(self) -> None:
        """Rebuild the context popover with current available contexts."""
        self.context_listbox.remove_all()

        if not self._all_contexts:
            self.context_listbox.set_visible(False)
            return

        self.context_listbox.set_visible(True)
        for ctx in self._all_contexts:
            check = Gtk.CheckButton(label=f"@{ctx}")
            check.set_active(ctx in self._contexts)
            check.connect("toggled", self._on_context_toggled, ctx)
            self.context_listbox.append(check)

    def _on_context_toggled(self, btn: Gtk.CheckButton, ctx: str) -> None:
        if btn.get_active():
            if ctx not in self._contexts:
                self._contexts.append(ctx)
        else:
            if ctx in self._contexts:
                self._contexts.remove(ctx)
        self._refresh_preview()

    def _rebuild_project_popover(self) -> None:
        """Rebuild the project popover with current available projects."""
        self.project_listbox.remove_all()

        if not self._all_projects:
            self.project_listbox.set_visible(False)
            return

        self.project_listbox.set_visible(True)
        for proj in self._all_projects:
            check = Gtk.CheckButton(label=f"+{proj}")
            check.set_active(proj in self._projects)
            check.connect("toggled", self._on_project_toggled, proj)
            self.project_listbox.append(check)

    def _on_project_toggled(self, btn: Gtk.CheckButton, proj: str) -> None:
        if btn.get_active():
            if proj not in self._projects:
                self._projects.append(proj)
        else:
            if proj in self._projects:
                self._projects.remove(proj)
        self._refresh_preview()

    # ── Preview row ──────────────────────────────────────────────────────

    def _refresh_preview(self) -> None:
        """Update the preview chips row."""
        child = self.preview_box.get_first_child()
        while child is not None:
            next_c = child.get_next_sibling()
            self.preview_box.remove(child)
            child = next_c

        if self._priority is not None:
            self.preview_box.append(priority_dot(self._priority))

        if self._due_date is not None:
            self.preview_box.append(due_date_badge(self._due_date))

        if self._scheduled_date is not None:
            self.preview_box.append(scheduled_badge(self._scheduled_date))

        if self._starting_date is not None:
            self.preview_box.append(starting_badge(self._starting_date))

        for ctx in self._contexts:
            self.preview_box.append(context_chip(ctx))

        for proj in self._projects:
            self.preview_box.append(project_label(proj))

    # ── Open / finish ────────────────────────────────────────────────────

    def open(
        self,
        parent: Gtk.Widget,
        callback: Callable[[AddTaskResult | None], None],
        *,
        project: str | None = None,
        all_contexts: list[str] | None = None,
        all_projects: list[str] | None = None,
    ) -> None:
        self._callback = callback
        self._project = project
        self.entry_row.set_text("")
        self._due_date = None
        self._scheduled_date = None
        self._starting_date = None
        self._priority = None
        self._contexts = []
        self._projects = []

        # Pre-fill project if opening from project view
        if project:
            self._projects = [project]

        self._all_contexts = all_contexts or []
        self._all_projects = all_projects or []
        self._rebuild_context_popover()
        self._rebuild_project_popover()
        self._refresh_preview()
        self.present(parent)

    def _finish(self, result: AddTaskResult | None) -> None:
        if self._callback is not None:
            self._callback(result)
        self.close()
