"""Main application window with split layout."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GObject, Gtk
from todotxt_lib import (
    Priority,
    Task,
    TodoFile,
    add_task,
    all_contexts,
    all_projects,
    complete_task,
    delete_task,
    deprioritize,
    filter_tasks,
    replace_task,
    set_priority,
    uncomplete_task,
)

from ._config import get_show_raw_text
from . import __version__
from ._content import TaskSection
from ._content_header import ContentHeader as ContentHeader
from ._detail_panel import rebuild_task_line
from ._dialogs import AddTaskDialog, AddTaskResult
from ._file_monitor import FileMonitor
from ._grouping import FALLBACK_GROUPS, GROUPING_MODES, group_tasks
from ._preferences import PreferencesDialog
from ._shortcuts import FILTER_BY_NUMBER, FILTER_ICONS, build_shortcuts_window
from ._sidebar import (
    FILTER_DEFS,
    SmartFilterRow,
    TagRow,
    build_tag_list,
)
from ._ui import RESOURCE_PREFIX


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
        todo_path: Path,
        done_path: Path,
    ) -> None:
        super().__init__(application=application)
        self._todo = TodoFile(todo_path)
        self._done_file = TodoFile(done_path)
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
        self._selection_kind: str = "smart"  # "smart" or "project"
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
            [self._todo.path, self._done_file.path],
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
        if self._todo.has_external_changes() or self._done_file.has_external_changes():
            self._load()
            self._refresh_selected_task()

    # ── Data loading ────────────────────────────────────────────────────

    def _load(self) -> None:
        self._todo.load()
        self._done_file.load()
        self._refresh_sidebar()
        self._refresh_content()

    def _all_tasks(self) -> list[Task]:
        return list(self._todo.tasks) + list(self._done_file.tasks)

    # ── Reload helpers (sync-safety) ─────────────────────────────────

    def _reload_if_changed(self) -> None:
        """Reload files from disk if they were modified externally.

        Called before every mutating operation so that our save does not
        silently overwrite changes made by another device / program.
        """
        changed = False
        if self._todo.has_external_changes():
            self._todo.load()
            changed = True
        if self._done_file.has_external_changes():
            self._done_file.load()
            changed = True
        if changed and self._selected_task is not None:
            raw = self._selected_task.raw
            found = next((t for t in self._all_tasks() if t.raw == raw), None)
            if found is not None:
                self._selected_task = found
            else:
                self._selected_task = None

    def _find_task(self, raw: str) -> tuple[Task | None, TodoFile | None]:
        """Locate a task by its raw line in either backing file."""
        for t in self._todo.tasks:
            if t.raw == raw:
                return t, self._todo
        for t in self._done_file.tasks:
            if t.raw == raw:
                return t, self._done_file
        return None, None

    def _refresh_selected_task(self) -> None:
        """Re-select the open task after an external reload, or close panel."""
        if self._selected_task is None:
            return
        found = next(
            (t for t in self._all_tasks() if t.raw == self._selected_task.raw),
            None,
        )
        if found is not None:
            self._selected_task = found
            all_task_list = self._all_tasks()
            self.detail_panel.set_available_tags(
                all_contexts(all_task_list),
                all_projects(all_task_list),
            )
            self.detail_panel.set_task(found)
        else:
            self._close_detail_panel()

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
        today_str = str(date.today())
        inbox = 0
        today = 0
        scheduled = 0
        starting = 0
        all_active = 0
        completed = 0

        for t in tasks:
            if t.done:
                completed += 1
            else:
                all_active += 1
                if len(t.projects) == 0:
                    inbox += 1
                if t.keyvalues.get("due") == today_str:
                    today += 1
                if "scheduled" in t.keyvalues:
                    scheduled += 1
                if "starting" in t.keyvalues:
                    starting += 1

        self._filter_rows["Inbox"].set_count(inbox)
        self._filter_rows["Today"].set_count(today)
        self._filter_rows["Scheduled"].set_count(scheduled)
        self._filter_rows["Starting"].set_count(starting)
        self._filter_rows["All"].set_count(all_active)
        self._filter_rows["Completed"].set_count(completed)

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
        tasks = self._get_filtered_tasks()
        search_text = self.search_entry.get_text().strip().lower()
        if search_text:
            tasks = [t for t in tasks if search_text in t.text.lower()]

        active_tasks = [t for t in tasks if not t.done]
        done_tasks = [t for t in tasks if t.done]

        # For Completed view, show all done tasks
        if self._selection_value == "Completed" and self._selection_kind == "smart":
            display_tasks = done_tasks
        else:
            display_tasks = active_tasks

        # Determine grouping mode and project label visibility
        mode = GROUPING_MODES[self._grouping_mode]
        if mode == "project":
            show_project = False
        elif self._selection_kind == "project":
            show_project = False
        else:
            show_project = True

        # Update header
        title, icon_name = self._current_title_icon()
        count = len(display_tasks)
        self.content_header.update(title, count, icon_name)

        # Rebuild sections
        child = self.sections_box.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.sections_box.remove(child)
            child = next_child

        if not display_tasks and not done_tasks:
            if search_text:
                self.status_page.set_title("No Results")
                self.status_page.set_description("Try a different search term.")
                self.status_page.set_icon_name("edit-find-symbolic")
            else:
                self.status_page.set_title("No Tasks")
                self.status_page.set_description('Press "+" to get started.')
                self.status_page.set_icon_name("checkbox-checked-symbolic")
            self.content_stack.set_visible_child_name("empty")
            return

        self.content_stack.set_visible_child_name("content")

        if display_tasks:
            groups = group_tasks(display_tasks, mode)
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
                    show_project=show_project,
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
                        show_project=show_project,
                        show_raw_text=self._show_raw_text,
                    )
                    self.sections_box.append(section)

        # Completed section at bottom (for non-Completed views)
        show_completed = done_tasks and not (
            self._selection_kind == "smart" and self._selection_value == "Completed"
        )
        if show_completed:
            completed_section = TaskSection(
                f"Completed ({len(done_tasks)})",
                done_tasks,
                self._complete_task,
                self._delete_task,
                on_task_selected=self._on_task_selected,
                show_project=show_project,
                show_raw_text=self._show_raw_text,
                initially_expanded=self._show_completed_in_list,
            )
            self.sections_box.append(completed_section)

    def _get_filtered_tasks(self) -> list[Task]:
        """Get tasks matching the current sidebar selection."""
        all_tasks = self._all_tasks()
        today_str = str(date.today())

        if self._selection_kind == "smart":
            v = self._selection_value
            if v == "Inbox":
                return [t for t in all_tasks if not t.done and len(t.projects) == 0]
            if v == "Today":
                return [
                    t
                    for t in all_tasks
                    if not t.done and t.keyvalues.get("due") == today_str
                ]
            if v == "Scheduled":
                return [
                    t for t in all_tasks if not t.done and "scheduled" in t.keyvalues
                ]
            if v == "Starting":
                return [
                    t for t in all_tasks if not t.done and "starting" in t.keyvalues
                ]
            if v == "All":
                return [t for t in all_tasks if not t.done]
            if v == "Completed":
                return [t for t in all_tasks if t.done]
        elif self._selection_kind == "project":
            return filter_tasks(all_tasks, project=self._selection_value)
        elif self._selection_kind == "context":
            return filter_tasks(all_tasks, context=self._selection_value)
        return all_tasks

    def _current_title_icon(self) -> tuple[str, str | None]:
        """Return (title, icon_name) for the current selection."""
        if self._selection_kind == "smart":
            icon = FILTER_ICONS.get(self._selection_value)
            return self._selection_value, icon
        if self._selection_kind == "context":
            return f"@{self._selection_value}", None
        return self._selection_value, None

    def _on_grouping_mode_changed(self, index: int) -> None:
        """Handle grouping dropdown selection change."""
        self._grouping_mode = index
        self._refresh_content()

    # ── Task actions ────────────────────────────────────────────────────

    def _complete_task(self, task: Task) -> None:
        self._reload_if_changed()
        fresh, source = self._find_task(task.raw)
        if fresh is None or source is not self._todo:
            self._refresh_sidebar()
            self._refresh_content()
            return
        complete_task(self._todo, fresh, date.today())
        self._todo.save()
        self._refresh_sidebar()
        self._refresh_content()
        self.toast_overlay.add_toast(Adw.Toast(title="Task completed"))

    def _delete_task(self, task: Task) -> None:
        self._reload_if_changed()
        fresh, source = self._find_task(task.raw)
        if fresh is None or source is None:
            self._close_detail_panel()
            self._refresh_sidebar()
            self._refresh_content()
            return
        delete_task(source, fresh)
        source.save()
        self._close_detail_panel()
        self._refresh_sidebar()
        self._refresh_content()
        self.toast_overlay.add_toast(Adw.Toast(title="Task deleted"))

    # ── Drag-and-drop onto sidebar tags ────────────────────────────────

    def _on_task_dropped_on_tag(
        self,
        task_raw: str,
        tag_name: str,
        tag_kind: str,
    ) -> None:
        """Add a project or context to a task dropped on a sidebar tag."""
        self._reload_if_changed()
        task, source_file = self._find_task(task_raw)
        if task is None or source_file is None:
            return

        # Skip if the task already has this tag
        if tag_kind == "project" and tag_name in task.projects:
            return
        if tag_kind == "context" and tag_name in task.contexts:
            return

        if tag_kind == "project":
            new_line = rebuild_task_line(task, add_project=tag_name)
        else:
            new_line = rebuild_task_line(task, add_context=tag_name)

        new_task = replace_task(source_file, task, new_line)
        source_file.save()

        if self._selected_task is not None and self._selected_task.raw == task_raw:
            self._selected_task = new_task
            self.detail_panel.set_task(new_task)

        self._refresh_sidebar()
        self._refresh_content()
        prefix = "+" if tag_kind == "project" else "@"
        self.toast_overlay.add_toast(Adw.Toast(title=f"Added {prefix}{tag_name}"))

    # ── Detail panel ────────────────────────────────────────────────────

    def _on_task_selected(self, task: Task) -> None:
        """Open the detail panel for the selected task."""
        self._selected_task = task
        all_task_list = self._all_tasks()
        self.detail_panel.set_available_tags(
            all_contexts(all_task_list),
            all_projects(all_task_list),
        )
        self.detail_panel.set_task(task)
        self.detail_split.set_show_sidebar(True)

    def _close_detail_panel(self) -> None:
        self._selected_task = None
        self.detail_split.set_show_sidebar(False)

    def _on_detail_task_updated(self, old_task: Task, new_line: str) -> None:
        """Handle task update from the detail panel."""
        self._reload_if_changed()
        fresh, source = self._find_task(old_task.raw)
        if fresh is None or source is None:
            self._refresh_sidebar()
            self._refresh_content()
            return

        if new_line.startswith("__priority__:"):
            pri_str = new_line.split(":", 1)[1]
            if source is not self._todo:
                return
            if pri_str:
                new_task = set_priority(self._todo, fresh, Priority(pri_str))
            else:
                new_task = deprioritize(self._todo, fresh)
            self._todo.save()
            self._selected_task = new_task
        else:
            new_task = replace_task(source, fresh, new_line)
            source.save()
            self._selected_task = new_task

        self._refresh_sidebar()
        self._refresh_content()
        if self._selected_task is not None:
            all_task_list = self._all_tasks()
            self.detail_panel.set_available_tags(
                all_contexts(all_task_list),
                all_projects(all_task_list),
            )
            self.detail_panel.set_task(self._selected_task)

    def _on_detail_task_completed(self, task: Task) -> None:
        self._complete_task(task)
        self._close_detail_panel()

    def _on_detail_task_uncompleted(self, task: Task) -> None:
        self._reload_if_changed()
        fresh, source = self._find_task(task.raw)
        if fresh is None or source is None:
            self._close_detail_panel()
            self._refresh_sidebar()
            self._refresh_content()
            return
        if source is self._done_file:
            new_task = uncomplete_task(self._done_file, fresh)
            delete_task(self._done_file, new_task)
            self._done_file.save()
            self._todo.tasks.append(new_task)
            self._todo.save()
        elif source is self._todo:
            uncomplete_task(self._todo, fresh)
            self._todo.save()
        self._close_detail_panel()
        self._refresh_sidebar()
        self._refresh_content()
        self.toast_overlay.add_toast(Adw.Toast(title="Task uncompleted"))

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
            new_task = add_task(self._todo, result.text, date.today())
            if result.priority is not None:
                set_priority(self._todo, new_task, result.priority)
            self._todo.save()
            self._refresh_sidebar()
            self._refresh_content()
            self.toast_overlay.add_toast(Adw.Toast(title="Task added"))

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
        current_dir = self._todo.path.parent
        self._prefs_dialog.open(
            self,
            current_dir,
            self._on_dir_changed,
            on_raw_text_changed=self._on_raw_text_changed,
        )

    def _on_raw_text_changed(self, value: bool) -> None:
        self._show_raw_text = value
        self._refresh_content()

    def _on_dir_changed(self, new_dir: Path) -> None:
        self._todo = TodoFile(new_dir / "todo.txt")
        self._done_file = TodoFile(new_dir / "done.txt")
        self._close_detail_panel()
        self._load()
        self._monitor.update_paths([self._todo.path, self._done_file.path])
        self.toast_overlay.add_toast(Adw.Toast(title=f"Switched to {new_dir.name}"))
