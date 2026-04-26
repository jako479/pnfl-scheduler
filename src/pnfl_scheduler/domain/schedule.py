"""Schedule output data structures."""

from __future__ import annotations

from dataclasses import dataclass

from pnfl_scheduler.domain.league import Division, Team

NUM_WEEKS = 16
GAMES_PER_WEEK = 9
HOME_GAMES_PER_TEAM = NUM_WEEKS // 2
WEEK_16_DIVISIONAL_GAMES = 8


def nonconference_games_for(division: Division) -> int:
    return 5 if division.expected_size == 4 else 4


@dataclass(frozen=True)
class Game:
    week: int  # 1-indexed
    home: Team
    away: Team


@dataclass(frozen=True)
class Schedule:
    games: tuple[Game, ...]

    def games_for(self, team: Team) -> tuple[Game, ...]:
        return tuple(g for g in self.games if team in (g.home, g.away))

    def home_games_for(self, team: Team) -> tuple[Game, ...]:
        return tuple(g for g in self.games if g.home == team)

    def away_games_for(self, team: Team) -> tuple[Game, ...]:
        return tuple(g for g in self.games if g.away == team)

    def games_between(self, a: Team, b: Team) -> tuple[Game, ...]:
        return tuple(g for g in self.games if {g.home, g.away} == {a, b})
