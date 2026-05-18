from __future__ import annotations

from pathlib import Path

import pytest

from pnfl_scheduler import config
from pnfl_scheduler.cli import build_parser, main
from pnfl_scheduler.schedulers.types import DEFAULT_SCHEDULER

# ---------------------------------------------------------------------------
# argument parsing
# ---------------------------------------------------------------------------


def test_parser_defaults() -> None:
    args = build_parser().parse_args(["--output", "schedule.txt", "--season", "2026"])
    assert args.output == Path("schedule.txt")
    assert args.season == 2026
    assert args.config is None
    assert args.format is None
    assert args.history is None
    assert args.report is None
    assert args.time_limit is None
    assert args.seed is None
    assert args.scheduler == DEFAULT_SCHEDULER


def test_parser_parses_optional_flags() -> None:
    args = build_parser().parse_args(
        ["--output", "out.txt", "--season", "2026", "--config", "custom.ini", "--time-limit", "30", "--seed", "7"]
    )
    assert args.config == Path("custom.ini")
    assert args.time_limit == 30.0
    assert args.seed == 7


def test_parser_requires_output() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--season", "2026"])


def test_parser_requires_season() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--output", "schedule.txt"])


# ---------------------------------------------------------------------------
# main — output format inference
# ---------------------------------------------------------------------------


def test_main_errors_on_unknown_output_format() -> None:
    with pytest.raises(SystemExit):
        main(["--output", "schedule.xyz", "--season", "2026"])


# ---------------------------------------------------------------------------
# main — config errors exit 1
# ---------------------------------------------------------------------------


def test_main_errors_when_explicit_config_missing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(
        ["--output", str(tmp_path / "schedule.txt"), "--season", "2026", "--config", str(tmp_path / "missing.ini")]
    )
    assert exit_code == 1
    assert "error" in capsys.readouterr().err.lower()


def test_main_errors_when_no_config_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(config, "CONFIG_CANDIDATES", [tmp_path / "generate-schedule.ini"])
    exit_code = main(["--output", str(tmp_path / "schedule.txt"), "--season", "2026"])
    assert exit_code == 1
    assert "error" in capsys.readouterr().err.lower()
