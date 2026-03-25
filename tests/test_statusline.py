"""Unit tests for claude_statusline."""

import re
import subprocess
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from claude_statusline.formatters import (
    build_line1,
    build_line2,
    format_countdown,
    format_token_count,
    git_info_str,
    resets_at_to_epoch,
    token_counts_str,
    usage_segment_str,
    vim_mode_str,
)
from claude_statusline.models import CurrentUsage, RateLimitWindow, StatusData
from claude_statusline.parser import parse_status_data
from claude_statusline.theme import build_theme, detect_theme, pct_color

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

DARK = build_theme("dark")
SEP = " | "


def strip_ansi(s: str) -> str:
    """Remove ANSI escape sequences from a string.

    Args:
        s (str): Input string possibly containing ANSI codes.

    Returns:
        str: Plain text with all ANSI escape sequences removed.
    """
    return _ANSI_RE.sub("", s)


# ---------------------------------------------------------------------------
# parse_status_data
# ---------------------------------------------------------------------------


class TestParseStatusData:
    """Tests for parse_status_data()."""

    def test_full_payload(self):
        """All fields present are extracted correctly."""
        raw = {
            "model": {"display_name": "claude-opus-4"},
            "workspace": {"current_dir": "/home/user/project"},
            "context_window": {
                "used_percentage": 42.5,
                "current_usage": {
                    "input_tokens": 1200,
                    "output_tokens": 300,
                    "cache_creation_input_tokens": 40,
                    "cache_read_input_tokens": 500,
                },
            },
            "cost": {"total_cost_usd": 1.23},
            "vim": {"mode": "INSERT"},
            "rate_limits": {
                "five_hour": {"used_percentage": 30, "resets_at": "2024-01-01T12:00:00Z"},
                "seven_day": {"used_percentage": 10, "resets_at": 1704110400},
            },
        }
        data = parse_status_data(raw)

        assert data.model == "claude-opus-4"
        assert data.cwd == "/home/user/project"
        assert data.context_used_pct == 42.5
        assert data.current_usage.input_tokens == 1200
        assert data.current_usage.output_tokens == 300
        assert data.current_usage.cache_creation_input_tokens == 40
        assert data.current_usage.cache_read_input_tokens == 500
        assert data.cost_usd == 1.23
        assert data.vim_mode == "INSERT"
        assert data.five_hour.used_pct == 30
        assert data.five_hour.resets_at == "2024-01-01T12:00:00Z"
        assert data.seven_day.used_pct == 10
        assert data.seven_day.resets_at == 1704110400

    def test_empty_payload_defaults(self):
        """Missing fields fall back to safe defaults."""
        data = parse_status_data({})

        assert data.model == "?"
        assert data.cwd == "."
        assert data.context_used_pct == 0.0
        assert data.current_usage == CurrentUsage(
            input_tokens=0,
            output_tokens=0,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=0,
        )
        assert data.cost_usd == 0.0
        assert data.vim_mode == ""
        assert data.five_hour.used_pct is None
        assert data.seven_day.used_pct is None

    def test_falsy_model_falls_back_to_question_mark(self):
        """An empty display_name string is treated as missing."""
        data = parse_status_data({"model": {"display_name": ""}})
        assert data.model == "?"

    def test_falsy_cwd_falls_back_to_dot(self):
        """An empty current_dir string is treated as missing."""
        data = parse_status_data({"workspace": {"current_dir": ""}})
        assert data.cwd == "."

    def test_null_current_usage_defaults_to_zero_counts(self):
        """A null current_usage object falls back to zero token counts."""
        data = parse_status_data({"context_window": {"current_usage": None}})
        assert data.current_usage == CurrentUsage(
            input_tokens=0,
            output_tokens=0,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=0,
        )


# ---------------------------------------------------------------------------
# pct_color
# ---------------------------------------------------------------------------


class TestPctColor:
    """Tests for pct_color()."""

    def test_low_returns_green(self):
        assert pct_color(0, DARK) == DARK.green
        assert pct_color(49, DARK) == DARK.green

    def test_mid_returns_yellow(self):
        assert pct_color(50, DARK) == DARK.yellow
        assert pct_color(79, DARK) == DARK.yellow

    def test_high_returns_red(self):
        assert pct_color(80, DARK) == DARK.red
        assert pct_color(100, DARK) == DARK.red


# ---------------------------------------------------------------------------
# detect_theme
# ---------------------------------------------------------------------------


