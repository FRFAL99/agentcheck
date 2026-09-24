"""Path globs with a real `**`, the same on every Python version.

`fnmatch` lets `*` cross `/`, and `PurePath.match` has no `**` before Python 3.13. Rules, as in
`.gitignore`: a pattern without `/` matches the file name at any depth (`.env*`); a pattern with `/`
is relative to the repo root (`tests/**`), and a leading `**/` makes it match at any depth.
"""

from __future__ import annotations

import re
from functools import lru_cache


@lru_cache(maxsize=256)
def _compile(pattern: str) -> re.Pattern[str]:
    anchored = "/" in pattern.rstrip("/")
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    prefix = "" if anchored else "(?:.*/)?"
    return re.compile(prefix + "".join(out) + r"\Z")


def matches(path: str, patterns: list[str] | tuple[str, ...]) -> bool:
    return any(_compile(p).match(path) for p in patterns)
