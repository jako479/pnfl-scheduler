"""Phase-1 inventory tests for the rank-only MatchupBuilder (the `two-phase` scheduler)."""

from __future__ import annotations

from collections import Counter

import pytest
from conftest import HISTORY_PATH, TEST_SEASON

from pnfl_scheduler.domain.history import NonConfHistory
from pnfl_scheduler.domain.league import Division, League, Team
from pnfl_scheduler.schedulers.matchup_builder import MatchupBuilder
from pnfl_scheduler.schedulers.types import MatchupPlan, make_matchup


@pytest.fixture(scope="session")
def rank_only_matchup_plan(league: League) -> MatchupPlan:
    return MatchupBuilder(
        teams=league.teams,
        rankings=league.rankings,
        history=NonConfHistory.load(HISTORY_PATH),
        season=TEST_SEASON,
    ).build_matchup_plan()


def _team_counts(matchups) -> Counter[Team]:
    counts: Counter[Team] = Counter()
    for i, j in matchups:
        counts[i] += 1
        counts[j] += 1
    return counts


def _nonconference_degree(team: Team, matchups) -> int:
    return sum(1 for i, j in matchups if team in (i, j) and i.conference != j.conference)


def test_rank_only_inventory_has_expected_total_counts(rank_only_matchup_plan, league) -> None:
    matchups = rank_only_matchup_plan.matchups
    assert len(matchups) == 144
    team_counts = _team_counts(matchups)
    for team in league.teams:
        assert team_counts[team] == 16, f"{team.metro}: wrong total game count in phase-1 inventory"


def test_rank_only_inventory_has_expected_divisional_and_conference_counts(rank_only_matchup_plan, league) -> None:
    pair_counts = Counter(rank_only_matchup_plan.matchups)
    for i, team_a in enumerate(league.teams):
        for team_b in league.teams[i + 1 :]:
            pair = make_matchup(team_a, team_b)
            if team_a.division == team_b.division:
                assert pair_counts[pair] == 2, f"{team_a.metro}/{team_b.metro}: divisional pair should appear twice"
            elif team_a.conference == team_b.conference:
                assert pair_counts[pair] == 1, f"{team_a.metro}/{team_b.metro}: conference pair should appear once"
            else:
                assert pair_counts[pair] <= 1, (
                    f"{team_a.metro}/{team_b.metro}: non-conference pair should appear at most once"
                )


def test_rank_only_inventory_assigns_expected_nonconference_degree(rank_only_matchup_plan, league) -> None:
    for team in league.teams:
        expected = 5 if team.division in (Division.AFC_EAST, Division.NFC_EAST) else 4
        actual = _nonconference_degree(team, rank_only_matchup_plan.matchups)
        assert actual == expected, f"{team.metro}: wrong non-conference degree"


def test_rank_only_inventory_uses_canonical_pair_ordering(rank_only_matchup_plan) -> None:
    assert all(i.metro < j.metro for i, j in rank_only_matchup_plan.matchups)