class TestDetectTheme:
    """Tests for detect_theme()."""

    def test_explicit_light(self, monkeypatch):
        monkeypatch.setenv("STATUSLINE_THEME", "light")
        assert detect_theme() == "light"

    def test_explicit_dark(self, monkeypatch):
        monkeypatch.setenv("STATUSLINE_THEME", "dark")
        assert detect_theme() == "dark"

    def test_colorfgbg_dark_background(self, monkeypatch):
        monkeypatch.delenv("STATUSLINE_THEME", raising=False)
        monkeypatch.setenv("COLORFGBG", "15;0")  # bg=0 → dark
        assert detect_theme() == "dark"

    def test_colorfgbg_light_background(self, monkeypatch):
        monkeypatch.delenv("STATUSLINE_THEME", raising=False)
        monkeypatch.setenv("COLORFGBG", "0;15")  # bg=15 → light
        assert detect_theme() == "light"

    def test_colorfgbg_invalid_falls_back_to_dark(self, monkeypatch):
        monkeypatch.delenv("STATUSLINE_THEME", raising=False)
        monkeypatch.setenv("COLORFGBG", "not;valid")
        assert detect_theme() == "dark"

    def test_no_env_defaults_to_dark(self, monkeypatch):
        monkeypatch.delenv("STATUSLINE_THEME", raising=False)
        monkeypatch.delenv("COLORFGBG", raising=False)
        assert detect_theme() == "dark"


# ---------------------------------------------------------------------------
# resets_at_to_epoch
# ---------------------------------------------------------------------------


class TestResetsAtToEpoch:
    """Tests for resets_at_to_epoch()."""

    def test_integer_passthrough(self):
        assert resets_at_to_epoch(1700000000) == 1700000000

    def test_iso_string_with_milliseconds(self):
        expected = int(datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc).timestamp())
        assert resets_at_to_epoch("2024-01-01T12:00:00.000Z") == expected

    def test_iso_string_plain(self):
        expected = int(datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc).timestamp())
        assert resets_at_to_epoch("2024-01-01T12:00:00Z") == expected

    def test_iso_string_without_z_suffix(self):
        expected = int(datetime(2025, 6, 15, 8, 30, 0, tzinfo=timezone.utc).timestamp())
        assert resets_at_to_epoch("2025-06-15T08:30:00") == expected


# ---------------------------------------------------------------------------
# format_countdown
# ---------------------------------------------------------------------------


class TestFormatCountdown:
    """Tests for format_countdown()."""

    def test_past_epoch_returns_soon(self):
        assert format_countdown(1000, now=2000) == "soon"

    def test_equal_epoch_returns_soon(self):
        assert format_countdown(1000, now=1000) == "soon"

    def test_minutes_only(self):
        assert format_countdown(1000 + 45 * 60, now=1000) == "45m"

    def test_hours_and_minutes(self):
        # 1h 30m = 5400s
        assert format_countdown(1000 + 5400, now=1000) == "1h30m"

    def test_exact_hours(self):
        assert format_countdown(1000 + 3600, now=1000) == "1h0m"

    def test_days_and_hours(self):
        # 2d 3h = 2*86400 + 3*3600 = 183600s
        assert format_countdown(1000 + 183600, now=1000) == "2d3h"

    def test_exact_days(self):
        assert format_countdown(1000 + 86400, now=1000) == "1d0h"


# ---------------------------------------------------------------------------
# vim_mode_str
# ---------------------------------------------------------------------------


class TestVimModeStr:
    """Tests for vim_mode_str()."""

    def test_empty_mode_returns_empty(self):
        assert vim_mode_str("", DARK, SEP) == ""

    def test_normal_mode_shows_label(self):
        result = strip_ansi(vim_mode_str("NORMAL", DARK, SEP))
        assert "NORMAL" in result

    def test_insert_mode_shows_label(self):
        result = strip_ansi(vim_mode_str("INSERT", DARK, SEP))
        assert "INSERT" in result

    def test_normal_uses_blue_color(self):
        result = vim_mode_str("NORMAL", DARK, SEP)
        assert DARK.blue in result

    def test_non_normal_uses_green_color(self):
        result = vim_mode_str("INSERT", DARK, SEP)
        assert DARK.green in result


# ---------------------------------------------------------------------------
# usage_segment_str
# ---------------------------------------------------------------------------


