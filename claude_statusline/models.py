"""Data models for the Claude Code status line."""

from dataclasses import dataclass


@dataclass
class CurrentUsage:
    """Token counts for the current Claude Code API call."""

    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int

    @property
    def total_tokens(self) -> int:
        """Total tokens used in the current API call."""
        return self.input_tokens + self.output_tokens + self.cache_creation_input_tokens + self.cache_read_input_tokens

    @property
    def context_tokens(self) -> int:
        """Total context token used in the current API call"""
        return self.input_tokens + self.cache_creation_input_tokens + self.cache_read_input_tokens


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
    current_usage: CurrentUsage
    cost_usd: float
    vim_mode: str
    five_hour: RateLimitWindow
    seven_day: RateLimitWindow
