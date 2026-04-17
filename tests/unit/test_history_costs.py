from pathlib import Path

from pnfl_scheduler.domain.history import NonConfHistory
from pnfl_scheduler.domain.teams import lookup_team
from pnfl_scheduler.schedulers.two_phase import _history_pair_cost

TEST_SEASON = 2048
TEST_HISTORY_PATH = Path(__file__).resolve().parents[1] / "data" / "nonconf_history.json"
EXPECTED_H2H_COSTS = {
    "Buffalo|Atlanta": 5,
    "Buffalo|New York": 6,
    "Buffalo|Philadelphia": 6,
    "Buffalo|Washington": 6,
    "Buffalo|Chicago": 3,
    "Buffalo|Green Bay": 4,
    "Buffalo|Minnesota": 6,
    "Buffalo|San Francisco": 5,
    "Buffalo|Seattle": 6,
    "Jacksonville|Atlanta": 6,
    "Jacksonville|New York": 6,
    "Jacksonville|Philadelphia": 4,
    "Jacksonville|Washington": 6,
    "Jacksonville|Chicago": 6,
    "Jacksonville|Green Bay": 5,
    "Jacksonville|Minnesota": 3,
    "Jacksonville|San Francisco": 6,
    "Jacksonville|Seattle": 5,
    "Miami|Atlanta": 6,
    "Miami|New York": 4,
    "Miami|Philadelphia": 6,
    "Miami|Washington": 6,
    "Miami|Chicago": 4,
    "Miami|Green Bay": 2,
    "Miami|Minnesota": 6,
    "Miami|San Francisco": 5,
    "Miami|Seattle": 6,
    "New England|Atlanta": 6,
    "New England|New York": 6,
    "New England|Philadelphia": 6,
    "New England|Washington": 5,
    "New England|Chicago": 5,
    "New England|Green Bay": 6,
    "New England|Minnesota": 4,
    "New England|San Francisco": 6,
    "New England|Seattle": 5,
    "Cincinnati|Atlanta": 6,
    "Cincinnati|New York": 5,
    "Cincinnati|Philadelphia": 0,
    "Cincinnati|Washington": 5,
    "Cincinnati|Chicago": 6,
    "Cincinnati|Green Bay": 6,
    "Cincinnati|Minnesota": 5,
    "Cincinnati|San Francisco": 6,
    "Cincinnati|Seattle": 5,
    "Denver|Atlanta": 6,
    "Denver|New York": 6,
    "Denver|Philadelphia": 0,
    "Denver|Washington": 5,
    "Denver|Chicago": 6,
    "Denver|Green Bay": 6,
    "Denver|Minnesota": 5,
    "Denver|San Francisco": 5,
    "Denver|Seattle": 4,
    "Las Vegas|Atlanta": 5,
    "Las Vegas|New York": 3,
    "Las Vegas|Philadelphia": 6,
    "Las Vegas|Washington": 6,
    "Las Vegas|Chicago": 0,
    "Las Vegas|Green Bay": 5,
    "Las Vegas|Minnesota": 6,
    "Las Vegas|San Francisco": 4,
    "Las Vegas|Seattle": 6,
    "Los Angeles|Atlanta": 0,
    "Los Angeles|New York": 0,
    "Los Angeles|Philadelphia": 0,
    "Los Angeles|Washington": 0,
    "Los Angeles|Chicago": 0,
    "Los Angeles|Green Bay": 0,
    "Los Angeles|Minnesota": 0,
    "Los Angeles|San Francisco": 0,
    "Los Angeles|Seattle": 0,
    "Pittsburgh|Atlanta": 5,
    "Pittsburgh|New York": 5,
    "Pittsburgh|Philadelphia": 6,
    "Pittsburgh|Washington": 6,
    "Pittsburgh|Chicago": 5,
    "Pittsburgh|Green Bay": 3,
    "Pittsburgh|Minnesota": 6,
    "Pittsburgh|San Francisco": 1,
    "Pittsburgh|Seattle": 6,
}


def _fixture_history() -> NonConfHistory:
    return NonConfHistory.load(TEST_HISTORY_PATH)


def test_opponent_cost_uses_zero_for_never_played_and_contiguous_season_values():
    buffalo = lookup_team("Buffalo")
    atlanta = lookup_team("Atlanta")
    chicago = lookup_team("Chicago")
    new_york = lookup_team("New York")

    history = NonConfHistory(
        {
            "Buffalo|Atlanta": None,
            "Buffalo|Chicago": 2043,
            "Buffalo|New York": 2047,
        }
    )

    assert history.opponent_cost(buffalo, atlanta, TEST_SEASON) == 0
    assert history.opponent_cost(buffalo, chicago, TEST_SEASON) == 1
    assert history.opponent_cost(buffalo, new_york, TEST_SEASON) == 5


def test_history_pair_cost_uses_history_only_with_no_sos_tiebreak():
    buffalo = lookup_team("Buffalo")
    atlanta = lookup_team("Atlanta")
    chicago = lookup_team("Chicago")

    history = NonConfHistory(
        {
            "Buffalo|Atlanta": 2045,
            "Buffalo|Chicago": 2045,
        }
    )

    assert _history_pair_cost(buffalo, atlanta, history, TEST_SEASON) == 1
    assert _history_pair_cost(buffalo, chicago, history, TEST_SEASON) == 1
    assert _history_pair_cost(buffalo, atlanta, None, TEST_SEASON) == 0
    assert _history_pair_cost(buffalo, atlanta, history, None) == 0


def test_nonconf_history_file_has_expected_h2h_costs_for_all_pairs():
    history = _fixture_history()
    assert len(EXPECTED_H2H_COSTS) == 81

    for key, expected_cost in EXPECTED_H2H_COSTS.items():
        afc_city, nfc_city = key.split("|")
        assert history.opponent_cost(lookup_team(afc_city), lookup_team(nfc_city), TEST_SEASON) == expected_cost
