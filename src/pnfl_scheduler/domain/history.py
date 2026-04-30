"""Non-conference matchup history for rotation-fair scheduling."""

from __future__ import annotations

import json
from os import PathLike
from pathlib import Path
from typing import TypedDict

from pnfl_scheduler.domain.league import Conference, Team

StrPath = str | PathLike[str]


def _make_matchup_key(team_a: Team, team_b: Team) -> str:
    """Return 'AFC metro|NFC metro' key for a non-conference pair."""
    afc = team_a if team_a.conference == Conference.AFC else team_b
    nfc = team_b if team_a.conference == Conference.AFC else team_a
    return f"{afc.metro}|{nfc.metro}"


class NonConfHistory:
    """Tracks the last season each non-conference pair played."""

    def __init__(self, matchups: dict[str, int] | None = None) -> None:
        self._matchups: dict[str, int] = {} if matchups is None else dict(matchups)

    @classmethod
    def load(cls, path: StrPath) -> NonConfHistory:
        """Load from JSON file. Returns empty history if file doesn't exist."""
        path = Path(path)
        if not path.exists():
            return cls()
        data: _HistoryJson = json.loads(path.read_text(encoding="utf-8"))
        return cls(matchups=data["matchups"])

    def last_played(self, team_a: Team, team_b: Team) -> int:
        """Return the last season these two teams played."""
        return self._matchups[_make_matchup_key(team_a, team_b)]

    @staticmethod
    def _played_opponent_cost(last_played: int, season: int) -> int:
        """Return gap-based cost for a played matchup.

        Examples:
        - last season -> 0
        - 2 seasons ago -> -1
        - 3 seasons ago -> -2
        """
        return last_played - season + 1

    def opponent_cost(self, team: Team, opp: Team, season: int) -> int:
        """Return cost for this matchup. Lower = more overdue.

        Played matchups use actual gap from the current season:
        - last season -> 0
        - 2 seasons ago -> -1
        - 3 seasons ago -> -2
        """
        return self._played_opponent_cost(self.last_played(team, opp), season)


class _HistoryJson(TypedDict):
    matchups: dict[str, int]
