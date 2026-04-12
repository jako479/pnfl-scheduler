import random

import pytest

from pnfl_scheduler.scheduler import PlayoffTeams, solve_schedule
from pnfl_scheduler.teams import Division, lookup_team


def _derive_division_winners(conf_standings):
    seen_divs = set()
    winners = []
    for city in conf_standings:
        team = lookup_team(city)
        if team.division not in seen_divs:
            winners.append(city)
            seen_divs.add(team.division)
    return winners


def _derive_wild_cards(conf_standings, dw_cities):
    dw_set = set(dw_cities)
    wcs = []
    for city in conf_standings:
        if city not in dw_set:
            wcs.append(city)
            if len(wcs) == 2:
                break
    return wcs


def _derive_last_place_5team(conf_standings):
    for city in reversed(conf_standings):
        team = lookup_team(city)
        if team.division in (Division.AFC_WEST, Division.NFC_WEST):
            return city
    raise ValueError("No 5-team division team found")


def _derive_non_playoff_ranked(conf_standings, playoff_cities):
    playoff_set = set(playoff_cities)
    return [c for c in conf_standings if c not in playoff_set]


def _build_config(afc_standings, nfc_standings):
    afc_dws = _derive_division_winners(afc_standings)
    nfc_dws = _derive_division_winners(nfc_standings)
    afc_wcs = _derive_wild_cards(afc_standings, afc_dws)
    nfc_wcs = _derive_wild_cards(nfc_standings, nfc_dws)
    all_dws = tuple(afc_dws + nfc_dws)
    all_wcs = tuple(afc_wcs + nfc_wcs)
    all_playoff = set(all_dws + all_wcs)
    return {
        "playoffs": PlayoffTeams(division_winners=all_dws, wild_cards=all_wcs),
        "last_place": (
            _derive_last_place_5team(afc_standings),
            _derive_last_place_5team(nfc_standings),
        ),
        "non_playoff_ranked": (
            _derive_non_playoff_ranked(afc_standings, all_playoff)
            + _derive_non_playoff_ranked(nfc_standings, all_playoff)
        ),
    }


# Config 1: 0 WC from 4-team div per conference → 5 free slots each direction
CONFIG_5_SLOTS = _build_config(
    ("New England", "Cincinnati", "Pittsburgh", "Denver",
     "Miami", "Buffalo", "Jacksonville", "Los Angeles", "Las Vegas"),
    ("Washington", "Chicago", "Minnesota", "San Francisco",
     "Atlanta", "New York", "Philadelphia", "Green Bay", "Seattle"),
)

# Config 2: 1 WC from each div per conference → 6 free slots each direction
CONFIG_6_SLOTS = _build_config(
    ("New England", "Cincinnati", "Miami", "Pittsburgh",
     "Buffalo", "Jacksonville", "Denver", "Los Angeles", "Las Vegas"),
    ("Washington", "Chicago", "Atlanta", "Minnesota",
     "New York", "Philadelphia", "San Francisco", "Green Bay", "Seattle"),
)

# Config 3: 2 WC from 4-team div per conference → 7 free slots each direction
CONFIG_7_SLOTS = _build_config(
    ("New England", "Cincinnati", "Miami", "Buffalo",
     "Jacksonville", "Pittsburgh", "Denver", "Los Angeles", "Las Vegas"),
    ("Washington", "Chicago", "Atlanta", "New York",
     "Philadelphia", "Minnesota", "San Francisco", "Green Bay", "Seattle"),
)

_solve_cache = {}


def _solve_for_config(config, config_id):
    if config_id not in _solve_cache:
        seed = random.randint(0, 1_000_000)
        print(f"\nScheduler seed ({config_id}): {seed}")
        _solve_cache[config_id] = solve_schedule(
            seed=seed,
            playoffs=config["playoffs"],
            last_place=config["last_place"],
            non_playoff_ranked=config["non_playoff_ranked"],
        )
    return _solve_cache[config_id]


CONFIGS = [
    pytest.param(CONFIG_5_SLOTS, id="5-free-slots"),
    pytest.param(CONFIG_6_SLOTS, id="6-free-slots"),
    pytest.param(CONFIG_7_SLOTS, id="7-free-slots"),
]


@pytest.fixture(params=CONFIGS, scope="session")
def config(request):
    """The raw config dict + solved schedule, paired together."""
    cfg = request.param
    cache_key = id(cfg)
    sched = _solve_for_config(cfg, cache_key)
    return cfg, sched


@pytest.fixture(scope="session")
def schedule(config):
    return config[1]


@pytest.fixture(scope="session")
def standings_data(config):
    return config[0]