class TestUsageSegmentStr:
    """Tests for usage_segment_str()."""

    def test_none_pct_returns_empty(self):
        window = RateLimitWindow(used_pct=None, resets_at="2024-01-01T12:00:00Z")
        assert usage_segment_str("5h", window, now=0, theme=DARK, sep=SEP) == ""

    def test_empty_resets_at_returns_empty(self):
        window = RateLimitWindow(used_pct=40, resets_at="")
        assert usage_segment_str("5h", window, now=0, theme=DARK, sep=SEP) == ""

    def test_none_resets_at_returns_empty(self):
        window = RateLimitWindow(used_pct=40, resets_at=None)
        assert usage_segment_str("5h", window, now=0, theme=DARK, sep=SEP) == ""

    def test_valid_segment_contains_label_and_pct(self):
        reset_epoch = 1000 + 3600  # 1 hour from now
        window = RateLimitWindow(used_pct=35, resets_at=reset_epoch)
        result = strip_ansi(usage_segment_str("5h", window, now=1000, theme=DARK, sep=SEP))
        assert "5h" in result
        assert "35%" in result
        assert "1h0m" in result


# ---------------------------------------------------------------------------
# format_token_count / token_counts_str
# ---------------------------------------------------------------------------


class TestTokenCounts:
    """Tests for token count formatting."""

    def test_format_token_count_for_small_values(self):
        assert format_token_count(999) == "999"

    def test_format_token_count_for_thousands(self):
        assert format_token_count(1200) == "1.2k"

    def test_format_token_count_for_millions(self):
        assert format_token_count(2_000_000) == "2.0M"

    def test_token_counts_str_contains_all_fields(self):
        current_usage = CurrentUsage(
            input_tokens=1200,
            output_tokens=300,
            cache_creation_input_tokens=40,
            cache_read_input_tokens=500,
        )
        result = strip_ansi(token_counts_str(current_usage, DARK, SEP))
        assert "tok" in result
        assert "i 1.2k" in result
        assert "o 300" in result
        assert "cw 40" in result
        assert "cr 500" in result


# ---------------------------------------------------------------------------
# git_info_str
# ---------------------------------------------------------------------------


