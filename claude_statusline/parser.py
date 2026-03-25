"""Parsing the Claude Code JSON stdin payload into typed data models."""

from typing import Any

from .models import CurrentUsage, RateLimitWindow, StatusData


def parse_status_data(raw: dict[str, Any]) -> StatusData:
    """Parse the Claude Code JSON stdin payload into a StatusData instance.

    Args:
        raw (dict[str, Any]): The raw JSON dictionary read from stdin.

    Returns:
        StatusData: A dataclass instance with all extracted values.
    """
    rate_limits: dict[str, dict[str, Any]] = raw.get("rate_limits", {})
    context_window: dict[str, Any] = raw.get("context_window", {})
    current_usage_raw: dict[str, Any] = context_window.get("current_usage", {}) or {}
    five_hour_raw = rate_limits.get("five_hour", {})
    seven_day_raw = rate_limits.get("seven_day", {})
    return StatusData(
        model=raw.get("model", {}).get("display_name") or "?",
        cwd=raw.get("workspace", {}).get("current_dir") or ".",
        context_used_pct=float(context_window.get("used_percentage") or 0),
        current_usage=CurrentUsage(
            input_tokens=int(current_usage_raw.get("input_tokens") or 0),
            output_tokens=int(current_usage_raw.get("output_tokens") or 0),
            cache_creation_input_tokens=int(current_usage_raw.get("cache_creation_input_tokens") or 0),
            cache_read_input_tokens=int(current_usage_raw.get("cache_read_input_tokens") or 0),
        ),
        cost_usd=float(raw.get("cost", {}).get("total_cost_usd") or 0),
        vim_mode=raw.get("vim", {}).get("mode") or "",
        five_hour=RateLimitWindow(
            used_pct=five_hour_raw.get("used_percentage"),
            resets_at=five_hour_raw.get("resets_at", ""),
        ),
        seven_day=RateLimitWindow(
            used_pct=seven_day_raw.get("used_percentage"),
            resets_at=seven_day_raw.get("resets_at", ""),
        ),
    )
