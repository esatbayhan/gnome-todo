"""Todo.txt GTK4/libadwaita GUI application."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk

from ._config import set_todo_dir
from ._core import done_file_path, has_configured_dir, todo_file_path
from ._ui import RESOURCE_PREFIX
from ._welcome import WelcomeDialog
from ._window import TodoWindow

try:
    from todotxt_gui_devtools import screenshot as _dev_screenshot
except ImportError:
    _dev_screenshot = None


@dataclass(frozen=True)
class RuntimeOptions:
    """Command-line options handled before GApplication sees argv."""

    force_welcome: bool = False
    screenshot: object | None = None


def _load_css() -> None:
    """Load the custom CSS stylesheet from GResource."""
    css_provider = Gtk.CssProvider()
    css_provider.load_from_resource(f"{RESOURCE_PREFIX}/style.css")
    display = Gdk.Display.get_default()
    assert display is not None
    Gtk.StyleContext.add_provider_for_display(
        display,
        css_provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )


class _TodoGuiApp(Adw.Application):
    """Adwaita application for todo.txt."""

    def __init__(self, options: RuntimeOptions) -> None:
        super().__init__(application_id="dev.bayhan.GnomeTodo")
        self._options = options
        self._exit_code = 0

    def do_activate(self) -> None:
        _load_css()

        if self._options.screenshot is not None and not has_configured_dir():
            print(
                "[screenshot] TODO_DIR or config must be set before screenshot mode",
                file=sys.stderr,
            )
            self._exit_code = 2
            self.quit()
            return

        if self._options.force_welcome or not has_configured_dir():
            # First start: show welcome dialog to pick a folder.
            temp_win = Adw.ApplicationWindow(application=self)
            temp_win.set_default_size(480, 400)
            temp_win.present()

            welcome = WelcomeDialog()

            def on_dir_chosen(chosen_dir: Path | None) -> None:
                temp_win.destroy()
                if chosen_dir is None:
                    self.quit()
                    return
                set_todo_dir(chosen_dir)
                (chosen_dir / "todo.txt").touch(exist_ok=True)
                (chosen_dir / "done.txt").touch(exist_ok=True)
                self._show_main_window()

            welcome.open(temp_win, on_dir_chosen)
        else:
            self._show_main_window()

    def _show_main_window(self) -> None:
        """Create and present the main application window."""
        win = TodoWindow(
            application=self,
            todo_path=todo_file_path(),
            done_path=done_file_path(),
        )
        if self._options.screenshot is not None:
            assert _dev_screenshot is not None
            _dev_screenshot.prepare_window_for_screenshot(win, self._options.screenshot)
        win.present()
        if self._options.screenshot is not None:
            self._schedule_screenshot(win)

    def _schedule_screenshot(self, win: TodoWindow) -> None:
        """Delegate screenshot capture to the optional devtools package."""
        assert _dev_screenshot is not None
        screenshot = self._options.screenshot
        assert screenshot is not None
        _dev_screenshot.schedule_screenshot_capture(
            self,
            win,
            screenshot,
            self._set_exit_code,
        )

    @property
    def exit_code(self) -> int:
        """Return the intended process exit code."""
        return self._exit_code

    def _set_exit_code(self, value: int) -> None:
        """Record a non-zero exit code from optional helpers."""
        self._exit_code = value


def parse_runtime_options(argv: list[str]) -> tuple[list[str], RuntimeOptions]:
    """Parse core options and optionally delegate dev-only flags."""
    force_welcome = "--first-run" in argv[1:]
    cleaned = [argv[0], *[arg for arg in argv[1:] if arg != "--first-run"]]

    if _dev_screenshot is None:
        if any(arg.startswith("--screenshot-") for arg in cleaned[1:]):
            raise ValueError("Screenshot mode is unavailable in this build")
        return cleaned, RuntimeOptions(force_welcome=force_welcome)

    cleaned, screenshot = _dev_screenshot.parse_screenshot_options(cleaned)
    return cleaned, RuntimeOptions(
        force_welcome=force_welcome,
        screenshot=screenshot,
    )


def run(argv: list[str] | None = None) -> int:
    """Entry point for the todogui command."""
    argv = list(sys.argv if argv is None else argv)
    try:
        app_argv, options = parse_runtime_options(argv)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2

    app = _TodoGuiApp(options)
    app.run(app_argv)
    return app.exit_code
