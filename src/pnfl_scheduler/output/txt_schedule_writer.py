from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..domain.schedule import Game, Schedule


def _week_games(schedule: Schedule) -> dict[int, list[Game]]:
    games_by_week: dict[int, list[Game]] = {}
    for game in sorted(schedule.games, key=lambda g: (g.week, g.away.city, g.home.city)):
        games_by_week.setdefault(game.week, []).append(game)
    return games_by_week


def _format_week_game(game: Game) -> str:
    return f"{game.away.city}#{game.home.city}"


@dataclass(frozen=True)
class TxtScheduleWriter:
    path: Path | str

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
