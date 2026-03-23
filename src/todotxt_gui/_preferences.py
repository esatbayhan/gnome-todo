"""Preferences dialog for changing the task folder."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from ._config import get_show_raw_text, set_show_raw_text, set_todo_dir
from ._ui import RESOURCE_PREFIX


@Gtk.Template(resource_path=f"{RESOURCE_PREFIX}/ui/preferences_dialog.ui")
class PreferencesDialog(Adw.Dialog):
    """Settings dialog with a directory picker for the task folder."""

    __gtype_name__ = "PreferencesDialog"

    dir_row = Gtk.Template.Child()
    raw_text_row = Gtk.Template.Child()

    def __init__(self) -> None:
        super().__init__()
        self._callback: Callable[[Path], None] | None = None
        self._on_raw_text_changed: Callable[[bool], None] | None = None

    # ── Template callbacks ────────────────────────────────────────────

    @Gtk.Template.Callback()
    def on_change_dir(self, *_args: object) -> None:
        dialog = Gtk.FileDialog()
        dialog.set_title("Choose Task Folder")
        dialog.select_folder(
            self.get_root(),  # type: ignore[arg-type]
            None,
            self._on_folder_selected,
        )

    def _on_folder_selected(
        self,
        dialog: Gtk.FileDialog,
        result: object,
    ) -> None:
        try:
            folder = dialog.select_folder_finish(result)  # type: ignore[arg-type]
        except GLib.Error:
            return  # user cancelled
        path = folder.get_path()
        if path is not None:
            new_dir = Path(path)
            # Ensure the files exist in the new directory.
            (new_dir / "todo.txt").touch(exist_ok=True)
            (new_dir / "done.txt").touch(exist_ok=True)
            set_todo_dir(new_dir)
            self.dir_row.set_subtitle(str(new_dir))
            if self._callback is not None:
                self._callback(new_dir)

    @Gtk.Template.Callback()
    def on_raw_text_toggled(self, row: object, _pspec: object) -> None:
        value = row.get_active()
        set_show_raw_text(value)
        if self._on_raw_text_changed is not None:
            self._on_raw_text_changed(value)

    # ── Open ──────────────────────────────────────────────────────────

    def open(
        self,
        parent: Gtk.Widget,
        current_dir: Path,
        callback: Callable[[Path], None],
        *,
        on_raw_text_changed: Callable[[bool], None] | None = None,
    ) -> None:
        """Present the preferences dialog over *parent*."""
        self._callback = callback
        self._on_raw_text_changed = on_raw_text_changed
        self.dir_row.set_subtitle(str(current_dir))
        self.raw_text_row.set_active(get_show_raw_text())
        self.present(parent)
