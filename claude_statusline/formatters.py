"""Formatting functions for each status line segment."""

import subprocess
from pathlib import Path
from datetime import datetime, timezone

from .theme import pct_color
from .models import RateLimitWindow, StatusData, Theme
from .constants import BAR_SEGMENTS, BOLD, ICON_COST, ICON_CTX, ICON_DIR, ICON_GIT, ICON_MODEL, ICON_VIM, ICON_WARN, RST


def resets_at_to_epoch(value: str | int) -> int:
    """Convert a rate-limit reset timestamp to a Unix epoch integer.

    Args:
        value (str | int): Either a Unix timestamp integer or an ISO 8601
            datetime string (e.g. "2024-01-01T12:00:00.000Z").

    Returns:
        int: Unix timestamp as an integer.
    """
    if isinstance(value, int):
        return value
    cleaned = value.split(".")[0].rstrip("Z")
    return int(datetime.fromisoformat(cleaned).replace(tzinfo=timezone.utc).timestamp())


def format_countdown(reset_epoch: int, now: int) -> str:
    """Format the time remaining until a rate-limit resets.

    Args:
        reset_epoch (int): Unix timestamp when the rate limit resets.
        now (int): Current Unix timestamp.

    Returns:
        str: Human-readable countdown (e.g. "1h30m", "2d3h", "soon").
    """
    diff = reset_epoch - now
    if diff <= 0:
        return "soon"
    if diff >= 86400:
        return f"{diff // 86400}d{diff % 86400 // 3600}h"
    if diff >= 3600:
        return f"{diff // 3600}h{diff % 3600 // 60}m"
    return f"{diff // 60}m"


def usage_segment_str(label: str, window: RateLimitWindow, now: int, theme: Theme, sep: str) -> str:
    """Build a formatted rate-limit usage segment.

    Args:
        label (str): Short window label (e.g. "5h", "7d").
        window (RateLimitWindow): Rate-limit usage data for the window.
        now (int): Current Unix timestamp.
        theme (Theme): The current terminal theme.
        sep (str): Separator string placed before the segment.

    Returns:
        str: Formatted segment with ANSI color codes, or "" if data is absent.
    """
    if window.used_pct is None or not window.resets_at:
        return ""
    try:
        pct = round(window.used_pct)
        reset_epoch = resets_at_to_epoch(window.resets_at)
        color = pct_color(pct, theme)
        reset_str = format_countdown(reset_epoch, now)
        return f"{sep}{theme.dim}{label}{RST} {color}{pct}%{RST} {theme.dim}↺ {reset_str}{RST}"
    except Exception:
        return ""


def git_info_str(cwd: str, theme: Theme, sep: str) -> str:
    """Build the git branch and working-tree status string.

    Args:
        cwd (str): Absolute path to the current working directory.
        theme (Theme): The current terminal theme.
        sep (str): Separator string placed before the segment.

    Returns:
        str: Formatted git info with ANSI colors, or "" if not in a git repo.
    """
    try:
        subprocess.run(["git", "-C", cwd, "rev-parse", "--git-dir"], capture_output=True, check=True)
    except subprocess.CalledProcessError:
        return ""

    branch = (
        subprocess.run(
            ["git", "-C", cwd, "branch", "--show-current"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        or "detached"
    )

    result = subprocess.run(["git", "-C", cwd, "status", "--porcelain"], capture_output=True, text=True)

    staged = unstaged = untracked = 0
    for line in result.stdout.splitlines():
        if len(line) < 2:
            continue
        x, y = line[0], line[1]
        if x == "?" and y == "?":
            untracked += 1
        else:
            if x not in (" ", "?"):
                staged += 1
            if y not in (" ", "?"):
                unstaged += 1

    status_parts = ""
    if staged:
        status_parts += f" {theme.green}+{staged}{RST}"
    if unstaged:
        status_parts += f" {theme.yellow}~{unstaged}{RST}"
    if untracked:
        status_parts += f" {theme.dim}?{untracked}{RST}"

    return f"{sep}{theme.magenta}{ICON_GIT} {branch}{RST}{status_parts}"


def vim_mode_str(vim_mode: str, theme: Theme, sep: str) -> str:
    """Build the vim mode indicator string.

    Args:
        vim_mode (str): Current vim mode (e.g. "NORMAL", "INSERT"). Empty
            string means vim mode is not active.
        theme (Theme): The current terminal theme.
        sep (str): Separator string placed before the segment.

    Returns:
        str: Formatted vim mode segment, or "" if vim mode is not active.
    """
    if not vim_mode:
        return ""
    color = theme.blue if vim_mode == "NORMAL" else theme.green
    return f"{sep}{color}{BOLD}{ICON_VIM} {vim_mode}{RST}"


def build_line1(data: StatusData, theme: Theme, now: int, sep: str) -> str:
    """Build the first status line (model, context bar, cost, usage).

    Args:
        data (StatusData): Parsed status payload.
        theme (Theme): The current terminal theme.
        now (int): Current Unix timestamp.
        sep (str): Separator string between segments.

    Returns:
        str: Fully formatted first line with ANSI escape codes.
    """
    pct_int = int(data.context_used_pct)
    ctx_color = pct_color(pct_int, theme)
    filled = min(BAR_SEGMENTS, (pct_int * BAR_SEGMENTS + 50) // 100)
    bar = "▰" * filled + "▱" * (BAR_SEGMENTS - filled)

    cost_str = f"${data.cost_usd:.2f}"
    usage_5h = usage_segment_str("5h", data.five_hour, now, theme, sep)
    usage_7d = usage_segment_str("7d", data.seven_day, now, theme, sep)
    tail = f"{sep}{theme.dim}{ICON_COST} {cost_str}{RST}{usage_5h}{usage_7d}"

    if pct_int >= 90:
        return (
            f"{theme.bg_red}{theme.white_bold} {ICON_WARN} CTX {pct_int}% {RST} "
            f"{theme.cyan}{BOLD}{ICON_MODEL} {data.model}{RST}"
            f"{sep}{ctx_color}{bar}{RST}"
            f"{tail}"
        )
    return (
        f"{theme.cyan}{BOLD}{ICON_MODEL} {data.model}{RST}"
        f"{sep}{theme.dim}{ICON_CTX}{RST} {ctx_color}{bar} {pct_int}%{RST}"
        f"{tail}"
    )


def build_line2(data: StatusData, theme: Theme, sep: str) -> str:
    """Build the second status line (directory, git, vim mode).

    Args:
        data (StatusData): Parsed status payload.
        theme (Theme): The current terminal theme.
        sep (str): Separator string between segments.

    Returns:
        str: Fully formatted second line with ANSI escape codes.
    """
    dir_name = Path(data.cwd).name or data.cwd
    git_part = git_info_str(data.cwd, theme, sep)
    vim_part = vim_mode_str(data.vim_mode, theme, sep)
    return f"{theme.blue}{ICON_DIR} {dir_name}{RST}{git_part}{vim_part}"
