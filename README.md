# Claude Code Status Line for Linux

[![CI](https://github.com/ceshine/claude-statusline-for-linux/actions/workflows/ci.yml/badge.svg)](https://github.com/ceshine/claude-statusline-for-linux/actions/workflows/ci.yml)

This repository hosts a Python package that provides a two-line status line layout for the Claude Code CLI with first-class support for Linux.

The motivation for this project is to provide a Linux-first alternative to the macOS-first bash script in [tzengyuxio/claude-statusline](https://github.com/tzengyuxio/claude-statusline/).

**Warning**: I do not own any macOS machines, so I have not verified compatibility on macOS.

Reference: [Claude Code Docs: Customize your status line](https://code.claude.com/docs/en/statusline)

## Prerequisites

- Linux (macOS compatibility is unverified).
- Python 3.11 or newer.
- `uv` installed. See the [uv documentation](https://docs.astral.sh/uv/).
- Git installed and available on `PATH` (used to render branch and status info).
- A Nerd Font installed for the glyph icons used in the statusline (otherwise icons may render as empty boxes).
- Claude Code with status line support enabled.

## Installation

1. Install the tool with `uv`:

```bash
uv tool install git+https://github.com/ceshine/claude-statusline-for-linux.git
```

Make sure `uv`'s tool bin directory (typically `~/.local/bin`) is on your `PATH` (you can run `uv tool update-shell` if needed), or use the full path `~/.local/bin/claude-statusline` below.

2. Add the following lines in `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "claude-statusline"
  }
}
```

> **Why `uv tool install` instead of `uvx`?** Running `uvx --from git+...` with an unpinned Git URL checks GitHub for updates on invocation, which adds network latency and can sporadically trigger statusline timeouts. Installing the tool locally avoids network checks and keeps startup fast.

### Update

Run the following command to update the installed tool to the latest commit on GitHub:

```bash
uv tool upgrade --reinstall claude-statusline-for-linux
```

> **Note:** `--reinstall` implies `--refresh`, ensuring `uv` fetches and rebuilds from the latest commit even if the package version number has not changed.

## Acknowledgements

- The statusline logic was adapted from the bash script in [tzengyuxio/claude-statusline](https://github.com/tzengyuxio/claude-statusline/), which primarily supports macOS.
- The [AGENTS.md](./AGENTS.md) was adapted from the example in this blog post: [Getting Good Results from Claude Code](https://www.dzombak.com/blog/2025/08/getting-good-results-from-claude-code/).
