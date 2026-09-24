# agentcheck

Check in seconds whether you can trust what Claude Code just did in your repo. Work in progress:
see [PROJECT.md](PROJECT.md) and [docs/STATUS.md](docs/STATUS.md).

```bash
uv tool install --editable .     # puts `agentcheck` on PATH, following the source
cd your-repo && agentcheck init  # wires the SessionStart and Stop hooks
```
