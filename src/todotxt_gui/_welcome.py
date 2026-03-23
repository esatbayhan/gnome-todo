"""Welcome dialog shown on first launch to pick a task folder."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from ._ui import RESOURCE_PREFIX


@Gtk.Template(resource_path=f"{RESOURCE_PREFIX}/ui/welcome_dialog.ui")
class WelcomeDialog(Adw.Dialog):
    """First-start dialog that asks the user to choose a task folder."""

    __gtype_name__ = "WelcomeDialog"

    choose_btn = Gtk.Template.Child()
    selected_label = Gtk.Template.Child()
    confirm_btn = Gtk.Template.Child()

    def __init__(self) -> None:
        super().__init__()
        self._callback: Callable[[Path | None], None] | None = None
        self._selected_dir: Path | None = None

    # ── Template callbacks ────────────────────────────────────────────

    @Gtk.Template.Callback()
    def on_choose_clicked(self, *_args: object) -> None:
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
            self._selected_dir = Path(path)
            self.selected_label.set_label(str(self._selected_dir))
            self.selected_label.set_visible(True)
            self.confirm_btn.set_visible(True)

    @Gtk.Template.Callback()
    def on_confirm(self, *_args: object) -> None:
        self._finish(self._selected_dir)

    # ── Open / finish ─────────────────────────────────────────────────

    def open(
        self,
        parent: Gtk.Widget,
        callback: Callable[[Path | None], None],
    ) -> None:
        """Present the welcome dialog over *parent*."""
        self._callback = callback
        self._selected_dir = None
        self.selected_label.set_visible(False)
        self.confirm_btn.set_visible(False)
        self.present(parent)

    def _finish(self, result: Path | None) -> None:
        if self._callback is not None:
            self._callback(result)
        self.set_can_close(True)
        self.close()
