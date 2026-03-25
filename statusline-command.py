#!/usr/bin/env python3
"""Claude Code Status Line — Two-line layout with Nerd Font icons (MD range)

Line 1: Model │ Context Bar (16 segs) │ Cost │ 5h usage │ 7d usage
Line 2: Directory │ Git Branch & Status │ Vim
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path

# --- Read and parse input ---
try:
    data = json.loads(sys.stdin.read())
except Exception:
    data = {}

now = int(time.time())

model = data.get("model", {}).get("display_name") or "?"
cwd = data.get("workspace", {}).get("current_dir") or "."
used_pct = float(data.get("context_window", {}).get("used_percentage") or 0)
cost = float(data.get("cost", {}).get("total_cost_usd") or 0)
vim_mode = data.get("vim", {}).get("mode") or ""


rate_limits = data.get("rate_limits", {})
_5h = rate_limits.get("five_hour", {})
_7d = rate_limits.get("seven_day", {})
rl_pct5h = _5h.get("used_percentage")
rl_pct7d = _7d.get("used_percentage")
rl_resets_at_5h = _5h.get("resets_at", "")
rl_resets_at_7d = _7d.get("resets_at", "")

dir_name = Path(cwd).name or cwd


# --- Theme detection ---
def detect_theme() -> str:
    theme = os.environ.get("STATUSLINE_THEME", "auto")
    if theme != "auto":
        return theme
    # COLORFGBG env var (e.g. "15;0" → bg=0 is dark)
    colorfgbg = os.environ.get("COLORFGBG", "")
    if colorfgbg:
        try:
            bg = int(colorfgbg.rsplit(";", 1)[-1])
            return "dark" if bg < 8 else "light"
        except ValueError:
            pass
    return "dark"


THEME = detect_theme()

# --- Colors ---
RST = "\033[0m"
BOLD = "\033[1m"

if THEME == "light":
    DIM = "\033[90m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    BLUE = "\033[34m"
    BG_RED = "\033[41m"
    WHITE_BOLD = "\033[1;30m"
else:
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    BLUE = "\033[34m"
    BG_RED = "\033[41m"
    WHITE_BOLD = "\033[1;37m"

# --- Nerd Font Icons (MD range, U+F0000+) ---
ICON_MODEL = "\U000f069a"  # nf-md-robot        󰚩
ICON_CTX = "\U000f036b"  # nf-md-memory       󰍛
ICON_DIR = "\U000f0770"  # nf-md-folder_outline 󰝰
ICON_GIT = "\U000f062c"  # nf-md-source_branch 󰘬
ICON_COST = "\U000f0109"  # nf-md-cash         󰄉
ICON_WARN = "\uf071"  # nf-fa-warning
ICON_VIM = "\U000f0577"  # nf-md-vim          󰕷

SEP = f"{DIM} │ {RST}"
BAR_SEGMENTS = 16


# --- Color helper for utilization percentage ---
def pct_color(pct: int) -> str:
    if pct < 50:
        return GREEN
    elif pct < 80:
        return YELLOW
    return RED


# --- Context bar ---
pct_int = int(used_pct)
ctx_color = pct_color(pct_int)
filled = min(BAR_SEGMENTS, (pct_int * BAR_SEGMENTS + 50) // 100)
empty = BAR_SEGMENTS - filled
bar = "▰" * filled + "▱" * empty

# --- Cost ---
cost_str = f"${cost:.2f}"


# --- Git info ---
def git_info_str() -> str:
    try:
        subprocess.run(["git", "-C", cwd, "rev-parse", "--git-dir"], capture_output=True, check=True)
    except subprocess.CalledProcessError:
        return ""

    branch = (
        subprocess.run(["git", "-C", cwd, "branch", "--show-current"], capture_output=True, text=True).stdout.strip()
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

    status = ""
    if staged:
        status += f" {GREEN}+{staged}{RST}"
    if unstaged:
        status += f" {YELLOW}~{unstaged}{RST}"
    if untracked:
        status += f" {DIM}?{untracked}{RST}"

    return f"{SEP}{MAGENTA}{ICON_GIT} {branch}{RST}{status}"


# --- Vim mode ---
def vim_str() -> str:
    if not vim_mode:
        return ""
    color = BLUE if vim_mode == "NORMAL" else GREEN
    return f"{SEP}{color}{BOLD}{ICON_VIM} {vim_mode}{RST}"


def _resets_at_to_epoch(s: str | int) -> int:
    from datetime import datetime, timezone

    if isinstance(s, int):
        return s
    s = s.split(".")[0].rstrip("Z")
    return int(datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp())


def format_countdown(reset_epoch: int) -> str:
    diff = reset_epoch - now
    if diff <= 0:
        return "soon"
    if diff >= 86400:
        return f"{diff // 86400}d{diff % 86400 // 3600}h"
    elif diff >= 3600:
        return f"{diff // 3600}h{diff % 3600 // 60}m"
    return f"{diff // 60}m"


def usage_segment(label: str, pct: int, reset_epoch: int) -> str:
    color = pct_color(pct)
    reset_str = format_countdown(reset_epoch)
    return f"{SEP}{DIM}{label}{RST} {color}{pct}%{RST} {DIM}↺ {reset_str}{RST}"


usage_5h = usage_7d = ""
try:
    if rl_pct5h is not None and rl_resets_at_5h:
        usage_5h = usage_segment("5h", int(rl_pct5h), _resets_at_to_epoch(rl_resets_at_5h))
    if rl_pct7d is not None and rl_resets_at_7d:
        usage_7d = usage_segment("7d", int(rl_pct7d), _resets_at_to_epoch(rl_resets_at_7d))
except Exception:
    pass

# --- Assemble output ---
git_part = git_info_str()
vim_part = vim_str()

line1_tail = f"{SEP}{DIM}{ICON_COST} {cost_str}{RST}{usage_5h}{usage_7d}"

if pct_int >= 90:
    line1 = (
        f"{BG_RED}{WHITE_BOLD} {ICON_WARN} CTX {pct_int}% {RST} "
        f"{CYAN}{BOLD}{ICON_MODEL} {model}{RST}"
        f"{SEP}{ctx_color}{bar}{RST}"
        f"{line1_tail}"
    )
else:
    line1 = (
        f"{CYAN}{BOLD}{ICON_MODEL} {model}{RST}{SEP}{DIM}{ICON_CTX}{RST} {ctx_color}{bar} {pct_int}%{RST}{line1_tail}"
    )

line2 = f"{BLUE}{ICON_DIR} {dir_name}{RST}{git_part}{vim_part}"

print(f"{line1}\n{line2}", end="")
