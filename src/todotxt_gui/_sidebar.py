"""Sidebar widgets: smart filter list rows and project list."""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Pango", "1.0")
from gi.repository import Gdk, GObject, Gtk, Pango
from todotxt_lib import Task

from ._ui import RESOURCE_PREFIX

# Color palette for project circles (CSS class suffixes)
_PALETTE = [
    "blue",
    "orange",
    "red",
    "purple",
    "green",
    "teal",
    "pink",
    "indigo",
    "brown",
    "mint",
]


def project_color(name: str) -> str:
    """Deterministic color from the palette based on project name."""
    return _PALETTE[hash(name) % len(_PALETTE)]


# ── Smart filter list rows ─────────────────────────────────────────────


# (name, icon_name)
FILTER_DEFS: list[tuple[str, str]] = [
    ("Inbox", "mail-inbox-symbolic"),
    ("Today", "calendar-today-symbolic"),
    ("Scheduled", "alarm-symbolic"),
    ("Starting", "media-playback-start-symbolic"),
    ("All", "view-list-symbolic"),
    ("Completed", "object-select-symbolic"),
]


@Gtk.Template(resource_path=f"{RESOURCE_PREFIX}/ui/smart_filter_row.ui")
class SmartFilterRow(Gtk.ListBoxRow):
    """A sidebar filter row: icon + name + count."""

    __gtype_name__ = "SmartFilterRow"

    icon = Gtk.Template.Child()
    name_label = Gtk.Template.Child()
    count_label = Gtk.Template.Child()

    def __init__(self, filter_name: str, icon_name: str) -> None:
        super().__init__()
        self.filter_name = filter_name
        self.icon.set_from_icon_name(icon_name)
        self.name_label.set_label(filter_name)

    def set_count(self, count: int) -> None:
        self.count_label.set_label(str(count))


# ── Tag rows (projects & contexts) ─────────────────────────────────────


class TagRow(Gtk.ListBoxRow):
    """A sidebar row for a +project or @context tag."""

    def __init__(
        self,
        tag_name: str,
        count: int,
        *,
        tag_kind: str = "project",
        on_task_dropped: Callable[[str, str, str], None] | None = None,
    ) -> None:
        super().__init__()
        self.tag_name = tag_name
        self.tag_kind = tag_kind
        self._on_task_dropped = on_task_dropped
        self._count_label = Gtk.Label()
        self._build(count)

    def _build(self, count: int) -> None:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        self.set_child(box)

        # Colored circle
        color = project_color(self.tag_name)
        circle = Gtk.Box()
        circle.add_css_class("project-circle")
        circle.add_css_class(f"circle-{color}")
        circle.set_valign(Gtk.Align.CENTER)
        box.append(circle)

        # Tag name
        name_label = Gtk.Label(label=self.tag_name, xalign=0.0)
        name_label.set_hexpand(True)
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        box.append(name_label)

        # Count
        self._count_label.add_css_class("dim-label")
        self._count_label.set_label(str(count))
        box.append(self._count_label)

        # Drop target for receiving dragged tasks
        if self._on_task_dropped is not None:
            drop = Gtk.DropTarget.new(GObject.TYPE_STRING, Gdk.DragAction.COPY)
            drop.connect("drop", self._on_drop)
            drop.connect("enter", self._on_drop_enter)
            drop.connect("leave", self._on_drop_leave)
            self.add_controller(drop)

    def _on_drop(
        self,
        _target: Gtk.DropTarget,
        value: str,
        _x: float,
        _y: float,
    ) -> bool:
        self.remove_css_class("drop-highlight")
        if self._on_task_dropped is not None:
            self._on_task_dropped(value, self.tag_name, self.tag_kind)
        return True

    def _on_drop_enter(
        self,
        _target: Gtk.DropTarget,
        _x: float,
        _y: float,
    ) -> Gdk.DragAction:
        self.add_css_class("drop-highlight")
        return Gdk.DragAction.COPY

    def _on_drop_leave(self, _target: Gtk.DropTarget) -> None:
        self.remove_css_class("drop-highlight")

    def set_count(self, count: int) -> None:
        self._count_label.set_label(str(count))


def build_tag_list(
    tasks: list[Task],
    attr: str,
) -> list[tuple[str, int]]:
    """Return sorted (tag_name, active_count) pairs.

    *attr* is the Task attribute to read — ``"projects"`` or ``"contexts"``.
    """
    counts: dict[str, int] = {}
    for t in tasks:
        if not t.done:
            for tag in getattr(t, attr):
                counts[tag] = counts.get(tag, 0) + 1
    # Include tags that only appear in done tasks (with 0 count)
    for t in tasks:
        for tag in getattr(t, attr):
            if tag not in counts:
                counts[tag] = 0
    return sorted(counts.items())
