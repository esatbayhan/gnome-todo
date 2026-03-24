"""Keyboard shortcuts window and filter quick-access mappings."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

# Smart filter name → icon
FILTER_ICONS: dict[str, str] = {
    "Inbox": "mail-unread-symbolic",
    "Today": "x-office-calendar-symbolic",
    "Scheduled": "alarm-symbolic",
    "Starting": "media-playback-start-symbolic",
    "All": "view-list-symbolic",
    "Completed": "object-select-symbolic",
}

# Ordered filter names for Ctrl+1..6 quick access
FILTER_BY_NUMBER: list[str] = [
    "Inbox",
    "Today",
    "Scheduled",
    "Starting",
    "All",
    "Completed",
]


def build_shortcuts_window() -> Gtk.ShortcutsWindow:
    """Build the keyboard shortcuts help overlay."""
    win = Gtk.ShortcutsWindow()

    section = Gtk.ShortcutsSection(section_name="shortcuts", visible=True)

    # Tasks group
    tasks_group = Gtk.ShortcutsGroup(title="Tasks", visible=True)
    for accel, title in [
        ("<Ctrl>n", "New task"),
        ("<Ctrl>f", "Search tasks"),
        ("Escape", "Close detail panel"),
    ]:
        tasks_group.append(
            Gtk.ShortcutsShortcut(
                accelerator=accel,
                title=title,
                visible=True,
            )
        )
    section.append(tasks_group)

    # Navigation group
    nav_group = Gtk.ShortcutsGroup(title="Navigation", visible=True)
    for accel, title in [
        ("<Ctrl>1", "Inbox"),
        ("<Ctrl>2", "Today"),
        ("<Ctrl>3", "Scheduled"),
        ("<Ctrl>4", "Starting"),
        ("<Ctrl>5", "All tasks"),
        ("<Ctrl>6", "Completed"),
        ("F9", "Toggle sidebar"),
    ]:
        nav_group.append(
            Gtk.ShortcutsShortcut(
                accelerator=accel,
                title=title,
                visible=True,
            )
        )
    section.append(nav_group)

    # General group
    general_group = Gtk.ShortcutsGroup(title="General", visible=True)
    for accel, title in [
        ("<Ctrl>comma", "Preferences"),
        ("<Ctrl>question", "Keyboard shortcuts"),
    ]:
        general_group.append(
            Gtk.ShortcutsShortcut(
                accelerator=accel,
                title=title,
                visible=True,
            )
        )
    section.append(general_group)

    win.add_section(section)
    return win
