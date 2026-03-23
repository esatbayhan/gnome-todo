"""Right-side task detail/edit panel (Planify-style)."""

from __future__ import annotations

import enum
import re
from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk
from todotxt_lib import Priority, Task

from ._ui import RESOURCE_PREFIX


class _Unset(enum.Enum):
    """Sentinel to distinguish 'not provided' from None."""

    TOKEN = 0


_UNSET = _Unset.TOKEN


def rebuild_task_line(
    task: Task,
    *,
    new_text: str | None = None,
    due: str | None | _Unset = _UNSET,
    scheduled: str | None | _Unset = _UNSET,
    starting: str | None | _Unset = _UNSET,
    add_context: str | None = None,
    remove_context: str | None = None,
    add_project: str | None = None,
    remove_project: str | None = None,
) -> str:
    """Reconstruct the task text portion with modifications.

    Returns just the text part (no done marker, priority, or dates prefix).
    The caller uses replace_task() which re-parses the full line.
    """
    text = new_text if new_text is not None else task.text

    # Remove a context
    if remove_context:
        text = re.sub(rf"\s*@{re.escape(remove_context)}\b", "", text)

    # Add a context
    if add_context and f"@{add_context}" not in text:
        text = f"{text} @{add_context}"

    # Remove a project
    if remove_project:
        text = re.sub(rf"\s*\+{re.escape(remove_project)}\b", "", text)

    # Add a project
    if add_project and f"+{add_project}" not in text:
        text = f"{text} +{add_project}"

    # Handle due date
    if not isinstance(due, _Unset):
        text = re.sub(r"\s*due:\S+", "", text)
        if due is not None:
            text = f"{text} due:{due}"

    # Handle scheduled date
    if not isinstance(scheduled, _Unset):
        text = re.sub(r"\s*scheduled:\S+", "", text)
        if scheduled is not None:
            text = f"{text} scheduled:{scheduled}"

    # Handle starting date
    if not isinstance(starting, _Unset):
        text = re.sub(r"\s*starting:\S+", "", text)
        if starting is not None:
            text = f"{text} starting:{starting}"

    return text.strip()


# Priority labels for the combo row
_PRIORITY_LABELS = ["None", "A — Highest", "B — High", "C — Medium", "D — Low"]
_PRIORITY_VALUES: list[Priority | None] = [
    None,
    Priority.A,
    Priority.B,
    Priority.C,
    Priority.D,
]


