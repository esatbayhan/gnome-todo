# Todo Panel Extension

This GNOME Shell extension adds a top-panel quick-add surface for the Todo Flatpak.

This project is Wayland-only. X11 sessions are not supported and should not be documented as supported.

## Requirements

- GNOME Shell 49
- `dev.bayhan.GnomeTodo` installed as a Flatpak
- The Todo app configured with a `todo.txt.d` directory

## Local install

```bash
./install-extension.sh
```

For code changes during development, use:

```bash
./install-extension.sh --reload
./watch-extension.sh
```

`--reload` tries a disable/enable cycle so you do not need to log out for every edit. A full logout is usually only needed for the first local install if GNOME Shell has not discovered the extension yet.

## Development notes

- The extension calls the helper command installed by the Flatpak:
  - `flatpak run --command=todogui-panel dev.bayhan.GnomeTodo summary --json`
  - `flatpak run --command=todogui-panel dev.bayhan.GnomeTodo add --text "Task" --json`
- Agenda rows are read-only and open the full app when clicked.
- If the Flatpak is missing or the app is not configured yet, the popup shows a dedicated state message.
