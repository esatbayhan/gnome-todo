"""Main application window with split layout."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GObject, Gtk
from todotxt_lib import (
    FALLBACK_GROUPS,
    GROUPING_MODES,
    MutationOutcome,
    SelectionKind,
    SidebarSelection,
    Task,
    TodoDirectory,
    TaskRef,
    add_tag_to_task,
    add_task_with_priority,
    all_contexts,
    all_projects,
    build_tag_list,
    complete_task_by_ref,
    compute_smart_filter_counts,
    delete_task_by_ref,
    find_task_by_ref,
    group_tasks,
    uncomplete_task_by_ref,
    update_task_from_detail,
)

from . import __version__
from ._config import get_auto_normalize_multi_task_files, get_show_raw_text
from ._content import TaskSection
from ._content_header import ContentHeader
from ._detail_panel import TaskDetailPanel
from ._dialogs import AddTaskDialog, AddTaskResult
from ._file_monitor import FileMonitor
from ._preferences import PreferencesDialog
from ._shortcuts import FILTER_BY_NUMBER, FILTER_ICONS, build_shortcuts_window
from ._sidebar import (
    FILTER_DEFS,
    SmartFilterRow,
    TagRow,
)
from ._ui import RESOURCE_PREFIX
from ._window_state import (
    build_content_state,
    smart_filter_row_counts,
)


@Gtk.Template(resource_path=f"{RESOURCE_PREFIX}/ui/window.ui")
class TodoWindow(Adw.ApplicationWindow):
    """Main window with sidebar + content + detail panel split view."""

    __gtype_name__ = "TodoWindow"

    toast_overlay = Gtk.Template.Child()
    split_view = Gtk.Template.Child()
    filter_list = Gtk.Template.Child()
    project_list = Gtk.Template.Child()
    context_list = Gtk.Template.Child()
    detail_split = Gtk.Template.Child()
    detail_panel = Gtk.Template.Child()
    show_sidebar_btn = Gtk.Template.Child()
    menu_btn = Gtk.Template.Child()
    search_btn = Gtk.Template.Child()
    search_bar = Gtk.Template.Child()
    search_entry = Gtk.Template.Child()
    content_stack = Gtk.Template.Child()
    status_page = Gtk.Template.Child()
    content_box = Gtk.Template.Child()
    content_header = Gtk.Template.Child()
    sections_box = Gtk.Template.Child()

    def __init__(
        self,
        application: Adw.Application,
        todo_dir: Path,
    ) -> None:
        super().__init__(application=application)
        self._store = TodoDirectory(
            todo_dir,
            auto_normalize_multi_task_files=get_auto_normalize_multi_task_files(),
        )
        self._add_dialog = AddTaskDialog()
        self._prefs_dialog = PreferencesDialog()

        # Shortcuts overlay
        self.set_help_overlay(build_shortcuts_window())

        # Preferences action
        prefs_action = Gio.SimpleAction.new("preferences", None)
        prefs_action.connect("activate", self._on_preferences)
        self.add_action(prefs_action)

        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._on_about)
        self.add_action(about_action)

        # Selection state
        self._selection_kind: SelectionKind = "smart"
        self._selection_value: str = "All"
        self._show_completed_in_list = False
        self._updating_sidebar = False
        self._selected_task: Task | None = None
        self._grouping_mode: int = 0  # index into GROUPING_MODES
        self._show_raw_text: bool = get_show_raw_text()

        # Wire up grouping dropdown callback
        self.content_header._on_grouping_changed = self._on_grouping_mode_changed

        # Wire up detail panel callbacks
        self.detail_panel._on_task_updated = self._on_detail_task_updated
        self.detail_panel._on_task_completed = self._on_detail_task_completed
        self.detail_panel._on_task_uncompleted = self._on_detail_task_uncompleted
        self.detail_panel._on_task_deleted = self._on_detail_task_deleted
        self.detail_panel._on_close = self._close_detail_panel

        # Populate the template's filter ListBox with SmartFilterRow children
        self._setup_filter_list()

        # Search bar / button binding
        self.search_bar.connect_entry(self.search_entry)
        self.search_btn.bind_property(
            "active",
            self.search_bar,
            "search-mode-enabled",
            GObject.BindingFlags.BIDIRECTIONAL,
        )

        # Keyboard shortcuts
        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_ctrl)

        # File monitoring for external changes (e.g. Syncthing)
        self._monitor = FileMonitor(
            [self._store.root_dir, self._store.done_dir],
            self._on_file_reload,
        )

        self._load()
        self._monitor.setup()

    def _on_about(self, *_args: object) -> None:
        """Present the standard GNOME about window with runtime version info."""
        about = Adw.AboutWindow(
            transient_for=self,
            application_name="Todo",
            application_icon="dev.bayhan.GnomeTodo",
            version=__version__,
            developer_name="Esat Bayhan",
            issue_url="https://github.com/esatbayhan/gnome-todo/issues",
            website="https://github.com/esatbayhan/gnome-todo",
            license_type=Gtk.License.MIT_X11,
        )
        about.present()

    def _setup_filter_list(self) -> None:
        """Populate the filter ListBox with SmartFilterRow children."""
        self._filter_rows: dict[str, SmartFilterRow] = {}
        for name, icon in FILTER_DEFS:
            row = SmartFilterRow(name, icon)
            self._filter_rows[name] = row
            self.filter_list.append(row)

    def _on_file_reload(self) -> None:
        """Reload data if files were modified externally."""
        if self._store.has_external_changes():
            self._load()
            self._refresh_selected_task()

    # ── Data loading ────────────────────────────────────────────────────

    def _load(self) -> None:
        self._store.load()
        self._refresh_sidebar()
        self._refresh_content()

    def _all_tasks(self) -> list[Task]:
        return list(self._store.tasks)

    # ── Reload helpers (sync-safety) ─────────────────────────────────

    def _reload_if_changed(self) -> None:
        """Reload files from disk if they were modified externally.

        Called before every mutating operation so that our save does not
        silently overwrite changes made by another device / program.
        """
        if self._store.has_external_changes():
            self._store.load()
            self._selected_task = self._resolve_task(self._selected_task)

    def _refresh_selected_task(self) -> None:
        """Re-select the open task after an external reload, or close panel."""
        if self._selected_task is None:
            return
        located = self._find_selected_task()
        if located is None:
            self._close_detail_panel()
            return

        self._selected_task = located.task
        self._sync_detail_panel()

    def _find_selected_task(self) -> object | None:
        if self._selected_task is None or self._selected_task.ref is None:
            return None
        resolved = self._resolve_task(self._selected_task)
        if resolved is None or resolved.ref is None:
            return None
        return find_task_by_ref(self._store, resolved.ref)

    def _resolve_task(self, task: Task | None) -> Task | None:
        if task is None or task.ref is None:
            return None
        return self._store.find_task_fuzzy(task.ref, raw=task.raw)

    # ── Sidebar refresh ─────────────────────────────────────────────────

    def _refresh_sidebar(self) -> None:
        self._updating_sidebar = True
        try:
            all_tasks = self._all_tasks()
            self._update_filter_counts(all_tasks)

            # Rebuild project list
            self.project_list.remove_all()
            for name, count in build_tag_list(all_tasks, "projects"):
                row = TagRow(
                    name,
                    count,
                    tag_kind="project",
                    on_task_dropped=self._on_task_dropped_on_tag,
                )
                self.project_list.append(row)

            # Rebuild context list
            self.context_list.remove_all()
            for name, count in build_tag_list(all_tasks, "contexts"):
                row = TagRow(
                    name,
                    count,
                    tag_kind="context",
                    on_task_dropped=self._on_task_dropped_on_tag,
                )
                self.context_list.append(row)

            # Restore selection
            if self._selection_kind == "smart":
                self._set_filter_active(self._selection_value)
                self.project_list.unselect_all()
                self.context_list.unselect_all()
            elif self._selection_kind == "project":
                self._select_project_row(self._selection_value)
                self._set_filter_active(None)
                self.context_list.unselect_all()
            elif self._selection_kind == "context":
                self._select_context_row(self._selection_value)
                self._set_filter_active(None)
                self.project_list.unselect_all()
        finally:
            self._updating_sidebar = False

    def _update_filter_counts(self, tasks: list[Task]) -> None:
        """Recompute counts for all filter rows."""
        counts = compute_smart_filter_counts(tasks, today=date.today())
        for name, count in smart_filter_row_counts(counts).items():
            self._filter_rows[name].set_count(count)

    def _set_filter_active(self, name: str | None) -> None:
        """Select the filter row matching the given name, deselect if None."""
        if name is None:
            self.filter_list.unselect_all()
            return
        row = self._filter_rows.get(name)
        if row is not None:
            self.filter_list.select_row(row)

    def _select_project_row(self, project_name: str) -> None:
        """Select the project row matching the given name."""
        row = self.project_list.get_first_child()
        while row is not None:
            if isinstance(row, TagRow) and row.tag_name == project_name:
                self.project_list.select_row(row)
                return
            row = row.get_next_sibling()

    def _select_context_row(self, context_name: str) -> None:
        """Select the context row matching the given name."""
        row = self.context_list.get_first_child()
        while row is not None:
            if isinstance(row, TagRow) and row.tag_name == context_name:
                self.context_list.select_row(row)
                return
            row = row.get_next_sibling()

    # ── Content refresh ─────────────────────────────────────────────────

    def _refresh_content(self) -> None:
        mode = GROUPING_MODES[self._grouping_mode]
        content_state = build_content_state(
            self._all_tasks(),
            selection=self._current_selection(),
            search_text=self.search_entry.get_text(),
            grouping_mode=mode,
            today=date.today(),
            filter_icons=FILTER_ICONS,
        )

        self.content_header.update(
            content_state.title,
            content_state.count,
            content_state.icon_name,
        )

        # Rebuild sections
        child = self.sections_box.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.sections_box.remove(child)
            child = next_child

        if content_state.empty_state is not None:
            self.status_page.set_title(content_state.empty_state.title)
            self.status_page.set_description(content_state.empty_state.description)
            self.status_page.set_icon_name(content_state.empty_state.icon_name)
            self.content_stack.set_visible_child_name("empty")
            return

        self.content_stack.set_visible_child_name("content")

        if content_state.display_tasks:
            groups = group_tasks(list(content_state.display_tasks), mode)
            single_fallback = len(groups) == 1 and (
                not groups[0][0] or groups[0][0] in FALLBACK_GROUPS
            )
            if single_fallback:
                section = TaskSection(
                    "",
                    groups[0][1],
                    self._complete_task,
                    self._delete_task,
                    on_task_selected=self._on_task_selected,
                    show_project=content_state.show_project,
                    show_raw_text=self._show_raw_text,
                )
                self.sections_box.append(section)
            else:
                for group_name, group_tasks_list in groups:
                    section = TaskSection(
                        group_name,
                        group_tasks_list,
                        self._complete_task,
                        self._delete_task,
                        on_task_selected=self._on_task_selected,
                        show_project=content_state.show_project,
                        show_raw_text=self._show_raw_text,
                    )
                    self.sections_box.append(section)

        # Completed section at bottom (for non-Completed views)
        if content_state.show_completed_section:
            completed_section = TaskSection(
                f"Completed ({len(content_state.done_tasks)})",
                list(content_state.done_tasks),
                self._complete_task,
                self._delete_task,
                on_task_selected=self._on_task_selected,
                show_project=content_state.show_project,
                show_raw_text=self._show_raw_text,
                initially_expanded=self._show_completed_in_list,
            )
            self.sections_box.append(completed_section)

    def _current_selection(self) -> SidebarSelection:
        """Return the current sidebar selection as a typed value."""
        return SidebarSelection(kind=self._selection_kind, value=self._selection_value)

    def _on_grouping_mode_changed(self, index: int) -> None:
        """Handle grouping dropdown selection change."""
        self._grouping_mode = index
        self._refresh_content()

    # ── Task actions ────────────────────────────────────────────────────

    def _complete_task(self, task: Task) -> None:
        if task.ref is None:
            return
        self._reload_if_changed()
        outcome = complete_task_by_ref(
            self._store,
            task.ref,
            completion_date=date.today(),
        )
        if outcome.status == "missing":
            self._refresh_sidebar()
            self._refresh_content()
            return

        self._apply_mutation_outcome(
            outcome,
            toast_title="Task completed",
        )

    def _delete_task(self, task: Task) -> None:
        if task.ref is None:
            return
        self._reload_if_changed()
        outcome = delete_task_by_ref(self._store, task.ref)
        if outcome.status == "missing":
            self._close_detail_panel()
            self._refresh_sidebar()
            self._refresh_content()
            return

        self._apply_mutation_outcome(
            outcome,
            close_detail=True,
            toast_title="Task deleted",
        )

    # ── Drag-and-drop onto sidebar tags ────────────────────────────────

    def _on_task_dropped_on_tag(
        self,
        task_ref: TaskRef,
        tag_name: str,
        tag_kind: str,
    ) -> None:
        """Add a project or context to a task dropped on a sidebar tag."""
        self._reload_if_changed()
        outcome = add_tag_to_task(
            self._store,
            task_ref,
            tag_name=tag_name,
            tag_kind=tag_kind,
        )
        if outcome.status != "changed":
            return

        prefix = "+" if tag_kind == "project" else "@"
        self._apply_mutation_outcome(
            outcome,
            select_task=(
                self._selected_task is not None and self._selected_task.ref == task_ref
            ),
            toast_title=f"Added {prefix}{tag_name}",
        )

    # ── Detail panel ────────────────────────────────────────────────────

    def _on_task_selected(self, task: Task) -> None:
        """Open the detail panel for the selected task."""
        self._selected_task = task
        self._sync_detail_panel()
        self.detail_split.set_show_sidebar(True)

    def _close_detail_panel(self) -> None:
        self._selected_task = None
        self.detail_split.set_show_sidebar(False)

    def _on_detail_task_updated(self, old_task: Task, new_line: str) -> None:
        """Handle task update from the detail panel."""
        if old_task.ref is None:
            return
        self._reload_if_changed()
        outcome = update_task_from_detail(
            self._store,
            old_task.ref,
            new_line,
        )
        if outcome.status == "missing":
            self._refresh_sidebar()
            self._refresh_content()
            return
        if outcome.status == "noop":
            return

        self._apply_mutation_outcome(
            outcome,
            select_task=True,
        )

    def _on_detail_task_completed(self, task: Task) -> None:
        self._complete_task(task)
        self._close_detail_panel()

    def _on_detail_task_uncompleted(self, task: Task) -> None:
        if task.ref is None:
            return
        self._reload_if_changed()
        outcome = uncomplete_task_by_ref(self._store, task.ref)
        if outcome.status == "missing":
            self._close_detail_panel()
            self._refresh_sidebar()
            self._refresh_content()
            return

        self._apply_mutation_outcome(
            outcome,
            close_detail=True,
            toast_title="Task uncompleted",
        )

    def _on_detail_task_deleted(self, task: Task) -> None:
        self._delete_task(task)

    # ── Template callbacks ─────────────────────────────────────────────

    @Gtk.Template.Callback()
    def on_hide_sidebar(self, *_args: object) -> None:
        self.split_view.set_show_sidebar(False)

    @Gtk.Template.Callback()
    def on_show_sidebar(self, *_args: object) -> None:
        self.split_view.set_show_sidebar(True)

    @Gtk.Template.Callback()
    def on_sidebar_visibility_changed(
        self,
        split: Adw.OverlaySplitView,
        _pspec: object,
    ) -> None:
        self.show_sidebar_btn.set_visible(not split.get_show_sidebar())

    def _select_tag(
        self,
        kind: str,
        value: str,
        deselect_lists: list[Gtk.ListBox],
    ) -> None:
        self._selection_kind = kind
        self._selection_value = value
        self._show_completed_in_list = False
        if kind != "smart":
            self._set_filter_active(None)
        self._updating_sidebar = True
        for lst in deselect_lists:
            lst.unselect_all()
        self._updating_sidebar = False
        self._close_detail_panel()
        self._refresh_content()
        if self.split_view.get_collapsed():
            self.split_view.set_show_sidebar(False)

    @Gtk.Template.Callback()
    def on_filter_selected(self, _listbox: object, row: object) -> None:
        if self._updating_sidebar:
            return
        if row is None or not isinstance(row, SmartFilterRow):
            return
        self._select_tag(
            "smart",
            row.filter_name,
            [self.project_list, self.context_list],
        )

    @Gtk.Template.Callback()
    def on_project_selected(self, _listbox: object, row: object) -> None:
        if self._updating_sidebar:
            return
        if not isinstance(row, TagRow):
            return
        self._select_tag(
            "project",
            row.tag_name,
            [self.context_list],
        )

    @Gtk.Template.Callback()
    def on_context_selected(self, _listbox: object, row: object) -> None:
        if self._updating_sidebar:
            return
        if not isinstance(row, TagRow):
            return
        self._select_tag(
            "context",
            row.tag_name,
            [self.project_list],
        )

    @Gtk.Template.Callback()
    def on_new_clicked(self, *_args: object) -> None:
        project = self._selection_value if self._selection_kind == "project" else None
        all_task_list = self._all_tasks()

        def on_result(result: AddTaskResult | None) -> None:
            if result is None:
                return
            self._reload_if_changed()
            outcome = add_task_with_priority(
                self._store,
                result.text,
                creation_date=date.today(),
                priority=result.priority,
            )
            self._apply_mutation_outcome(
                outcome,
                toast_title="Task added",
            )

        self._add_dialog.open(
            self,
            on_result,
            project=project,
            all_contexts=all_contexts(all_task_list),
            all_projects=all_projects(all_task_list),
        )

    @Gtk.Template.Callback()
    def on_search_changed(self, _entry: object) -> None:
        self._refresh_content()

    def _on_key_pressed(
        self, _ctrl: object, keyval: int, _keycode: int, state: Gdk.ModifierType
    ) -> bool:
        ctrl = Gdk.ModifierType.CONTROL_MASK
        if state & ctrl:
            if keyval in (Gdk.KEY_n, Gdk.KEY_N):
                self.on_new_clicked()
                return True
            if keyval in (Gdk.KEY_f, Gdk.KEY_F):
                self.search_btn.set_active(True)
                return True
            if keyval == Gdk.KEY_comma:
                self._on_preferences()
                return True
            # Ctrl+1..6 → quick filter switching
            digit = keyval - Gdk.KEY_1
            if 0 <= digit < len(FILTER_BY_NUMBER):
                name = FILTER_BY_NUMBER[digit]
                self._selection_kind = "smart"
                self._selection_value = name
                self._show_completed_in_list = False
                self._set_filter_active(name)
                self.project_list.unselect_all()
                self.context_list.unselect_all()
                self._close_detail_panel()
                self._refresh_content()
                return True
        if keyval == Gdk.KEY_Escape:
            if self.search_bar.get_search_mode():
                self.search_btn.set_active(False)
                return True
            if self.detail_split.get_show_sidebar():
                self._close_detail_panel()
                return True
        if keyval == Gdk.KEY_F9:
            visible = self.split_view.get_show_sidebar()
            self.split_view.set_show_sidebar(not visible)
            return True
        return False

    # ── Preferences ────────────────────────────────────────────────────

    def _on_preferences(self, *_args: object) -> None:
        current_dir = self._store.root_dir
        self._prefs_dialog.open(
            self,
            current_dir,
            self._on_dir_changed,
            on_auto_normalize_changed=self._on_auto_normalize_changed,
            on_raw_text_changed=self._on_raw_text_changed,
        )

    def _on_auto_normalize_changed(self, value: bool) -> None:
        self._store.auto_normalize_multi_task_files = value

    def _on_raw_text_changed(self, value: bool) -> None:
        self._show_raw_text = value
        self._refresh_content()

    def _on_dir_changed(self, new_dir: Path) -> None:
        self._store = TodoDirectory(
            new_dir,
            auto_normalize_multi_task_files=get_auto_normalize_multi_task_files(),
        )
        self._close_detail_panel()
        self._load()
        self._monitor.update_paths([self._store.root_dir, self._store.done_dir])
        self.toast_overlay.add_toast(Adw.Toast(title=f"Switched to {new_dir.name}"))

    def _sync_detail_panel(self) -> None:
        """Refresh the detail panel for the currently selected task."""
        if self._selected_task is None:
            return
        all_task_list = self._all_tasks()
        self.detail_panel.set_available_tags(
            all_contexts(all_task_list),
            all_projects(all_task_list),
        )
        self.detail_panel.set_task(self._selected_task)

    def _apply_mutation_outcome(
        self,
        outcome: MutationOutcome,
        *,
        select_task: bool = False,
        close_detail: bool = False,
        toast_title: str | None = None,
    ) -> None:
        """Persist changed files, refresh views, and update selection state."""
        if close_detail:
            self._close_detail_panel()
        elif select_task and outcome.task is not None:
            self._selected_task = outcome.task
        else:
            self._selected_task = self._resolve_task(self._selected_task)
            if self._selected_task is None:
                self._close_detail_panel()

        self._refresh_sidebar()
        self._refresh_content()

        if not close_detail and self._selected_task is not None:
            self._sync_detail_panel()

        if toast_title is not None and outcome.changed:
            self.toast_overlay.add_toast(Adw.Toast(title=toast_title))
