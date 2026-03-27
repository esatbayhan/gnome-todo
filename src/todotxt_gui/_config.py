"""Persistent configuration stored as JSON in XDG_CONFIG_HOME."""

from __future__ import annotations

import json
import os
from pathlib import Path

_APP_ID = "todotxt-gui"


def config_path() -> Path:
    """Return the path to the JSON config file."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg is not None else Path.home() / ".config"
    return base / _APP_ID / "config.json"


def load_config() -> dict[str, object]:
    """Load the config file, returning an empty dict if missing."""
    p = config_path()
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def save_config(data: dict[str, object]) -> None:
    """Write *data* to the config file, creating directories as needed."""
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_todo_dir() -> Path | None:
    """Return the configured todo directory, or ``None``."""
    d = load_config().get("todo_dir")
    return Path(d) if d else None


def set_todo_dir(directory: Path) -> None:
    """Persist *directory* as the todo directory."""
    cfg = load_config()
    cfg["todo_dir"] = str(directory)
    save_config(cfg)


def get_show_raw_text() -> bool:
    """Return whether to show raw task text (True) or clean text (False)."""
    return bool(load_config().get("show_raw_text", False))


def set_show_raw_text(value: bool) -> None:
    """Persist the show-raw-text preference."""
    cfg = load_config()
    cfg["show_raw_text"] = value
    save_config(cfg)


def get_auto_normalize_multi_task_files() -> bool:
    """Return whether multi-task files should normalize on mutation."""
    return bool(load_config().get("auto_normalize_multi_task_files", True))


def set_auto_normalize_multi_task_files(value: bool) -> None:
    """Persist the multi-task normalization preference."""
    cfg = load_config()
    cfg["auto_normalize_multi_task_files"] = value
    save_config(cfg)
