# Pitfalls already solved — not to rediscover

One row per trap that cost time, or would have. The long story, when there is one, is in the
devlog.

| Pitfall                                                                                             | Adopted solution                                                                                     |
| --------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| A Stop hook's plain stdout is shown to nobody                                                       | The report goes in `systemMessage`, inside a JSON object that is the **only** thing on stdout        |
| SessionStart's plain stdout goes into **Claude's** context                                          | `hook session-start` prints nothing                                                                  |
| The transcript may not yet contain the current turn at Stop                                         | Final text from `last_assistant_message`; transcript only for earlier messages                       |
| SessionStart fires again on `resume` and `compact`: re-saving the baseline resets the diff silently | Baseline written once per `session_id`, never overwritten                                            |
| `git stash create` ignores untracked files — the ones an agent creates                              | Snapshot = `git write-tree` on a copy of the index after `git add -A` (ADR 0001)                     |
| `.agentcheck/` appears as `??` in the user's `git status`                                           | `.agentcheck/.gitignore` containing `*`, written by `init`                                           |
| A process spawned by Claude Code runs from a cwd nobody chose (learned in obsidian-dev-agent)       | Repo resolved from the hook input's `cwd`, never from the process cwd                                |
| `git add` on Windows prints `LF will be replaced by CRLF` warnings on stderr                        | Harmless: judge git by its exit code, never by stderr being empty                                    |
| On Windows a piped stdout is cp1252: rich raises `UnicodeEncodeError` on `✓`, and `CliRunner` tests can't see it | The CLI callback reconfigures stdout/stderr to UTF-8 with `errors="replace"`; a subprocess test runs with `PYTHONIOENCODING=cp1252` |
| `uv python install` fails with `invalid peer certificate: UnknownIssuer`: something on this machine intercepts TLS | `system-certs = true` in `%APPDATA%/uv/uv.toml` (machine config, not the project). `native-tls` is the deprecated name |
| Git Bash rewrites an argument like `/compact` into `C:/Program Files/Git/compact` before `claude -p` sees it | `MSYS_NO_PATHCONV=1` in front of the command |
| `uv tool install --editable` follows the source, **not new dependencies**: after adding tree-sitter every hook crashed on import, in every repo | `uv tool install --editable . --reinstall` after a dependency change (CLAUDE.md); and the CLI imports the analysis lazily, so hooks start even when it can't load — a test makes `tree_sitter` unimportable |
| **tree-sitter 0.26.0 crashes the process** (access violation while freeing a `Node`) on ordinary Python files — our own `test_signals.py`, and the stdlib within 200 files. Not catchable | Pinned `tree-sitter>=0.25.2,<0.26`: 0.25.2 went through 1094 stdlib files and 6000 JuTrack TS/JS files. A test runs the extractor on the crashing file in a child process. Step 7 runs the analysis in a child process anyway |
| Test fixtures (`.env.example`, code broken on purpose, manifests) trigger every signal | `fixtures/`, `testdata/`, `__fixtures__/`, `__snapshots__/` are data: no signal applies, they only count as files touched |
| pytest collects fixture files named `test_*.py` and fails on duplicate module names | `norecursedirs = ["fixtures", …]` in `pyproject.toml` |
| On Windows `Path.write_text` writes `\r\n`: a test expecting `b"a\n"` from git fails | Compare with the bytes on disk, or write with `newline="\n"` |
| The VS Code extension and the terminal run **different** Claude Code versions (2.1.281 vs 2.1.23): hook inputs differ | Treat every field beyond `session_id`/`cwd`/`transcript_path` as optional; the raw log says which version sent what |
| `git push` fails with `unable to get local issuer certificate`: same TLS interception, Git Bash's git trusts only its OpenSSL bundle | `git config http.sslBackend schannel` in this repo (as JuTrack does), so git uses the Windows store |
