"""Plain-text schedule writer: one line per game, grouped by week."""

from __future__ import annotations

from dataclasses import dataclass
from os import PathLike
from pathlib import Path

from pnfl_scheduler.domain.schedule import Game, Schedule

StrPath = str | PathLike[str]


def _week_games(schedule: Schedule) -> dict[int, list[Game]]:
    games_by_week: dict[int, list[Game]] = {}
    for game in sorted(schedule.games, key=lambda g: (g.week, g.away.metro, g.home.metro)):
        games_by_week.setdefault(game.week, []).append(game)
    return games_by_week


def _format_week_game(game: Game) -> str:
    return f"{game.away.metro}#{game.home.metro}"


@dataclass(frozen=True)
class TxtScheduleWriter:
    """Writes a compact text schedule (`Week N` headers followed by `away#home` lines)."""

    path: StrPath

    def write(self, schedule: Schedule) -> None:
        Path(self.path).write_text(self.render(schedule), encoding="utf-8")

    def render(self, schedule: Schedule) -> str:
        games_by_week = _week_games(schedule)
        weeks = sorted(games_by_week)

        lines: list[str] = []
        for week in weeks:
            lines.append(f"Week {week}")
            for game in games_by_week[week]:
                lines.append(_format_week_game(game))

        return "\n".join(lines) + "\n"
