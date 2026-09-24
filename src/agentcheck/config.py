"""Configuration: the defaults of PROJECT.md §8, overridden by `.agentcheck/config.toml`.

Only the keys something reads exist here; `[llm]` and `[feedback_loop]` arrive with the phases that
use them. Unknown keys are ignored, so a config written for a later version still loads.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path

CONFIG_PATH = Path(".agentcheck") / "config.toml"

# PROJECT.md §8 has `migrations/**` and `tests/**`, anchored at the root. Django keeps migrations in
# every app and monorepos keep tests in every package: the defaults match at any depth.
DEFAULT_SENSITIVE = [".env*", "**/migrations/**", ".github/workflows/**"]
DEFAULT_TESTS = [
    "**/tests/**",
    "**/test/**",
    "**/__tests__/**",
    "**/test_*.py",
    "**/*_test.py",
    "**/*.test.*",
    "**/*.spec.*",
]


class ConfigError(Exception):
    pass


@dataclass
class Config:
    max_lines: int = 8
    many_files_threshold: int = 15
    sensitive: list[str] = field(default_factory=lambda: list(DEFAULT_SENSITIVE))
    tests: list[str] = field(default_factory=lambda: list(DEFAULT_TESTS))


# (toml table, toml key) -> Config attribute
_KEYS = {
    ("report", "max_lines"): "max_lines",
    ("risk", "many_files_threshold"): "many_files_threshold",
    ("paths", "sensitive"): "sensitive",
    ("paths", "tests"): "tests",
}


def load_config(repo: Path) -> Config:
    """The repo's config; the defaults when there is no file. Raises ConfigError on a bad file."""
    config = Config()
    path = repo / CONFIG_PATH
    if not path.exists():
        return config
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise ConfigError(f"{CONFIG_PATH.as_posix()} is not valid TOML: {exc}") from exc

    types = {f.name: f.type for f in fields(Config)}
    for (table, key), attr in _KEYS.items():
        value = data.get(table, {}).get(key) if isinstance(data.get(table), dict) else None
        if value is None:
            continue
        expected_list = "list" in str(types[attr])
        ok = (
            isinstance(value, list) and all(isinstance(v, str) for v in value)
            if expected_list
            else isinstance(value, int) and not isinstance(value, bool) and value > 0
        )
        if not ok:
            kind = "a list of strings" if expected_list else "a positive integer"
            raise ConfigError(f"[{table}] {key} in {CONFIG_PATH.as_posix()} must be {kind}")
        setattr(config, attr, value)
    return config
