"""Claude Code Status Line — Two-line layout with Nerd Font icons (MD range)

Line 1: Model │ Context Bar (16 segs) │ Cost │ Tokens
Line 2: Directory │ Git Branch & Status │ 5h usage │ 7d usage │ Vim
"""

import json
import sys
import time

from .constants import RST
from .formatters import build_line1, build_line2
from .parser import parse_status_data
from .theme import build_theme, detect_theme


def main() -> None:
    """Read stdin JSON, build status lines, and print output."""
    try:
        raw = json.loads(sys.stdin.read())
    except Exception:
        # Gracefully handle missing or malformed stdin (e.g. hook not yet
        # configured, or Claude Code version that emits no JSON).
        raw = {}

    now = int(time.time())
    data = parse_status_data(raw)
    theme = build_theme(detect_theme())
    sep = f"{theme.dim} │ {RST}"

    line1 = build_line1(data, theme, now, sep)
    line2 = build_line2(data, theme, now, sep)
    print(f"{line1}\n{line2}", end="")