@Gtk.Template(resource_path=f"{RESOURCE_PREFIX}/ui/task_detail_panel.ui")
class TaskDetailPanel(Gtk.Box):
    """Right-side panel for viewing and editing a task's properties."""

    __gtype_name__ = "TaskDetailPanel"

    text_entry = Gtk.Template.Child()
    priority_combo = Gtk.Template.Child()
    due_row = Gtk.Template.Child()
    due_date_menu_btn = Gtk.Template.Child()
    detail_calendar = Gtk.Template.Child()
    scheduled_row = Gtk.Template.Child()
    scheduled_menu_btn = Gtk.Template.Child()
    scheduled_calendar = Gtk.Template.Child()
    starting_row = Gtk.Template.Child()
    starting_menu_btn = Gtk.Template.Child()
    starting_calendar = Gtk.Template.Child()
    completed_switch = Gtk.Template.Child()
    labels_flow = Gtk.Template.Child()
    label_entry = Gtk.Template.Child()
    projects_flow = Gtk.Template.Child()
    project_entry = Gtk.Template.Child()
    created_row = Gtk.Template.Child()
    completed_date_row = Gtk.Template.Child()

    def __init__(
        self,
        *,
        on_task_updated: Callable[[Task, str], None] | None = None,
        on_task_completed: Callable[[Task], None] | None = None,
        on_task_uncompleted: Callable[[Task], None] | None = None,
        on_task_deleted: Callable[[Task], None] | None = None,
        on_close: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self._on_task_updated = on_task_updated
        self._on_task_completed = on_task_completed
        self._on_task_uncompleted = on_task_uncompleted
        self._on_task_deleted = on_task_deleted
        self._on_close = on_close
        self._task: Task | None = None
        self._updating = False
        self._all_contexts: list[str] = []
        self._all_projects: list[str] = []

        # Autocomplete: filter suggestion chips as user types
        self.label_entry.connect("changed", self._on_label_text_changed)
        self.project_entry.connect("changed", self._on_project_text_changed)

    # ── Public API ───────────────────────────────────────────────────────

    def set_available_tags(
        self,
        contexts: list[str],
        projects: list[str],
    ) -> None:
        """Update the lists used for autocomplete suggestions."""
        self._all_contexts = contexts
        self._all_projects = projects

    def set_task(self, task: Task | None) -> None:
        """Populate the panel with a task, or clear it."""
        self._updating = True
        try:
            self._task = task
            if task is None:
                return

            # Text
            self.text_entry.set_text(task.text)

            # Priority
            if task.priority is not None and task.priority in _PRIORITY_VALUES:
                idx = _PRIORITY_VALUES.index(task.priority)
            else:
                idx = 0
            self.priority_combo.set_selected(idx)
            self.priority_combo.set_sensitive(not task.done)

            # Due date
            due = task.keyvalues.get("due")
            if due:
                self.due_row.set_subtitle(due)
            else:
                self.due_row.set_subtitle("Not set")

            # Scheduled date
            sched = task.keyvalues.get("scheduled")
            if sched:
                self.scheduled_row.set_subtitle(sched)
            else:
                self.scheduled_row.set_subtitle("Not set")

            # Starting date
            start = task.keyvalues.get("starting")
            if start:
                self.starting_row.set_subtitle(start)
            else:
                self.starting_row.set_subtitle("Not set")

            # Completed
            self.completed_switch.set_active(task.done)

            # Labels (contexts)
            self._rebuild_chips(
                self.labels_flow,
                task.contexts,
                self._on_remove_context,
            )
            self._add_suggestions(
                self.labels_flow,
                self._all_contexts,
                task.contexts,
                self._on_add_context_suggestion,
            )

            # Projects
            self._rebuild_chips(
                self.projects_flow,
                task.projects,
                self._on_remove_project,
            )
            self._add_suggestions(
                self.projects_flow,
                self._all_projects,
                task.projects,
                self._on_add_project_suggestion,
            )

            # Info
            if task.creation_date:
                self.created_row.set_subtitle(str(task.creation_date))
            else:
                self.created_row.set_subtitle("Unknown")

            if task.completion_date:
                self.completed_date_row.set_subtitle(str(task.completion_date))
                self.completed_date_row.set_visible(True)
            else:
                self.completed_date_row.set_subtitle("N/A")
                self.completed_date_row.set_visible(task.done)
        finally:
            self._updating = False

    def _rebuild_chips(
        self,
        flow: Gtk.FlowBox,
        items: tuple[str, ...],
        on_remove: Callable[[str], None],
    ) -> None:
        """Rebuild a flow box with removable chip buttons."""
        # Remove all children
        while True:
            child = flow.get_child_at_index(0)
            if child is None:
                break
            flow.remove(child)

        for item in items:
            chip_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            chip_box.add_css_class("detail-chip")

            remove_btn = Gtk.Button(icon_name="window-close-symbolic")
            remove_btn.add_css_class("flat")
            remove_btn.add_css_class("circular")
            remove_btn.add_css_class("chip-remove-btn")
            remove_btn.connect("clicked", self._make_remove_handler(on_remove, item))
            chip_box.append(remove_btn)

            label = Gtk.Label(label=item)
            # label.set_margin_end(20)
            chip_box.append(label)

            flow.append(chip_box)

    # ── Template callbacks ───────────────────────────────────────────────

    @Gtk.Template.Callback()
    def on_text_changed(self, entry: Adw.EntryRow) -> None:
        if self._updating or self._task is None or self._on_task_updated is None:
            return
        new_text = entry.get_text().strip()
        if not new_text or new_text == self._task.text:
            return
        new_line = rebuild_task_line(self._task, new_text=new_text)
        self._on_task_updated(self._task, new_line)

    @Gtk.Template.Callback()
    def on_priority_changed(self, combo: Adw.ComboRow, _pspec: object) -> None:
        if self._updating or self._task is None or self._on_task_updated is None:
            return
        idx = combo.get_selected()
        new_pri = _PRIORITY_VALUES[idx] if idx < len(_PRIORITY_VALUES) else None
        if new_pri == self._task.priority:
            return
        pri_val = new_pri.value if new_pri else ""
        self._on_task_updated(self._task, f"__priority__:{pri_val}")

    def _handle_date_selected(
        self,
        calendar: Gtk.Calendar,
        menu_btn: Gtk.MenuButton,
        key: str,
    ) -> None:
        if self._updating or self._task is None or self._on_task_updated is None:
            return
        dt = calendar.get_date()
        date_str = f"{dt.get_year()}-{dt.get_month():02d}-{dt.get_day_of_month():02d}"
        new_line = rebuild_task_line(self._task, **{key: date_str})
        popover = menu_btn.get_popover()
        if popover is not None:
            popover.popdown()
        self._on_task_updated(self._task, new_line)

    def _handle_date_cleared(
        self,
        menu_btn: Gtk.MenuButton,
        key: str,
    ) -> None:
        if self._updating or self._task is None or self._on_task_updated is None:
            return
        new_line = rebuild_task_line(self._task, **{key: None})
        popover = menu_btn.get_popover()
        if popover is not None:
            popover.popdown()
        self._on_task_updated(self._task, new_line)

    @Gtk.Template.Callback()
    def on_due_date_selected(self, calendar: Gtk.Calendar) -> None:
        self._handle_date_selected(calendar, self.due_date_menu_btn, "due")

    @Gtk.Template.Callback()
    def on_due_date_cleared(self, _btn: object) -> None:
        self._handle_date_cleared(self.due_date_menu_btn, "due")

    @Gtk.Template.Callback()
    def on_scheduled_date_selected(self, calendar: Gtk.Calendar) -> None:
        self._handle_date_selected(calendar, self.scheduled_menu_btn, "scheduled")

    @Gtk.Template.Callback()
    def on_scheduled_date_cleared(self, _btn: object) -> None:
        self._handle_date_cleared(self.scheduled_menu_btn, "scheduled")

    @Gtk.Template.Callback()
    def on_starting_date_selected(self, calendar: Gtk.Calendar) -> None:
        self._handle_date_selected(calendar, self.starting_menu_btn, "starting")

    @Gtk.Template.Callback()
    def on_starting_date_cleared(self, _btn: object) -> None:
        self._handle_date_cleared(self.starting_menu_btn, "starting")

    @Gtk.Template.Callback()
    def on_completed_toggled(self, switch: Adw.SwitchRow, _pspec: object) -> None:
        if self._updating or self._task is None:
            return
        if switch.get_active() and not self._task.done:
            if self._on_task_completed is not None:
                self._on_task_completed(self._task)
        elif not switch.get_active() and self._task.done:
            if self._on_task_uncompleted is not None:
                self._on_task_uncompleted(self._task)

    @Gtk.Template.Callback()
    def on_add_context(self, entry: Adw.EntryRow) -> None:
        if self._task is None or self._on_task_updated is None:
            return
        text = entry.get_text().strip().lstrip("@")
        if not text:
            return
        entry.set_text("")
        new_line = rebuild_task_line(self._task, add_context=text)
        self._on_task_updated(self._task, new_line)

    @Gtk.Template.Callback()
    def on_add_project(self, entry: Adw.EntryRow) -> None:
        if self._task is None or self._on_task_updated is None:
            return
        text = entry.get_text().strip().lstrip("+")
        if not text:
            return
        entry.set_text("")
        new_line = rebuild_task_line(self._task, add_project=text)
        self._on_task_updated(self._task, new_line)

    @Gtk.Template.Callback()
    def on_delete_clicked(self, _btn: object) -> None:
        if self._task is not None and self._on_task_deleted is not None:
            self._on_task_deleted(self._task)

    @Gtk.Template.Callback()
    def on_close_clicked(self, _btn: object) -> None:
        if self._on_close is not None:
            self._on_close()

    def _on_remove_context(self, ctx: str) -> None:
        if self._task is None or self._on_task_updated is None:
            return
        new_line = rebuild_task_line(self._task, remove_context=ctx)
        self._on_task_updated(self._task, new_line)

    def _on_remove_project(self, proj: str) -> None:
        if self._task is None or self._on_task_updated is None:
            return
        new_line = rebuild_task_line(self._task, remove_project=proj)
        self._on_task_updated(self._task, new_line)

    @staticmethod
    def _make_remove_handler(
        on_remove: Callable[[str], None], item: str
    ) -> Callable[[object], None]:
        def handler(_btn: object) -> None:
            on_remove(item)

        return handler

    # ── Inline suggestion chips ────────────────────────────────────────

    def _add_suggestions(
        self,
        flow: Gtk.FlowBox,
        all_items: list[str],
        current_items: tuple[str, ...],
        on_click: Callable[[str], None],
        filter_text: str = "",
    ) -> None:
        """Append suggestion chips for unused tags to a flow box."""
        available = [
            item
            for item in all_items
            if item not in current_items
            and (not filter_text or filter_text in item.lower())
        ]
        for item in available[:8]:
            btn = Gtk.Button(label=item)
            btn.add_css_class("suggestion-chip")
            btn.add_css_class("flat")
            btn.connect("clicked", self._make_remove_handler(on_click, item))
            flow.append(btn)

    def _clear_suggestions(self, flow: Gtk.FlowBox) -> None:
        """Remove only suggestion chips from a flow box."""
        to_remove: list[Gtk.Widget] = []
        idx = 0
        while True:
            child = flow.get_child_at_index(idx)
            if child is None:
                break
            inner = child.get_child()
            if inner is not None and inner.has_css_class("suggestion-chip"):
                to_remove.append(child)
            idx += 1
        for child in to_remove:
            flow.remove(child)

    def _on_label_text_changed(self, entry: Adw.EntryRow) -> None:
        if self._updating or self._task is None:
            return
        text = entry.get_text().strip().lstrip("@").lower()
        self._clear_suggestions(self.labels_flow)
        self._add_suggestions(
            self.labels_flow,
            self._all_contexts,
            self._task.contexts,
            self._on_add_context_suggestion,
            filter_text=text,
        )

    def _on_project_text_changed(self, entry: Adw.EntryRow) -> None:
        if self._updating or self._task is None:
            return
        text = entry.get_text().strip().lstrip("+").lower()
        self._clear_suggestions(self.projects_flow)
        self._add_suggestions(
            self.projects_flow,
            self._all_projects,
            self._task.projects,
            self._on_add_project_suggestion,
            filter_text=text,
        )

    def _on_add_context_suggestion(self, ctx: str) -> None:
        if self._task is None or self._on_task_updated is None:
            return
        self.label_entry.set_text("")
        new_line = rebuild_task_line(self._task, add_context=ctx)
        self._on_task_updated(self._task, new_line)

    def _on_add_project_suggestion(self, proj: str) -> None:
        if self._task is None or self._on_task_updated is None:
            return
        self.project_entry.set_text("")
        new_line = rebuild_task_line(self._task, add_project=proj)
        self._on_task_updated(self._task, new_line)
