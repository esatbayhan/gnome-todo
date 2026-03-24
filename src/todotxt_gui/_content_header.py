"""Content header widget with title, count, and grouping menu."""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gio, GLib, Gtk

from todotxt_lib import GROUPING_MODES
from ._ui import RESOURCE_PREFIX

# Translators: menu item labels for task grouping modes
_GROUPING_LABELS = (
    "Context",
    "Project",
    "Due Date",
    "Scheduled",
    "Starting",
    "Priority",
    "None",
)
# Translators: prefix shown on the grouping button, e.g. "Group by Context"
_GROUP_BY = "Group by"


@Gtk.Template(resource_path=f"{RESOURCE_PREFIX}/ui/content_header.ui")
class ContentHeader(Gtk.Box):
    """Title + count + grouping menu button for the content pane."""

    __gtype_name__ = "ContentHeader"

    icon = Gtk.Template.Child()
    title_label = Gtk.Template.Child()
    count_label = Gtk.Template.Child()
    grouping_btn = Gtk.Template.Child()
    grouping_label = Gtk.Template.Child()

    def __init__(self) -> None:
        super().__init__()
        self._on_grouping_changed: Callable[[int], None] | None = None

        # Stateful radio action for the popover menu
        action = Gio.SimpleAction.new_stateful(
            "mode",
            GLib.VariantType.new("s"),
            GLib.Variant.new_string(GROUPING_MODES[0]),
        )
        action.connect("activate", self._on_mode_activated)
        group = Gio.SimpleActionGroup()
        group.add_action(action)
        self.grouping_btn.insert_action_group("grouping", group)
        self._grouping_action = action

        # Build menu model
        menu = Gio.Menu()
        section = Gio.Menu()
        for label, mode in zip(_GROUPING_LABELS, GROUPING_MODES):
            item = Gio.MenuItem.new(label, None)
            item.set_action_and_target_value(
                "grouping.mode",
                GLib.Variant.new_string(mode),
            )
            section.append_item(item)
        menu.append_section(None, section)
        self.grouping_btn.set_menu_model(menu)

    def _on_mode_activated(
        self,
        action: Gio.SimpleAction,
        parameter: GLib.Variant,
    ) -> None:
        action.set_state(parameter)
        mode = parameter.get_string()
        index = GROUPING_MODES.index(mode)
        self.grouping_label.set_label(
            f"{_GROUP_BY} {_GROUPING_LABELS[index]}",
        )
        if self._on_grouping_changed is not None:
            self._on_grouping_changed(index)

    def update(
        self,
        title: str,
        total_count: int,
        icon_name: str | None = None,
    ) -> None:
        """Update header with new title, count, and icon."""
        self.title_label.set_label(title)
        self.count_label.set_label(str(total_count))

        if icon_name:
            self.icon.set_from_icon_name(icon_name)
            self.icon.set_visible(True)
        else:
            self.icon.set_visible(False)

    def set_grouping_visible(self, visible: bool) -> None:
        """Show or hide the grouping menu button."""
        self.grouping_btn.set_visible(visible)

    def set_grouping_index(self, index: int) -> None:
        """Set the active grouping mode without triggering the callback."""
        mode = GROUPING_MODES[index]
        self._grouping_action.set_state(GLib.Variant.new_string(mode))
        self.grouping_label.set_label(
            f"{_GROUP_BY} {_GROUPING_LABELS[index]}",
        )
