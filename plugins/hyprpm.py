from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from typing import Any, Sequence

from archx_setup.plugins.api import Command, CommandHandler, Context


def _parse_hyprpm_list(text: str) -> dict[str, dict[str, bool]]:
    """
    Parse `hyprpm list` output into:
        { repo_name: { plugin_name: enabled_bool } }

    Expected format (unicode art may vary):
      → Repository hyprland-plugins:
        │ Plugin hyprexpo
        └─ enabled: true
    """
    repos: dict[str, dict[str, bool]] = {}
    current_repo: str | None = None
    current_plugin: str | None = None

    repo_re = re.compile(r"Repository\s+(.+?):\s*$")
    plugin_re = re.compile(r"Plugin\s+([A-Za-z0-9_.-]+)\s*$")
    enabled_re = re.compile(r"enabled:\s*(true|false)\s*$", re.IGNORECASE)

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        m_repo = repo_re.search(line)
        if m_repo:
            current_repo = m_repo.group(1).strip()
            repos.setdefault(current_repo, {})
            current_plugin = None
            continue

        m_plugin = plugin_re.search(line)
        if m_plugin:
            current_plugin = m_plugin.group(1)
            if current_repo is not None:
                repos.setdefault(current_repo, {}).setdefault(current_plugin, False)
            continue

        m_enabled = enabled_re.search(line)
        if m_enabled and current_repo is not None and current_plugin is not None:
            repos.setdefault(current_repo, {})[current_plugin] = (m_enabled.group(1).lower() == "true")

    return repos


class HyprpmEnsurePluginEnabledCommand:
    def __init__(
        self,
        *,
        repo_name: str | None,
        repo_url: str | None,
        plugin: str,
        update_before_add: bool,
    ) -> None:
        self.repo_name = repo_name
        self.repo_url = repo_url
        self.plugin = plugin
        self.update_before_add = update_before_add

    def _list_state(self, ctx: Context) -> dict[str, dict[str, bool]]:
        res = ctx.runner.run(["hyprpm", "list"], check=True, capture=True)
        return _parse_hyprpm_list(res.stdout)

    def apply(self, ctx: Context) -> str:
        if ctx.options.dry_run:
            repo_msg = f" from repo {self.repo_name!r}" if self.repo_name else ""
            return f"Would ensure HyprPM plugin {self.plugin!r} is enabled{repo_msg}."

        state = self._list_state(ctx)

        # If the repo is known and the plugin is already enabled in that repo, we are done.
        if self.repo_name and state.get(self.repo_name, {}).get(self.plugin) is True:
            return f"HyprPM plugin {self.plugin} is already enabled."

        # If the plugin is enabled in any repo (repo_name not provided or changed), also treat as done.
        if not self.repo_name:
            for _repo, plugins in state.items():
                if plugins.get(self.plugin) is True:
                    return f"HyprPM plugin {self.plugin} is already enabled."

        # Ensure repo is added when we have enough info.
        need_add_repo = False
        if self.repo_name:
            need_add_repo = self.repo_name not in state
        # If repo_name isn't given, we can't reliably check; only add if repo_url is explicitly provided.
        if not self.repo_name and self.repo_url:
            need_add_repo = True

        if need_add_repo:
            if not self.repo_url:
                raise ValueError(
                    "hyprpm command requires 'repo_url' when the repository is not present (or repo_name is omitted)."
                )
            if self.update_before_add:
                ctx.runner.run(["hyprpm", "update"], check=True, capture=True)
            # `hyprpm add` prompts; run it non-interactively.
            ctx.runner.run(
                ["bash", "-lc", f"echo y | hyprpm add {self.repo_url}"],
                check=True,
                capture=True,
            )

        # Enable the plugin (hyprpm will fail if it can't be found/installed).
        ctx.runner.run(["hyprpm", "enable", self.plugin], check=True, capture=True)
        return f"Enabled HyprPM plugin {self.plugin}."


@dataclass(frozen=True)
class HyprpmPlugin:
    name: str = "archx.hyprpm.default"

    def handlers(self) -> Sequence[CommandHandler]:
        return (CommandHandler(kind="hyprpm", backend=None),)

    def is_available(self, ctx: Context) -> tuple[bool, str | None]:
        if ctx.runner.dry_run:
            return True, None
        if shutil.which("hyprpm") is None:
            return False, "`hyprpm` not found on PATH"
        return True, None

    def from_dict(self, raw: dict[str, Any], ctx: Context) -> Command:
        plugin = raw.get("plugin") or raw.get("name")
        if not isinstance(plugin, str) or not plugin:
            raise ValueError("hyprpm command requires 'plugin' (or 'name')")

        repo_name = raw.get("repo_name") or raw.get("repo")
        if repo_name is not None and (not isinstance(repo_name, str) or not repo_name):
            raise ValueError("'repo_name' must be a non-empty string if present")

        repo_url = raw.get("repo_url") or raw.get("url")
        if repo_url is not None and (not isinstance(repo_url, str) or not repo_url):
            raise ValueError("'repo_url' must be a non-empty string if present")

        update_before_add = raw.get("update_before_add", True)
        if not isinstance(update_before_add, bool):
            raise ValueError("'update_before_add' must be a boolean if present")

        return HyprpmEnsurePluginEnabledCommand(
            repo_name=repo_name,
            repo_url=repo_url,
            plugin=plugin,
            update_before_add=update_before_add,
        )

PLUGIN = HyprpmPlugin()
