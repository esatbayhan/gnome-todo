"""GTK helpers for detail-panel tag chips and suggestions."""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk
from todotxt_lib import TagFlowState, normalize_tag_input


def rebuild_tag_flow(
    flow: Gtk.FlowBox,
    state: TagFlowState,
    *,
    on_remove: Callable[[str], None],
    on_add: Callable[[str], None],
) -> None:
    """Rebuild a flow with removable chips followed by suggestion buttons."""
    _clear_flow(flow)

    for item in state.items:
        flow.append(_build_item_chip(item, on_remove))
    for item in state.suggestions:
        flow.append(_build_suggestion_chip(item, on_add))


def _clear_flow(flow: Gtk.FlowBox) -> None:
    while True:
        child = flow.get_child_at_index(0)
        if child is None:
            return
        flow.remove(child)


def _build_item_chip(
    item: str,
    on_remove: Callable[[str], None],
) -> Gtk.Box:
    chip_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
    chip_box.add_css_class("detail-chip")

    remove_btn = Gtk.Button(icon_name="window-close-symbolic")
    remove_btn.add_css_class("flat")
    remove_btn.add_css_class("circular")
    remove_btn.add_css_class("chip-remove-btn")
    remove_btn.connect("clicked", _make_item_handler(on_remove, item))
    chip_box.append(remove_btn)

    chip_box.append(Gtk.Label(label=item))
    return chip_box


def _build_suggestion_chip(
    item: str,
    on_add: Callable[[str], None],
) -> Gtk.Button:
    button = Gtk.Button(label=item)
    button.add_css_class("suggestion-chip")
    button.add_css_class("flat")
    button.connect("clicked", _make_item_handler(on_add, item))
    return button


def _make_item_handler(
    callback: Callable[[str], None],
    item: str,
) -> Callable[[object], None]:
    def handler(_btn: object) -> None:
        callback(item)

    return handler
