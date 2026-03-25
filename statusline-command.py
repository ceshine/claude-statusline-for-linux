#!/usr/bin/env python3
"""Claude Code Status Line — Two-line layout with Nerd Font icons (MD range)

Line 1: Model │ Context Bar (16 segs) │ Cost │ 5h usage │ 7d usage
Line 2: Directory │ Git Branch & Status │ Venv │ Vim
"""

import os
import sys
import json
import time
import subprocess
import threading
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
ICON_VENV = "\U000f0320"  # nf-md-language_python 󰌠

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


# --- Python venv detection ---
def venv_str() -> str:
    venv_name = py_ver = ""
    virtual_env = os.environ.get("VIRTUAL_ENV", "")
    if virtual_env:
        venv_name = Path(virtual_env).name
    else:
        for candidate in [".venv", "venv", ".env"]:
            python_bin = Path(cwd) / candidate / "bin" / "python"
            if python_bin.is_file():
                venv_name = candidate
                try:
                    ver_out = subprocess.run(
                        [str(python_bin), "--version"], capture_output=True, text=True
                    ).stdout.strip()
                    # e.g. "Python 3.11.2" → "3.11"
                    parts = ver_out.split()
                    if len(parts) >= 2:
                        py_ver = ".".join(parts[1].split(".")[:2])
                except Exception:
                    pass
                break

    if not venv_name:
        return ""
    ver_suffix = f" ({py_ver})" if py_ver else ""
    return f"{SEP}{YELLOW}{ICON_VENV} {venv_name}{ver_suffix}{RST}"


# --- Vim mode ---
def vim_str() -> str:
    if not vim_mode:
        return ""
    color = BLUE if vim_mode == "NORMAL" else GREEN
    return f"{SEP}{color}{BOLD}{ICON_VIM} {vim_mode}{RST}"


# --- Usage cache (background refresh via thread) ---
CACHE_DIR = Path.home() / ".claude" / "statusline-cache"
USAGE_CACHE = CACHE_DIR / "usage.dat"
LOCK_FILE = CACHE_DIR / "usage-update.lock"
CACHE_TTL = 60


def refresh_usage_cache():
    try:
        LOCK_FILE.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        try:
            age = now - int(LOCK_FILE.stat().st_mtime)
            if age <= 60:
                return
            import shutil

            shutil.rmtree(LOCK_FILE, ignore_errors=True)
            LOCK_FILE.mkdir(parents=True, exist_ok=False)
        except Exception:
            return

    def _fetch():
        try:
            import urllib.request

            token = ""
            creds_path = Path.home() / ".claude" / ".credentials.json"
            if creds_path.is_file():
                creds = json.loads(creds_path.read_text())
                token = creds.get("claudeAiOauth", {}).get("accessToken", "")

            if not token:
                return

            req = urllib.request.Request(
                "https://api.anthropic.com/api/oauth/usage",
                headers={
                    "Authorization": f"Bearer {token}",
                    "anthropic-beta": "oauth-2025-04-20",
                },
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                body = json.loads(resp.read())

            if "five_hour" not in body:
                return

            def to_epoch(s: str) -> int:
                from datetime import datetime, timezone

                # Strip sub-second precision and trailing Z
                s = s.split(".")[0].rstrip("Z")
                return int(datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp())

            pct5h = int(body["five_hour"]["utilization"])
            epoch5h = to_epoch(body["five_hour"]["resets_at"])
            pct7d = int(body["seven_day"]["utilization"])
            epoch7d = to_epoch(body["seven_day"]["resets_at"])

            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            tmp = USAGE_CACHE.with_suffix(".tmp")
            tmp.write_text(f"{pct5h} {epoch5h} {pct7d} {epoch7d}\n")
            tmp.replace(USAGE_CACHE)
        except Exception:
            pass
        finally:
            import shutil

            shutil.rmtree(LOCK_FILE, ignore_errors=True)

    t = threading.Thread(target=_fetch, daemon=True)
    t.start()
    return t


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


# Trigger background refresh if cache is missing or stale
refresh_thread = None
if not USAGE_CACHE.is_file():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    refresh_thread = refresh_usage_cache()
else:
    cache_age = now - int(USAGE_CACHE.stat().st_mtime)
    if cache_age > CACHE_TTL:
        refresh_thread = refresh_usage_cache()

usage_5h = usage_7d = ""
if USAGE_CACHE.is_file():
    try:
        parts = USAGE_CACHE.read_text().split()
        pct5h, epoch5h, pct7d, epoch7d = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
        if pct5h != -1:
            usage_5h = usage_segment("5h", pct5h, epoch5h)
        if pct7d != -1:
            usage_7d = usage_segment("7d", pct7d, epoch7d)
    except Exception:
        pass

# --- Assemble output ---
git_part = git_info_str()
venv_part = venv_str()
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

line2 = f"{BLUE}{ICON_DIR} {dir_name}{RST}{git_part}{venv_part}{vim_part}"

# Wait for background thread to finish writing the cache before exit
# (only if it was just started and the script is about to exit)
if refresh_thread is not None:
    refresh_thread.join(timeout=0)  # don't block — fire and forget

print(f"{line1}\n{line2}", end="")
