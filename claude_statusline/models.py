"""Data models for the Claude Code status line."""

from dataclasses import dataclass


@dataclass
class Theme:
    """ANSI color codes for a terminal theme."""

    dim: str
    cyan: str
    green: str
    yellow: str
    red: str
    magenta: str
    blue: str
    bg_red: str
    white_bold: str


@dataclass
class RateLimitWindow:
    """Usage data for a single rate-limit window."""

    used_pct: float | None
    resets_at: str | int | None


@dataclass
class StatusData:
    """Parsed Claude Code status payload from stdin."""

    model: str
    cwd: str
    context_used_pct: float
    cost_usd: float
    vim_mode: str
    five_hour: RateLimitWindow
    seven_day: RateLimitWindow
