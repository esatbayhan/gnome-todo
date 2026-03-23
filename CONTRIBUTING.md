# Contributing

Contributions are welcome! Here's how to get started.

## Prerequisites

- `flatpak`
- `flatpak-builder`

See the [README](README.md#requirements-for-building) for installation
instructions per distribution.

## Building

Clone the repository and run the Flatpak build script:

```bash
git clone https://github.com/esatbayhan/gnome-todo.git
cd gnome-todo
./run-flatpak.sh
```

This installs the GNOME SDK/runtime if needed, builds the app, and installs it
as a user Flatpak.

## Running tests

```bash
PYTHONPATH=src python -m pytest tests/ -v
```

## Code style

- **Python** — use type hints, follow PEP 8. Format with `ruff`.
- **UI** — static widget trees go in Blueprint `.blp` files under `src/ui/`.
  Dynamic content is handled in Python.
- Keep changes focused. One feature or fix per pull request.

## Submitting changes

1. Fork the repository
2. Create a feature branch (`git checkout -b my-feature`)
3. Make your changes and add tests if applicable
4. Ensure all tests pass
5. Open a pull request with a clear description of what you changed and why
