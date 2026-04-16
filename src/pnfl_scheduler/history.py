"""Non-conference matchup history for rotation-fair scheduling."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ortools.graph.python import linear_sum_assignment

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

    def opponent_cost(self, team: Team, opp: Team) -> int:
        """Return cost for this matchup. Lower = more overdue.

        null (never played) = 0, then seasons ranked oldest-first:
        oldest = 1, next oldest = 2, etc.
        """
        non_conf_teams = [t for t in TEAMS if t.conference != team.conference]
        seasons = sorted({s for t in non_conf_teams if (s := self.last_played(team, t)) is not None})
        season_to_cost = {s: i + 1 for i, s in enumerate(seasons)}

        s = self.last_played(team, opp)
        return 0 if s is None else season_to_cost[s]

    def compute_forced_pairings(
        self,
        playoff_mandated_pairs: set[tuple[int, int]] | None = None,
    ) -> set[tuple[int, int]]:
        """Use LinearSumAssignment to find the optimal 9 non-conf pairings.

        Each AFC team is assigned one NFC opponent that minimizes total
        staleness cost. Playoff-mandated pairs are excluded from the assignment
        so teams are forced to pick a different history-based opponent.

        Returns pairs as (smaller_id, larger_id) tuples.
        """
        if playoff_mandated_pairs is None:
            playoff_mandated_pairs = set()

        afc_teams = [t for t in TEAMS if t.conference == Conference.AFC]
        nfc_teams = [t for t in TEAMS if t.conference == Conference.NFC]

        # Map team IDs to assignment matrix indices
        afc_idx = {t.id: i for i, t in enumerate(afc_teams)}
        nfc_idx = {t.id: i for i, t in enumerate(nfc_teams)}

        assignment = linear_sum_assignment.SimpleLinearSumAssignment()

        for a in afc_teams:
            for n in nfc_teams:
                pair = (min(a.id, n.id), max(a.id, n.id))
                if pair in playoff_mandated_pairs:
                    continue  # Skip pairs already reserved by the playoff rules.

                # Cost is the sum of both sides' staleness
                cost = self.opponent_cost(a, n) + self.opponent_cost(n, a)
                assignment.add_arc_with_cost(afc_idx[a.id], nfc_idx[n.id], cost)

        status = assignment.solve()
        if status != assignment.OPTIMAL:
            raise RuntimeError("LinearSumAssignment failed to find optimal history pairings")

        forced: set[tuple[int, int]] = set()
        for i, a in enumerate(afc_teams):
            j = assignment.right_mate(i)
            n = nfc_teams[j]
            forced.add((min(a.id, n.id), max(a.id, n.id)))

        return forced
