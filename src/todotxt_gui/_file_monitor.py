"""Path monitoring with debounced reload for external changes."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib


class FileMonitor:
    """Watch files or directories and trigger a debounced reload."""

    def __init__(
        self,
        paths: list[Path],
        on_reload: Callable[[], None],
        debounce_ms: int = 250,
    ) -> None:
        self._paths = paths
        self._on_reload = on_reload
        self._debounce_ms = debounce_ms
        self._monitors: list[Gio.FileMonitor] = []
        self._reload_source_id: int = 0

    def setup(self) -> None:
        """Start watching all configured paths."""
        self.teardown()
        for path in self._paths:
            path.mkdir(parents=True, exist_ok=True)
            gfile = Gio.File.new_for_path(str(path))
            if path.is_dir():
                monitor = gfile.monitor_directory(Gio.FileMonitorFlags.NONE, None)
            else:
                monitor = gfile.monitor_file(Gio.FileMonitorFlags.NONE, None)
            monitor.connect("changed", self._on_file_changed)
            self._monitors.append(monitor)

    def teardown(self) -> None:
        """Cancel all active file monitors."""
        if self._reload_source_id:
            GLib.source_remove(self._reload_source_id)
            self._reload_source_id = 0
        for monitor in self._monitors:
            monitor.cancel()
        self._monitors.clear()

    def update_paths(self, paths: list[Path]) -> None:
        """Replace watched paths and restart monitoring."""
        self._paths = paths
        self.setup()

    def _on_file_changed(
        self,
        _monitor: Gio.FileMonitor,
        _file: Gio.File,
        _other: Gio.File | None,
        event_type: Gio.FileMonitorEvent,
    ) -> None:
        """Handle file-system change events; debounce into a single reload."""
        if event_type in (
            Gio.FileMonitorEvent.CHANGED,
            Gio.FileMonitorEvent.CREATED,
            Gio.FileMonitorEvent.CHANGES_DONE_HINT,
            Gio.FileMonitorEvent.DELETED,
        ):
            self._schedule_reload()

    def _schedule_reload(self) -> None:
        """Debounce rapid events into one reload after the configured delay."""
        if self._reload_source_id:
            GLib.source_remove(self._reload_source_id)
        self._reload_source_id = GLib.timeout_add(
            self._debounce_ms,
            self._on_reload_timeout,
        )

    def _on_reload_timeout(self) -> bool:
        """Fire the reload callback."""
        self._reload_source_id = 0
        self._on_reload()
        return GLib.SOURCE_REMOVE
