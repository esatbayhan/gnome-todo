"""Reusable small widgets: priority dots, due date badges, context chips."""

from __future__ import annotations

from datetime import date

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gtk, Pango
from todotxt_lib import Priority


def format_relative_date(due_str: str) -> tuple[str, str]:
    """Return (display_text, css_class) for a due date string.

    css_class is one of: 'due-overdue', 'due-today', 'due-upcoming'.
    """
    try:
        due = date.fromisoformat(due_str)
    except ValueError:
        return (due_str, "due-upcoming")

    today = date.today()
    delta = (due - today).days

    if delta < 0:
        return (due.strftime("%b %-d"), "due-overdue")
    if delta == 0:
        return ("Today", "due-today")
    if delta == 1:
        return ("Tomorrow", "due-upcoming")
    if delta < 7:
        return (due.strftime("%A"), "due-upcoming")
    return (due.strftime("%b %-d"), "due-upcoming")


# Priority → CSS color class suffix
_PRIORITY_COLORS: dict[Priority, str] = {
    Priority.A: "A",
    Priority.B: "B",
    Priority.C: "C",
    Priority.D: "D",
}


def priority_dot(pri: Priority) -> Gtk.Widget:
    """Return a small colored circle for the given priority."""
    dot = Gtk.Box()
    dot.add_css_class("priority-dot")
    suffix = _PRIORITY_COLORS.get(pri, "D")
    dot.add_css_class(f"priority-{suffix}")
    dot.set_valign(Gtk.Align.CENTER)
    dot.set_tooltip_text(f"Priority {pri.value}")
    return dot


def due_date_badge(due_str: str) -> Gtk.Widget:
    """Return a colored badge label for the given due date string."""
    text, css_class = format_relative_date(due_str)
    label = Gtk.Label(label=text)
    label.add_css_class("due-badge")
    label.add_css_class(css_class)
    label.set_valign(Gtk.Align.CENTER)
    return label


def scheduled_badge(date_str: str) -> Gtk.Widget:
    """Return a colored badge for a scheduled: date."""
    text, _ = format_relative_date(date_str)
    label = Gtk.Label(label=f"Sched: {text}")
    label.add_css_class("due-badge")
    label.add_css_class("scheduled")
    label.set_valign(Gtk.Align.CENTER)
    return label


def starting_badge(date_str: str) -> Gtk.Widget:
    """Return a colored badge for a starting: date."""
    text, _ = format_relative_date(date_str)
    label = Gtk.Label(label=f"Start: {text}")
    label.add_css_class("due-badge")
    label.add_css_class("starting")
    label.set_valign(Gtk.Align.CENTER)
    return label


def context_chip(name: str) -> Gtk.Widget:
    """Return a small pill-shaped label for a @context."""
    label = Gtk.Label(label=f"@{name}")
    label.add_css_class("context-chip")
    label.set_valign(Gtk.Align.CENTER)
    label.set_ellipsize(Pango.EllipsizeMode.END)
    return label


def project_label(name: str) -> Gtk.Widget:
    """Return a dim label for a +project tag."""
    label = Gtk.Label(label=f"+{name}")
    label.add_css_class("project-tag")
    label.add_css_class("dim-label")
    label.set_valign(Gtk.Align.CENTER)
    label.set_ellipsize(Pango.EllipsizeMode.END)
    return label
