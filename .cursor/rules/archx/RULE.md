---
description: "archx repo structure + workflows (configs, plugins, Hyprland, wallpapers)"
alwaysApply: true
---

You are working in the `archx` repo.

## High-level architecture (read this first)

### Entry point
- Run the setup from repo root with: `./archx-install`
- Dry-run: `./archx-install --dry-run`
- `archx-install` runs `python -m archx_setup` and points it at the config directory `archx/`.

### Declarative configs
- Configs live in `archx/` (TOML preferred).
- They are loaded **recursively** and executed in **sorted path order**.
- Current convention: one file per “stage”:
  - `archx/000_essentials.toml`
  - `archx/001_apps.toml`
  - `archx/002_archx.toml`
  - `archx/003_desktop.toml`
  - `archx/004_dm.toml`
  - `archx/005_boot.toml`

### Dotfiles payloads
- User/system configuration payloads live under `dotfiles/`.
- Setup config uses `[[symlink]] source = "dotfiles/..."` to install them into the system.

### Command execution model (plugins)
- Core runner is `archx_setup/`.
- Built-in command kinds are implemented in `archx_setup/plugins/builtin.py` and backends under `archx_setup/plugins/builtin_backends/`.
- External (repo) command plugins live in `plugins/` (plain `*.py` files exporting `PLUGIN = ...`).
- `archx-install` passes `--plugins-dir ./plugins` so these are loaded automatically.

### Important plugin behavior
- `hyprpm` command kind is provided by `plugins/hyprpm.py`
- `vicinae-extension-store` command kind is provided by `plugins/vicinae_extension_store.py`

## TOML config rules (critical)

### Preferred style
Use TOML “kind tables”:
- `[[package]]`, `[[packages]]`
- `[[symlink]]`
- `[[service]]`
- `[[shell]]`
- any custom kind like `[[hyprpm]]`, `[[vicinae-extension-store]]`

### Ordering semantics
This repo supports **interleaving** TOML array-of-tables while preserving on-disk order, e.g.:
`[[package]] ...`, then `[[symlink]] ...`, then another `[[package]] ...`

Implementation detail:
- The TOML loader scans the TOML text for `[[...]]` headers in order to preserve appearance order.
- Do NOT reorder blocks casually in configs; ordering is meaningful.

### When to use `[[command]]`
Use `[[command]]` only when you need explicit ordering across many kinds and want a fully-generic representation.

## Hyprland configuration

### File layout
- Main entry: `dotfiles/hypr/hyprland.conf`
- It sources fragments under `dotfiles/hypr/conf.d/`:
  - `00_monitors.conf`
  - `00_programs.conf`
  - `01_autostart.conf`
  - `02_environment.conf`
  - `03_general.conf`
  - `04_input.conf`
  - `05_binds.conf`
  - `06_plugins.conf`
  - `07_gestures.conf`
  - `08_window_rules.conf`

### Rule for edits
- Prefer editing the appropriate file under `dotfiles/hypr/conf.d/` instead of editing `hyprland.conf` directly.
- Preserve ordering of `source = conf.d/...` lines unless you intentionally want different runtime behavior.

## Wallpapers (awww + rotation)

- Wallpapers are stored in-repo at `dotfiles/archx/wallpaper/`.
- They are used at runtime via the symlinked path `~/.config/archx/wallpaper/`.
- Rotation script: `dotfiles/archx/awww-wallpaper-cycle.sh`
- Hyprland autostart launches:
  - `awww-daemon`
  - the rotation script with flags like `--interval` and transition options

Rule:
- The rotation script should control `awww img ...` calls.
- Starting `awww-daemon` is done by Hyprland autostart (not by the script).

## Safety + style conventions

- Prefer TOML configs under `archx/` (not JSON) unless there’s a strong reason.
- Keep setup commands idempotent (safe to re-run).
- Avoid adding “shell” unless a plugin is truly not worth it; prefer new external plugins in `plugins/` for repeatable logic.
- When changing config paths or repo layout, always update:
  - `archx-install`
  - `README.md` (repo-level)
  - `archx_setup/README.md` (runner-level)


