"""Command-line entry point."""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.console import Console

from agentcheck import __version__
from agentcheck.init import SETTINGS_PATH, InitError, run_init

app = typer.Typer(
    help="Check in seconds whether you can trust what Claude Code just did in your repo.",
    no_args_is_help=True,
    add_completion=False,
)
hook_app = typer.Typer(
    help="Entry points called by Claude Code hooks. Not meant to be run by hand.",
    no_args_is_help=True,
)
app.add_typer(hook_app, name="hook")

console = Console()


def _version(value: bool) -> None:
    if value:
        console.print(f"agentcheck {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", callback=_version, is_eager=True, help="Show the version."),
) -> None:
    # On Windows a piped stdout is cp1252, and rich crashes on "✓". UTF-8 everywhere, and
    # anything still unencodable is replaced instead of raising.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


@app.command()
def init() -> None:
    """Configure the Claude Code hooks in .claude/settings.json and create .agentcheck/."""
    try:
        result = run_init(Path.cwd())
    except InitError as exc:
        console.print(f"[red]✗[/red] {exc}")
        raise typer.Exit(1)

    settings = SETTINGS_PATH.as_posix()
    if result.hooks_added:
        verb = "created" if result.settings_created else "updated"
        console.print(f"[green]✓[/green] {settings} {verb}: {', '.join(result.hooks_added)} hook added")
    if result.hooks_present:
        console.print(f"[green]✓[/green] already configured: {', '.join(result.hooks_present)}")
    console.print("[green]✓[/green] .agentcheck/ ready (ignored by git)")
    if not result.on_path:
        console.print(
            "[yellow]![/yellow] `agentcheck` is not on PATH: Claude Code won't find the hooks. "
            "Install it with `uv tool install --editable <path-to-agentcheck>`."
        )


@hook_app.command("session-start")
def hook_session_start() -> None:
    """SessionStart hook. Stub until Step 2: consumes the input, prints nothing."""
    # Nothing on stdout: on SessionStart plain stdout goes into Claude's context.
    sys.stdin.read()


@hook_app.command("stop")
def hook_stop() -> None:
    """Stop hook. Stub until Step 3: consumes the input, prints nothing."""
    sys.stdin.read()
