"""Non-conference matchup history for rotation-fair scheduling."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .teams import TEAMS, Conference, Team

FORMAT_VERSION = 1


def _canonical_key(team_a: Team, team_b: Team) -> str:
    """Return 'AFCcity|NFCcity' key for a non-conference pair."""
    afc = team_a if team_a.conference == Conference.AFC else team_b
    nfc = team_b if team_a.conference == Conference.AFC else team_a
    return f"{afc.city}|{nfc.city}"


def _all_nonconf_keys() -> list[str]:
    """Return all 81 canonical non-conference pair keys."""
    from .teams import Division

    div_order = [Division.AFC_EAST, Division.AFC_WEST]
    nfc_div_order = [Division.NFC_EAST, Division.NFC_WEST]

    afc: list[Team] = []
    for div in div_order:
        afc.extend(sorted((t for t in TEAMS if t.division == div), key=lambda t: t.city))

    nfc: list[Team] = []
    for div in nfc_div_order:
        nfc.extend(sorted((t for t in TEAMS if t.division == div), key=lambda t: t.city))

    return [f"{a.city}|{n.city}" for a in afc for n in nfc]


class NonConfHistory:
    """Tracks the last season each non-conference pair played."""

    def __init__(self, matchups: dict[str, int | None] | None = None) -> None:
        if matchups is None:
            self._matchups: dict[str, int | None] = {k: None for k in _all_nonconf_keys()}
        else:
            self._matchups = dict(matchups)

    @classmethod
    def load(cls, path: Path | str) -> NonConfHistory:
        """Load from JSON file. Returns empty history if file doesn't exist."""
        path = Path(path)
        if not path.exists():
            return cls()
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
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
        return self._matchups[_canonical_key(team_a, team_b)]

    def record_matchup(self, team_a: Team, team_b: Team, season: int) -> None:
        """Record that these two teams played in the given season."""
        self._matchups[_canonical_key(team_a, team_b)] = season

    def opponent_cost(self, team: Team, opp: Team, season: int) -> int:
        """Return cost for this matchup. Lower = more overdue.

        Never played returns 0.
        Played matchups are ranked by last-played season starting at 1 for
        the oldest recorded played season and increasing by 1 per season
        toward the present.
        """
        s = self.last_played(team, opp)
        if s is None:
            return 0

        oldest_played = min(played for played in self._matchups.values() if played is not None)
        return (s - oldest_played) + 1
