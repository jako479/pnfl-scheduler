import random
from pathlib import Path

import pytest

from pnfl_scheduler.history import NonConfHistory
from pnfl_scheduler.scheduler import PlayoffTeams, solve_schedule
from pnfl_scheduler.scheduler_history import solve_schedule as solve_schedule_history
from pnfl_scheduler.scheduler_two_phase import solve_schedule as solve_schedule_two_phase
from pnfl_scheduler.teams import Conference, Division, lookup_team

HISTORY_PATH = Path(__file__).resolve().parent.parent / "data" / "nonconf_history.json"
SCHEDULER_TWO_PHASE = "two-phase"
SCHEDULER_HISTORY = "history"
SCHEDULER_ORIGINAL = "original"


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
        "conference_ranking": {
            Conference.AFC: tuple(afc_standings),
            Conference.NFC: tuple(nfc_standings),
        },
        "non_playoff_ranked": (
            _derive_non_playoff_ranked(afc_standings, all_playoff) + _derive_non_playoff_ranked(nfc_standings, all_playoff)
        ),
    }


# Config 1: 0 WC from 4-team div per conference → 5 free slots each direction
CONFIG_5_SLOTS = _build_config(
    (
        "New England",
        "Cincinnati",
        "Pittsburgh",
        "Denver",
        "Miami",
        "Buffalo",
        "Jacksonville",
        "Los Angeles",
        "Las Vegas",
    ),
    (
        "Washington",
        "Chicago",
        "Minnesota",
        "San Francisco",
        "Atlanta",
        "New York",
        "Philadelphia",
        "Green Bay",
        "Seattle",
    ),
)

# Config 2: 1 WC from each div per conference → 6 free slots each direction
CONFIG_6_SLOTS = _build_config(
    (
        "New England",
        "Cincinnati",
        "Miami",
        "Pittsburgh",
        "Buffalo",
        "Jacksonville",
        "Denver",
        "Los Angeles",
        "Las Vegas",
    ),
    (
        "Washington",
        "Chicago",
        "Atlanta",
        "Minnesota",
        "New York",
        "Philadelphia",
        "San Francisco",
        "Green Bay",
        "Seattle",
    ),
)

# Config 3: 2 WC from 4-team div per conference → 7 free slots each direction
CONFIG_7_SLOTS = _build_config(
    (
        "New England",
        "Cincinnati",
        "Miami",
        "Buffalo",
        "Jacksonville",
        "Pittsburgh",
        "Denver",
        "Los Angeles",
        "Las Vegas",
    ),
    (
        "Washington",
        "Chicago",
        "Atlanta",
        "New York",
        "Philadelphia",
        "Minnesota",
        "San Francisco",
        "Green Bay",
        "Seattle",
    ),
)

_solve_cache = {}


def _selected_scheduler(pytest_config) -> str:
    use_history = pytest_config.getoption("--history")
    use_original = pytest_config.getoption("--no-history")

    if use_history and use_original:
        raise pytest.UsageError("Choose at most one legacy scheduler flag: --history or --no-history")
    if use_history:
        return SCHEDULER_HISTORY
    if use_original:
        return SCHEDULER_ORIGINAL
    return SCHEDULER_TWO_PHASE


def _solve_for_config(config, config_id, scheduler_kind):
    cache_key = (config_id, scheduler_kind)
    if cache_key not in _solve_cache:
        seed = random.randint(0, 1_000_000)
        label = f"{scheduler_kind}/{config_id}"
        print(f"\nScheduler seed ({label}): {seed}")
        if scheduler_kind == SCHEDULER_HISTORY:
            history = NonConfHistory.load(HISTORY_PATH)
            _solve_cache[cache_key] = solve_schedule_history(
                seed=seed,
                playoffs=config["playoffs"],
                last_place=config["last_place"],
                non_playoff_ranked=config["non_playoff_ranked"],
                history=history,
            )
        elif scheduler_kind == SCHEDULER_ORIGINAL:
            _solve_cache[cache_key] = solve_schedule(
                seed=seed,
                playoffs=config["playoffs"],
                last_place=config["last_place"],
                non_playoff_ranked=config["non_playoff_ranked"],
            )
        else:
            history = NonConfHistory.load(HISTORY_PATH)
            _solve_cache[cache_key] = solve_schedule_two_phase(
                seed=seed,
                playoffs=config["playoffs"],
                last_place=config["last_place"],
                non_playoff_ranked=config["non_playoff_ranked"],
                conference_ranking=config["conference_ranking"],
                history=history,
            )
    return _solve_cache[cache_key]


ALL_CONFIGS = [
    pytest.param(CONFIG_5_SLOTS, id="5-free-slots"),
    pytest.param(CONFIG_6_SLOTS, id="6-free-slots"),
    pytest.param(CONFIG_7_SLOTS, id="7-free-slots"),
]


def pytest_addoption(parser):
    parser.addoption(
        "--all-configs",
        action="store_true",
        default=False,
        help="Run against all 3 playoff configs (slow). Default: fastest config only.",
    )
    parser.addoption(
        "--history",
        action="store_true",
        default=False,
        help="Use the history-aware legacy scheduler instead of the two-phase default.",
    )
    parser.addoption(
        "--no-history",
        action="store_true",
        default=False,
        help="Use the original one-phase scheduler instead of the two-phase default.",
    )


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--all-configs"):
        skip = pytest.mark.skip(reason="use --all-configs to run")
        for item in items:
            if "6-free-slots" in item.nodeid or "7-free-slots" in item.nodeid:
                item.add_marker(skip)

    scheduler_kind = _selected_scheduler(config)
    if scheduler_kind != SCHEDULER_HISTORY:
        skip_history = pytest.mark.skip(reason="only runs with history scheduler")
        for item in items:
            if "history_schedule" in item.fixturenames:
                item.add_marker(skip_history)
    if scheduler_kind == SCHEDULER_TWO_PHASE:
        skip_legacy = pytest.mark.skip(reason="legacy scheduler-only rule")
        for item in items:
            if "legacy_scheduler_only" in item.keywords:
                item.add_marker(skip_legacy)
    else:
        skip_two_phase = pytest.mark.skip(reason="only runs with two-phase scheduler")
        for item in items:
            if "two_phase_only" in item.keywords:
                item.add_marker(skip_two_phase)


@pytest.fixture(params=ALL_CONFIGS, scope="session")
def config(request):
    """The raw config dict + solved schedule, paired together."""
    cfg = request.param
    cache_key = id(cfg)
    scheduler_kind = _selected_scheduler(request.config)
    sched = _solve_for_config(cfg, cache_key, scheduler_kind=scheduler_kind)
    return cfg, sched


@pytest.fixture(scope="session")
def schedule(config):
    return config[1]


@pytest.fixture(scope="session")
def standings_data(config):
    return config[0]


@pytest.fixture(scope="session")
def history_schedule(config):
    """The solved schedule from the history scheduler. Only available with --history."""
    return config[1]


@pytest.fixture(scope="session")
def history():
    """The NonConfHistory loaded from the data file."""
    return NonConfHistory.load(HISTORY_PATH)


@pytest.fixture(scope="session")
def forced_pairings(history, standings_data):
    """The 9 forced non-conf pairings computed by LinearSumAssignment."""
    from pnfl_scheduler.scheduler_history import _compute_playoff_mandated_pairs

    playoff_mandated_pairs = _compute_playoff_mandated_pairs(standings_data["playoffs"])
    return history.compute_forced_pairings(playoff_mandated_pairs=playoff_mandated_pairs)
