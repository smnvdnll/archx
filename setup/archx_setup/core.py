from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from archx_setup.backends.pacman import PacmanBackend
from archx_setup.backends.shell_bash import BashShellBackend
from archx_setup.backends.symlink_ln import LnSymlinkBackend, SymlinkConflictPolicy
from archx_setup.backends.systemctl import SystemctlBackend
from archx_setup.backends.yay import YayBackend
from archx_setup.decisions import DecisionStore
from archx_setup.util import CommandRunner, expand_path, repo_root_from_setup_dir


class Command(Protocol):
    def apply(self, ctx: "Context") -> str: ...


@dataclass(frozen=True)
class Options:
    dry_run: bool
    non_interactive: bool
    symlink_conflict: str  # ask|replace|skip


@dataclass(frozen=True)
class Context:
    repo_root: Path
    logger: logging.Logger
    runner: CommandRunner
    decisions: DecisionStore
    options: Options
    backends: "Backends"


@dataclass(frozen=True)
class Backends:
    pacman: PacmanBackend
    yay: YayBackend
    systemctl: SystemctlBackend
    symlink: LnSymlinkBackend
    shell: BashShellBackend


class PackageCommand:
    def __init__(self, name: str, *, backend: str = "pacman") -> None:
        self.name = name
        self.backend = backend

    def apply(self, ctx: Context) -> str:
        if self.backend == "pacman":
            backend = ctx.backends.pacman
        elif self.backend == "yay":
            backend = ctx.backends.yay
        else:
            raise ValueError(f"Unknown package backend: {self.backend}")

        if backend.is_installed(self.name):
            pretty = self.name[:1].upper() + self.name[1:]
            return f"{pretty} package is already installed."
        backend.install(self.name)
        pretty = self.name[:1].upper() + self.name[1:]
        return f"Installed {pretty} package."


class ServiceCommand:
    def __init__(
        self, name: str, *, enable_now: bool = False, backend: str = "systemctl"
    ) -> None:
        self.name = name
        self.enable_now = enable_now
        self.backend = backend

    def apply(self, ctx: Context) -> str:
        if self.backend != "systemctl":
            raise ValueError(f"Unknown service backend: {self.backend}")
        if ctx.backends.systemctl.is_enabled(self.name):
            return f"{self.name} is already enabled."
        ctx.backends.systemctl.enable(self.name, now=self.enable_now)
        return f"Enabled {self.name}."


class SymlinkCommand:
    def __init__(self, source: str, target: str, *, backend: str = "ln") -> None:
        self.source = source
        self.target = target
        self.backend = backend

    def apply(self, ctx: Context) -> str:
        if self.backend != "ln":
            raise ValueError(f"Unknown symlink backend: {self.backend}")

        # Resolve source relative to repo root if it's not absolute-ish.
        src = self.source
        if not Path(src).is_absolute() and not src.startswith("~"):
            src = str(ctx.repo_root / src)

        return ctx.backends.symlink.ensure_symlink(source=src, target=self.target)


class ShellCommand:
    def __init__(
        self,
        script: list[str],
        *,
        cwd: str | None = None,
        sudo: bool = False,
        backend: str = "bash",
    ) -> None:
        self.script = script
        self.cwd = cwd
        self.sudo = sudo
        self.backend = backend

    def apply(self, ctx: Context) -> str:
        if self.backend != "bash":
            raise ValueError(f"Unknown shell backend: {self.backend}")

        # Reasonable default: run scripts from user's HOME (avoids cloning into repo).
        cwd_path = Path.home()
        if self.cwd is not None:
            cwd_path = expand_path(self.cwd)

        if ctx.options.dry_run:
            return f"Would run shell script ({len(self.script)} lines)."

        ctx.backends.shell.run_script(self.script, cwd=cwd_path, sudo=self.sudo)
        return f"Ran shell script ({len(self.script)} lines)."


class CommandFactory:
    def from_dict(self, raw: dict[str, Any]) -> Command:
        kind = raw.get("kind") or raw.get("command")
        if not isinstance(kind, str):
            raise ValueError("Command missing 'kind'")

        backend = raw.get("backend")
        if backend is not None and not isinstance(backend, str):
            raise ValueError("'backend' must be a string if present")

        if kind == "package":
            name = raw.get("name") or raw.get("package")
            if not isinstance(name, str) or not name:
                raise ValueError("package command requires 'name'")
            return PackageCommand(name, backend=backend or "pacman")

        if kind == "service":
            name = raw.get("name")
            if not isinstance(name, str) or not name:
                raise ValueError("service command requires 'name'")
            enable_now = bool(raw.get("enable_now", False))
            return ServiceCommand(name, enable_now=enable_now, backend=backend or "systemctl")

        if kind == "symlink":
            source = raw.get("source") or raw.get("real")
            target = raw.get("target") or raw.get("pointer")
            if not isinstance(source, str) or not isinstance(target, str):
                raise ValueError("symlink command requires 'source' and 'target'")
            return SymlinkCommand(source, target, backend=backend or "ln")

        if kind == "shell":
            script = raw.get("script")
            if isinstance(script, str):
                lines = [script]
            elif isinstance(script, list) and all(isinstance(x, str) for x in script):
                lines = list(script)
            else:
                raise ValueError("shell command requires 'script' (string or list of strings)")

            cwd = raw.get("cwd")
            if cwd is not None and not isinstance(cwd, str):
                raise ValueError("'cwd' must be a string if present")

            sudo = raw.get("sudo", False)
            if not isinstance(sudo, bool):
                raise ValueError("'sudo' must be a boolean if present")

            return ShellCommand(
                lines,
                cwd=cwd,
                sudo=sudo,
                backend=backend or "bash",
            )

        raise ValueError(f"Unknown command kind: {kind}")


def build_context(
    *,
    setup_dir: Path,
    decisions_path: Path,
    options: Options,
    logger: logging.Logger,
) -> Context:
    repo_root = repo_root_from_setup_dir(setup_dir)
    runner = CommandRunner(dry_run=options.dry_run, logger=logger)
    decisions = DecisionStore(decisions_path, logger)

    pacman = PacmanBackend(runner=runner, logger=logger)
    yay = YayBackend(runner=runner, logger=logger)
    systemctl = SystemctlBackend(runner=runner, logger=logger)
    symlink = LnSymlinkBackend(
        runner=runner,
        logger=logger,
        decisions=decisions,
        non_interactive=options.non_interactive,
        conflict_policy=SymlinkConflictPolicy(mode=options.symlink_conflict),
    )
    shell = BashShellBackend(runner=runner, logger=logger)

    return Context(
        repo_root=repo_root,
        logger=logger,
        runner=runner,
        decisions=decisions,
        options=options,
        backends=Backends(
            pacman=pacman,
            yay=yay,
            systemctl=systemctl,
            symlink=symlink,
            shell=shell,
        ),
    )