class TestGitInfoStr:
    """Tests for git_info_str() using mocked subprocess."""

    def _make_run(self, branch: str = "main", porcelain: str = "") -> object:
        """Build a fake subprocess.run that simulates a git repo.

        Args:
            branch (str): Branch name returned by git branch --show-current.
            porcelain (str): Output of git status --porcelain.

        Returns:
            object: A callable usable as side_effect for mock.patch.
        """

        def fake_run(args, **kwargs):
            mock = MagicMock()
            if "rev-parse" in args:
                return mock  # no exception → is a repo
            if "branch" in args:
                mock.stdout = branch + "\n"
                return mock
            if "status" in args:
                mock.stdout = porcelain
                return mock
            return mock

        return fake_run

    def test_not_a_git_repo_returns_empty(self):
        with patch("claude_statusline.formatters.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(128, "git")
            assert git_info_str("/not/a/repo", DARK, SEP) == ""

    def test_clean_repo_shows_branch_only(self):
        with patch("claude_statusline.formatters.subprocess.run", side_effect=self._make_run("main", "")):
            result = strip_ansi(git_info_str("/repo", DARK, SEP))
        assert "main" in result
        assert "+" not in result
        assert "~" not in result
        assert "?" not in result

    def test_dirty_repo_shows_all_counts(self):
        # M  staged, _M unstaged, ?? untracked
        porcelain = "M  staged.txt\n M unstaged.txt\n?? new.txt\n"
        with patch("claude_statusline.formatters.subprocess.run", side_effect=self._make_run("dev", porcelain)):
            result = strip_ansi(git_info_str("/repo", DARK, SEP))
        assert "dev" in result
        assert "+1" in result
        assert "~1" in result
        assert "?1" in result

    def test_detached_head_shows_detached(self):
        with patch("claude_statusline.formatters.subprocess.run", side_effect=self._make_run("", "")):
            result = strip_ansi(git_info_str("/repo", DARK, SEP))
        assert "detached" in result

    def test_multiple_staged_and_untracked(self):
        porcelain = "M  a.txt\nA  b.txt\n?? x.txt\n?? y.txt\n?? z.txt\n"
        with patch("claude_statusline.formatters.subprocess.run", side_effect=self._make_run("main", porcelain)):
            result = strip_ansi(git_info_str("/repo", DARK, SEP))
        assert "+2" in result
        assert "?3" in result


# ---------------------------------------------------------------------------
# build_line1
# ---------------------------------------------------------------------------


class TestBuildLine1:
    """Tests for build_line1()."""

    def _make_data(self, context_pct: float = 50.0, cost: float = 0.5, model: str = "claude-opus-4") -> StatusData:
        return StatusData(
            model=model,
            cwd="/tmp",
            context_used_pct=context_pct,
            current_usage=CurrentUsage(
                input_tokens=0,
                output_tokens=0,
                cache_creation_input_tokens=0,
                cache_read_input_tokens=0,
            ),
            cost_usd=cost,
            vim_mode="",
            five_hour=RateLimitWindow(used_pct=None, resets_at=None),
            seven_day=RateLimitWindow(used_pct=None, resets_at=None),
        )

    def test_normal_context_contains_model_and_cost(self):
        data = self._make_data(context_pct=50.0, cost=1.23)
        result = strip_ansi(build_line1(data, DARK, now=0, sep=SEP))
        assert "claude-opus-4" in result
        assert "$1.23" in result
        assert "50%" in result

    def test_high_context_shows_warning(self):
        data = self._make_data(context_pct=92.0)
        result = strip_ansi(build_line1(data, DARK, now=0, sep=SEP))
        assert "CTX" in result
        assert "92%" in result
        assert "claude-opus-4" in result

    def test_normal_context_no_warning_prefix(self):
        data = self._make_data(context_pct=89.0)
        result = strip_ansi(build_line1(data, DARK, now=0, sep=SEP))
        assert "CTX" not in result

    def test_token_counts_appear_when_present(self):
        data = StatusData(
            model="m",
            cwd="/tmp",
            context_used_pct=10.0,
            current_usage=CurrentUsage(
                input_tokens=1200,
                output_tokens=300,
                cache_creation_input_tokens=40,
                cache_read_input_tokens=500,
            ),
            cost_usd=0.0,
            vim_mode="",
            five_hour=RateLimitWindow(used_pct=20, resets_at=9999999999),
            seven_day=RateLimitWindow(used_pct=5, resets_at=9999999999),
        )
        result = strip_ansi(build_line1(data, DARK, now=0, sep=SEP))
        assert "tok" in result
        assert "i 1.2k" in result
        assert "o 300" in result
        assert "cw 40" in result
        assert "cr 500" in result


# ---------------------------------------------------------------------------
# build_line2
# ---------------------------------------------------------------------------


class TestBuildLine2:
    """Tests for build_line2()."""

    def test_shows_directory_name(self):
        data = StatusData(
            model="m",
            cwd="/home/user/myproject",
            context_used_pct=0.0,
            current_usage=CurrentUsage(
                input_tokens=0,
                output_tokens=0,
                cache_creation_input_tokens=0,
                cache_read_input_tokens=0,
            ),
            cost_usd=0.0,
            vim_mode="",
            five_hour=RateLimitWindow(used_pct=None, resets_at=None),
            seven_day=RateLimitWindow(used_pct=None, resets_at=None),
        )
        with patch("claude_statusline.formatters.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(128, "git")
            result = strip_ansi(build_line2(data, DARK, now=0, sep=SEP))
        assert "myproject" in result

    def test_includes_vim_mode_when_active(self):
        data = StatusData(
            model="m",
            cwd="/tmp",
            context_used_pct=0.0,
            current_usage=CurrentUsage(
                input_tokens=0,
                output_tokens=0,
                cache_creation_input_tokens=0,
                cache_read_input_tokens=0,
            ),
            cost_usd=0.0,
            vim_mode="NORMAL",
            five_hour=RateLimitWindow(used_pct=None, resets_at=None),
            seven_day=RateLimitWindow(used_pct=None, resets_at=None),
        )
        with patch("claude_statusline.formatters.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(128, "git")
            result = strip_ansi(build_line2(data, DARK, now=0, sep=SEP))
        assert "NORMAL" in result

    def test_includes_usage_windows(self):
        data = StatusData(
            model="m",
            cwd="/tmp",
            context_used_pct=0.0,
            current_usage=CurrentUsage(
                input_tokens=1200,
                output_tokens=300,
                cache_creation_input_tokens=40,
                cache_read_input_tokens=500,
            ),
            cost_usd=0.0,
            vim_mode="",
            five_hour=RateLimitWindow(used_pct=20, resets_at=9999999999),
            seven_day=RateLimitWindow(used_pct=5, resets_at=9999999999),
        )
        with patch("claude_statusline.formatters.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(128, "git")
            result = strip_ansi(build_line2(data, DARK, now=0, sep=SEP))
        assert "5h" in result
        assert "7d" in result
        assert "tok" not in result
