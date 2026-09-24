"""Command-line entry point."""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape

from agentcheck import __version__, gitstate
from agentcheck.hooks import run_hook
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


@app.command()
def run(
    from_: str = typer.Option(..., "--from", help="Tree, commit or ref to compare from."),
    to: str = typer.Option(None, "--to", help="Tree, commit or ref to compare to. Default: the working tree."),
) -> None:
    """Run the analysis by hand between two states of the repo, without hooks (for debugging)."""
    # Imported here, not at the top: the hook commands share this module, and a missing or broken
    # analysis dependency must not stop them from starting.
    from agentcheck.config import ConfigError, load_config
    from agentcheck.structural.turn import analyze_turn

    repo = gitstate.repo_root(Path.cwd())
    if repo is None:
        console.print("[red]✗[/red] not inside a git repository.")
        raise typer.Exit(1)
    try:
        config = load_config(repo)
        new = to if to is not None else gitstate.snapshot(repo)
        result = analyze_turn(repo, from_, new, config)
    except (gitstate.GitError, ConfigError) as exc:
        console.print(f"[red]✗[/red] {escape(str(exc))}")
        raise typer.Exit(1)

    console.print(f"{len(result.changes)} files changed, {len(result.findings)} findings")
    for finding in result.findings:
        console.print("[yellow]![/yellow] " + escape(f"[{finding.severity}] {finding.message}"), highlight=False)
    for error in result.errors:
        console.print("[red]✗[/red] " + escape(f"signal failed, {error}"), highlight=False)


@app.command("analyze-turn", hidden=True)
def analyze_turn_command(
    repo: Path = typer.Option(..., "--repo"),
    from_: str = typer.Option(..., "--from"),
    to: str = typer.Option(..., "--to"),
) -> None:
    """Internal: the Stop hook runs the analysis through this, in a child process. Prints JSON."""
    import json

    from agentcheck.config import Config, ConfigError, load_config
    from agentcheck.structural.turn import analyze_turn

    errors = []
    try:
        config = load_config(repo)
    except ConfigError as exc:
        config = Config()
        errors.append(f"config: {exc}")
    result = analyze_turn(repo, from_, to, config)
    sys.stdout.write(
        json.dumps(
            {
                "changes": len(result.changes),
                "findings": [f.to_dict() for f in result.findings],
                "errors": errors + result.errors,
            }
        )
    )


def _run_hook(event: str) -> None:
    # Bytes, decoded as UTF-8: Claude Code sends UTF-8, and on Windows sys.stdin would be cp1252.
    raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    out = run_hook(event, raw)
    if out:
        sys.stdout.write(out)


@hook_app.command("session-start")
def hook_session_start() -> None:
    """SessionStart hook: saves the session baseline. Prints nothing."""
    # Nothing on stdout: on SessionStart plain stdout goes into Claude's context.
    _run_hook("SessionStart")


@hook_app.command("user-prompt-submit")
def hook_user_prompt_submit() -> None:
    """UserPromptSubmit hook: marks where the turn starts. Prints nothing."""
    # Nothing on stdout: on UserPromptSubmit plain stdout goes into Claude's context.
    _run_hook("UserPromptSubmit")


@hook_app.command("stop")
def hook_stop() -> None:
    """Stop hook: records what changed in this turn. Prints nothing."""
    _run_hook("Stop")
