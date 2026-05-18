from __future__ import annotations

from pathlib import Path

import pytest

from pnfl_scheduler.domain.league import Division, Team
from pnfl_scheduler.domain.schedule import Game, Schedule
from pnfl_scheduler.writers.html_writer import HtmlScheduleWriter
from pnfl_scheduler.writers.txt_writer import TxtScheduleWriter
from pnfl_scheduler.writers.writer import available_writer_formats, get_writer

# A tiny hand-built schedule — no solver needed to exercise the writers.
ALPHA = Team("Alpha", Division.AFC_EAST)
BETA = Team("Beta", Division.AFC_EAST)
SCHEDULE = Schedule(
    (
        Game(week=1, home=ALPHA, away=BETA),
        Game(week=2, home=BETA, away=ALPHA),
    )
)


# ---------------------------------------------------------------------------
# writer registry
# ---------------------------------------------------------------------------


def test_available_writer_formats() -> None:
    assert available_writer_formats() == ("htm", "html", "txt")


def test_get_writer_returns_txt_writer(tmp_path: Path) -> None:
    assert isinstance(get_writer("txt", tmp_path / "s.txt"), TxtScheduleWriter)


def test_get_writer_returns_html_writer(tmp_path: Path) -> None:
    assert isinstance(get_writer("html", tmp_path / "s.html"), HtmlScheduleWriter)
    assert isinstance(get_writer("htm", tmp_path / "s.htm"), HtmlScheduleWriter)


def test_get_writer_is_case_insensitive(tmp_path: Path) -> None:
    assert isinstance(get_writer("TXT", tmp_path / "s.txt"), TxtScheduleWriter)


def test_get_writer_errors_on_unsupported_format(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        get_writer("xml", tmp_path / "s.xml")


# ---------------------------------------------------------------------------
# TxtScheduleWriter
# ---------------------------------------------------------------------------


def test_txt_writer_render_groups_games_by_week() -> None:
    assert TxtScheduleWriter("unused").render(SCHEDULE) == "Week 1\nBeta#Alpha\nWeek 2\nAlpha#Beta\n"


def test_txt_writer_write_creates_file(tmp_path: Path) -> None:
    path = tmp_path / "schedule.txt"
    writer = TxtScheduleWriter(path)
    writer.write(SCHEDULE)
    assert path.read_text(encoding="utf-8") == writer.render(SCHEDULE)


# ---------------------------------------------------------------------------
# HtmlScheduleWriter
# ---------------------------------------------------------------------------


def test_html_writer_render_produces_html_document() -> None:
    out = HtmlScheduleWriter("unused").render(SCHEDULE)
    assert out.startswith("<html>")
    assert "</html>" in out
    assert "Alpha" in out and "Beta" in out
    assert "Beta at Alpha" in out


def test_html_writer_write_creates_file(tmp_path: Path) -> None:
    path = tmp_path / "schedule.html"
    HtmlScheduleWriter(path).write(SCHEDULE)
    assert path.read_text(encoding="utf-8").startswith("<html>")


def test_html_writer_includes_season_label_when_provided() -> None:
    assert "2048" in HtmlScheduleWriter("unused", season_label="2048").render(SCHEDULE)
