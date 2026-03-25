"""Terminal theme detection and ANSI color helpers."""

import os

from .models import Theme


def detect_theme() -> str:
    """Detect the terminal color theme from environment variables.

    Checks STATUSLINE_THEME first, then falls back to COLORFGBG.

    Returns:
        str: One of "light", "dark", or "auto" (defaults to "dark").
    """
    theme = os.environ.get("STATUSLINE_THEME", "auto")
    if theme != "auto":
        return theme
    colorfgbg = os.environ.get("COLORFGBG", "")
    if colorfgbg:
        try:
            bg = int(colorfgbg.rsplit(";", 1)[-1])
            return "dark" if bg < 8 else "light"
        except ValueError:
            pass
    return "dark"


def build_theme(theme_name: str) -> Theme:
    """Build a Theme instance with ANSI escape sequences for the given name.

    Args:
        theme_name (str): Either "light" or "dark".

    Returns:
        Theme: Populated theme dataclass.
    """
    if theme_name == "light":
        return Theme(
            dim="\033[90m",
            cyan="\033[36m",
            green="\033[32m",
            yellow="\033[33m",
            red="\033[31m",
            magenta="\033[35m",
            blue="\033[34m",
            bg_red="\033[41m",
            white_bold="\033[1;30m",
        )
    return Theme(
        dim="\033[2m",
        cyan="\033[36m",
        green="\033[32m",
        yellow="\033[33m",
        red="\033[31m",
        magenta="\033[35m",
        blue="\033[34m",
        bg_red="\033[41m",
        white_bold="\033[1;37m",
    )


def pct_color(pct: int, theme: Theme) -> str:
    """Return the ANSI color code appropriate for a utilization percentage.

    Args:
        pct (int): Utilization percentage in the range 0–100.
        theme (Theme): The current terminal theme.

    Returns:
        str: ANSI escape sequence for green (<50%), yellow (<80%), or red (≥80%).
    """
    if pct < 50:
        return theme.green
    if pct < 80:
        return theme.yellow
    return theme.red
