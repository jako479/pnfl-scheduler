from collections import Counter

import pytest

from tests.conftest import CONFIG_5_SLOTS, CONFIG_6_SLOTS, CONFIG_7_SLOTS, HISTORY_PATH

from pnfl_scheduler.history import NonConfHistory
from pnfl_scheduler.scheduler_two_phase import (
    FIXED_NONCONF_RANK_OPPONENTS,
    _fixed_rank_pairs,
    _normalize_conference_ranking,
    _rank_by_id,
    _solve_four_team_extra_rank_pairs,
    build_phase_one_matchup_inventory,
)
from pnfl_scheduler.teams import Conference, Division, TEAMS, Team, lookup_team


ALL_CONFIGS = [
    pytest.param(CONFIG_5_SLOTS, id="5-free-slots"),
    pytest.param(CONFIG_6_SLOTS, id="6-free-slots"),
    pytest.param(CONFIG_7_SLOTS, id="7-free-slots"),
]


def _phase_one_inventory(config) -> tuple[tuple[int, int], ...]:
    return build_phase_one_matchup_inventory(
        conference_ranking=config["conference_ranking"],
        last_place=config["last_place"],
        history=NonConfHistory.load(HISTORY_PATH),
    )


def _pair_counts(inventory: tuple[tuple[int, int], ...]) -> Counter[tuple[int, int]]:
    return Counter(inventory)


def _team_counts(inventory: tuple[tuple[int, int], ...]) -> Counter[int]:
    counts: Counter[int] = Counter()
    for i, j in inventory:
        counts[i] += 1
        counts[j] += 1
    return counts


def _nonconference_opponents(team: Team, inventory: tuple[tuple[int, int], ...]) -> set[Team]:
    team_by_id = {t.id: t for t in TEAMS}
    opponents: set[Team] = set()
    for i, j in inventory:
        if i == team.id and team_by_id[j].conference != team.conference:
            opponents.add(team_by_id[j])
        elif j == team.id and team_by_id[i].conference != team.conference:
            opponents.add(team_by_id[i])
    return opponents


def _ranked_teams_by_conf(config) -> dict[Conference, tuple[Team, ...]]:
    return {
        conf: tuple(lookup_team(city) for city in config["conference_ranking"][conf])
        for conf in Conference
    }


def _expected_fixed_opponents(team: Team, config) -> set[Team]:
    ranked = _ranked_teams_by_conf(config)
    conf_ranked = ranked[team.conference]
    other_conf = Conference.NFC if team.conference == Conference.AFC else Conference.AFC
    team_rank = conf_ranked.index(team) + 1
    return {
        ranked[other_conf][opp_rank - 1]
        for opp_rank in FIXED_NONCONF_RANK_OPPONENTS[team_rank]
    }


@pytest.mark.parametrize("config", ALL_CONFIGS)
def test_phase_one_inventory_has_expected_total_counts(config):
    inventory = _phase_one_inventory(config)
    pair_counts = _pair_counts(inventory)
    team_counts = _team_counts(inventory)

    assert len(inventory) == 144
    assert sum(pair_counts.values()) == 144
    for team in TEAMS:
        assert team_counts[team.id] == 16, f"{team.city}: wrong total number of games in phase-1 inventory"


@pytest.mark.parametrize("config", ALL_CONFIGS)
def test_phase_one_inventory_has_expected_divisional_and_conference_counts(config):
    inventory = _phase_one_inventory(config)
    pair_counts = _pair_counts(inventory)

    for i, team_a in enumerate(TEAMS):
        for team_b in TEAMS[i + 1 :]:
            pair = (team_a.id, team_b.id)
            if team_a.division == team_b.division:
                assert pair_counts[pair] == 2, f"{team_a.city}/{team_b.city}: divisional pair should appear twice"
            elif team_a.conference == team_b.conference:
                assert pair_counts[pair] == 1, f"{team_a.city}/{team_b.city}: conference pair should appear once"
            else:
                assert pair_counts[pair] <= 1, f"{team_a.city}/{team_b.city}: non-conference pair should appear at most once"


@pytest.mark.parametrize("config", ALL_CONFIGS)
def test_phase_one_inventory_assigns_expected_nonconference_degree(config):
    inventory = _phase_one_inventory(config)

    for team in TEAMS:
        expected = 5 if team.division in (Division.AFC_EAST, Division.NFC_EAST) else 4
        actual = len(_nonconference_opponents(team, inventory))
        assert actual == expected, f"{team.city}: wrong non-conference degree"


@pytest.mark.parametrize("config", ALL_CONFIGS)
def test_phase_one_inventory_contains_fixed_rank_table_pairs(config):
    inventory = _phase_one_inventory(config)

    for team in TEAMS:
        opponents = _nonconference_opponents(team, inventory)
        expected_fixed = _expected_fixed_opponents(team, config)
        assert expected_fixed.issubset(opponents), f"{team.city}: missing one of the fixed rank-table opponents"


@pytest.mark.parametrize("config", ALL_CONFIGS)
def test_phase_one_inventory_adds_exactly_one_extra_east_sos_pair(config):
    inventory = _phase_one_inventory(config)
    ranked = _normalize_conference_ranking(config["conference_ranking"])
    rank_by_id = _rank_by_id(ranked)
    expected_extra_pairs = _solve_four_team_extra_rank_pairs(
        ranked_teams_by_conf=ranked,
        rank_by_id=rank_by_id,
        forbidden_pairs=_fixed_rank_pairs(ranked),
    )

    assert expected_extra_pairs.issubset(set(inventory))


@pytest.mark.parametrize("config", ALL_CONFIGS)
def test_phase_one_inventory_history_fills_remaining_nonconference_slots(config):
    inventory = _phase_one_inventory(config)

    east_divisions = {Division.AFC_EAST, Division.NFC_EAST}
    for team in TEAMS:
        opponents = _nonconference_opponents(team, inventory)
        fixed = _expected_fixed_opponents(team, config)
        extra = opponents - fixed

        expected_extra = 2 if team.division in east_divisions else 1
        assert len(extra) == expected_extra, f"{team.city}: wrong number of non-fixed non-conference opponents"


@pytest.mark.parametrize("config", ALL_CONFIGS)
def test_phase_one_inventory_uses_canonical_pair_ordering(config):
    inventory = _phase_one_inventory(config)
    assert all(i < j for i, j in inventory)
