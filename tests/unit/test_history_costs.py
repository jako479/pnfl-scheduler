from pnfl_scheduler.domain.history import NonConfHistory
from pnfl_scheduler.domain.league import lookup_team
from tests.conftest import HISTORY_PATH, TEST_SEASON

EXPECTED_H2H_COSTS = {
    "Buffalo|Atlanta": -1,
    "Buffalo|New York": 0,
    "Buffalo|Philadelphia": 0,
    "Buffalo|Washington": 0,
    "Buffalo|Chicago": -3,
    "Buffalo|Green Bay": -2,
    "Buffalo|Minnesota": 0,
    "Buffalo|San Francisco": -1,
    "Buffalo|Seattle": 0,
    "Jacksonville|Atlanta": 0,
    "Jacksonville|New York": 0,
    "Jacksonville|Philadelphia": -2,
    "Jacksonville|Washington": 0,
    "Jacksonville|Chicago": 0,
    "Jacksonville|Green Bay": -1,
    "Jacksonville|Minnesota": -3,
    "Jacksonville|San Francisco": 0,
    "Jacksonville|Seattle": -1,
    "Miami|Atlanta": 0,
    "Miami|New York": -2,
    "Miami|Philadelphia": 0,
    "Miami|Washington": 0,
    "Miami|Chicago": -2,
    "Miami|Green Bay": -4,
    "Miami|Minnesota": 0,
    "Miami|San Francisco": -1,
    "Miami|Seattle": 0,
    "New England|Atlanta": 0,
    "New England|New York": 0,
    "New England|Philadelphia": 0,
    "New England|Washington": -1,
    "New England|Chicago": -1,
    "New England|Green Bay": 0,
    "New England|Minnesota": -2,
    "New England|San Francisco": 0,
    "New England|Seattle": -1,
    "Cincinnati|Atlanta": 0,
    "Cincinnati|New York": -1,
    "Cincinnati|Philadelphia": -6,
    "Cincinnati|Washington": -1,
    "Cincinnati|Chicago": 0,
    "Cincinnati|Green Bay": 0,
    "Cincinnati|Minnesota": -1,
    "Cincinnati|San Francisco": 0,
    "Cincinnati|Seattle": -1,
    "Denver|Atlanta": 0,
    "Denver|New York": 0,
    "Denver|Philadelphia": -6,
    "Denver|Washington": -1,
    "Denver|Chicago": 0,
    "Denver|Green Bay": 0,
    "Denver|Minnesota": -1,
    "Denver|San Francisco": -1,
    "Denver|Seattle": -2,
    "Las Vegas|Atlanta": -1,
    "Las Vegas|New York": -3,
    "Las Vegas|Philadelphia": 0,
    "Las Vegas|Washington": 0,
    "Las Vegas|Chicago": -6,
    "Las Vegas|Green Bay": -1,
    "Las Vegas|Minnesota": 0,
    "Las Vegas|San Francisco": -2,
    "Las Vegas|Seattle": 0,
    "Los Angeles|Atlanta": -6,
    "Los Angeles|New York": -6,
    "Los Angeles|Philadelphia": -6,
    "Los Angeles|Washington": -6,
    "Los Angeles|Chicago": -6,
    "Los Angeles|Green Bay": -6,
    "Los Angeles|Minnesota": -6,
    "Los Angeles|San Francisco": -6,
    "Los Angeles|Seattle": -6,
    "Pittsburgh|Atlanta": -1,
    "Pittsburgh|New York": -1,
    "Pittsburgh|Philadelphia": 0,
    "Pittsburgh|Washington": 0,
    "Pittsburgh|Chicago": -1,
    "Pittsburgh|Green Bay": -3,
    "Pittsburgh|Minnesota": 0,
    "Pittsburgh|San Francisco": -5,
    "Pittsburgh|Seattle": 0,
}


def test_opponent_cost_uses_contiguous_season_values_and_never_played_below_oldest(teams):
    buffalo = lookup_team(teams, "Buffalo")
    atlanta = lookup_team(teams, "Atlanta")
    chicago = lookup_team(teams, "Chicago")
    new_york = lookup_team(teams, "New York")

    history = NonConfHistory(
        {
            "Buffalo|Atlanta": None,
            "Buffalo|Chicago": 2043,
            "Buffalo|New York": 2047,
        }
    )

    # Played: cost = last_played - season + 1. Last-season = 0, older goes more negative.
    assert history.opponent_cost(buffalo, new_york, TEST_SEASON) == 0
    assert history.opponent_cost(buffalo, chicago, TEST_SEASON) == -4
    # Never played: one lower than the oldest played matchup cost.
    assert history.opponent_cost(buffalo, atlanta, TEST_SEASON) == -5


def test_nonconf_history_file_has_expected_h2h_costs_for_all_pairs(teams):
    history = NonConfHistory.load(HISTORY_PATH)
    assert len(EXPECTED_H2H_COSTS) == 81

    for key, expected_cost in EXPECTED_H2H_COSTS.items():
        afc_metro, nfc_metro = key.split("|")
        assert history.opponent_cost(lookup_team(teams, afc_metro), lookup_team(teams, nfc_metro), TEST_SEASON) == expected_cost
