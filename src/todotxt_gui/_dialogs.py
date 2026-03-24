"""Dialog widgets for the todo.txt GUI: enhanced quick-add with property pickers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk
from todotxt_lib import Priority, append_missing_task_metadata
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
        self._add_tag_from_entry(entry, self._contexts, "@")

    @Gtk.Template.Callback()
    def on_project_entry_activated(self, entry: Adw.EntryRow) -> None:
        self._add_tag_from_entry(entry, self._projects, "+")

    @Gtk.Template.Callback()
    def on_confirm(self, *_args: object) -> None:
        text = self.entry_row.get_text().strip()
        if not text:
            self._finish(None)
            return

        result = AddTaskResult(
            text=append_missing_task_metadata(
                text,
                contexts=self._contexts,
                projects=self._projects,
                due=self._due_date,
                scheduled=self._scheduled_date,
                starting=self._starting_date,
            ),
            priority=self._priority,
        )
        self._finish(result)

    @Gtk.Template.Callback()
    def on_cancel(self, *_args: object) -> None:
        self._finish(None)

    # ── Context/project popover rebuilds ──────────────────────────────────

    def _rebuild_context_popover(self) -> None:
        """Rebuild the context popover with current available contexts."""
        self._rebuild_tag_popover(
            self.context_listbox,
            self._all_contexts,
            self._contexts,
            "@",
            self._on_context_toggled,
        )

    def _on_context_toggled(self, btn: Gtk.CheckButton, ctx: str) -> None:
        self._toggle_tag_selection(self._contexts, ctx, btn.get_active())

    def _rebuild_project_popover(self) -> None:
        """Rebuild the project popover with current available projects."""
        self._rebuild_tag_popover(
            self.project_listbox,
            self._all_projects,
            self._projects,
            "+",
            self._on_project_toggled,
        )

    def _on_project_toggled(self, btn: Gtk.CheckButton, proj: str) -> None:
        self._toggle_tag_selection(self._projects, proj, btn.get_active())

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

    def _add_tag_from_entry(
        self,
        entry: Adw.EntryRow,
        target: list[str],
        prefix: str,
    ) -> None:
        text = entry.get_text().strip().lstrip(prefix)
        if not text or text in target:
            return
        target.append(text)
        entry.set_text("")
        self._refresh_preview()

    def _toggle_tag_selection(
        self,
        target: list[str],
        item: str,
        is_active: bool,
    ) -> None:
        if is_active:
            if item not in target:
                target.append(item)
        elif item in target:
            target.remove(item)
        self._refresh_preview()

    def _rebuild_tag_popover(
        self,
        listbox: Gtk.ListBox,
        available: list[str],
        selected: list[str],
        prefix: str,
        on_toggled: Callable[[Gtk.CheckButton, str], None],
    ) -> None:
        listbox.remove_all()
        if not available:
            listbox.set_visible(False)
            return

        listbox.set_visible(True)
        for item in available:
            check = Gtk.CheckButton(label=f"{prefix}{item}")
            check.set_active(item in selected)
            check.connect("toggled", on_toggled, item)
            listbox.append(check)
