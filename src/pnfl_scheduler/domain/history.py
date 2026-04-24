"""Non-conference matchup history for rotation-fair scheduling."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

from pnfl_scheduler.domain.teams import Conference, Team

FORMAT_VERSION = 1

# Lowers the H2H cost for matchups between coaches that have never played each other
NEVER_PLAYED_COST_BONUS = 1


def _canonical_key(team_a: Team, team_b: Team) -> str:
    """Return 'AFCcity|NFCcity' key for a non-conference pair."""
    afc = team_a if team_a.conference == Conference.AFC else team_b
    nfc = team_b if team_a.conference == Conference.AFC else team_a
    return f"{afc.metro}|{nfc.metro}"


class NonConfHistory:
    """Tracks the last season each non-conference pair played."""

    def __init__(self, matchups: dict[str, int | None] | None = None) -> None:
        self._matchups: dict[str, int | None] = {} if matchups is None else dict(matchups)

    @classmethod
    def load(cls, path: Path | str) -> NonConfHistory:
        """Load from JSON file. Returns empty history if file doesn't exist."""
        path = Path(path)
        if not path.exists():
            return cls()
        data: _HistoryJson = json.loads(path.read_text(encoding="utf-8"))
        return cls(matchups=data["matchups"])

    def save(self, path: Path | str) -> None:
        """Write history to JSON file."""
        path = Path(path)
        data = {
            "format_version": FORMAT_VERSION,
            "matchups": self._matchups,
        }
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def last_played(self, team_a: Team, team_b: Team) -> int | None:
        """Return the last season these two teams played, or None if never."""
        return self._matchups.get(_canonical_key(team_a, team_b))

    def record_matchup(self, team_a: Team, team_b: Team, season: int) -> None:
        """Record that these two teams played in the given season."""
        self._matchups[_canonical_key(team_a, team_b)] = season

    @staticmethod
    def _played_opponent_cost(last_played: int, season: int) -> int:
        """Return gap-based cost for a played matchup.

        Examples:
        - last season -> 0
        - 2 seasons ago -> -1
        - 3 seasons ago -> -2
        """
        return last_played - season + 1

    def _never_played_cost(self, season: int) -> int:
        """Return a cost one lower than the oldest played matchup cost."""
        played_seasons = [played for played in self._matchups.values() if played is not None and played < season]
        if not played_seasons:
            raise ValueError("Cannot compute never-played cost without any prior played matchups in history")
        oldest_played = min(played_seasons)
        return self._played_opponent_cost(oldest_played, season) - NEVER_PLAYED_COST_BONUS

    def opponent_cost(self, team: Team, opp: Team, season: int) -> int:
        """Return cost for this matchup. Lower = more overdue.

        Played matchups use actual gap from the current season:
        - last season -> 0
        - 2 seasons ago -> -1
        - 3 seasons ago -> -2

        Never played returns one lower than the oldest played matchup cost for
        the current season.
        """
        s = self.last_played(team, opp)
        if s is None:
            return self._never_played_cost(season)

        return self._played_opponent_cost(s, season)


class _HistoryJson(TypedDict):
    format_version: int
    matchups: dict[str, int | None]
