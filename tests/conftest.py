import random
from pathlib import Path

import pytest

from pnfl_scheduler.domain.history import NonConfHistory
from pnfl_scheduler.domain.teams import Conference
from pnfl_scheduler.schedulers import DEFAULT_SCHEDULER, available_schedulers, get_scheduler

HISTORY_PATH = Path(__file__).resolve().parent.parent / "data" / "nonconf_history.json"


def _build_config(afc_standings, nfc_standings):
    return {
        "conference_ranking": {
            Conference.AFC: tuple(afc_standings),
            Conference.NFC: tuple(nfc_standings),
        },
    }


# Baseline conference ranking variant.
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

# Alternate conference ranking variant.
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

# Alternate conference ranking variant.
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
    return pytest_config.getoption("--scheduler")


def _solve_for_config(config, config_id, scheduler_kind):
    cache_key = (config_id, scheduler_kind)
    if cache_key not in _solve_cache:
        seed = random.randint(0, 1_000_000)
        label = f"{scheduler_kind}/{config_id}"
        print(f"\nScheduler seed ({label}): {seed}")
        history = NonConfHistory.load(HISTORY_PATH)
        scheduler = get_scheduler(scheduler_kind)
        _solve_cache[cache_key] = scheduler(
            seed=seed,
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
        help="Run against all 3 ranking configs (slow). Default: fastest config only.",
    )
    parser.addoption(
        "--scheduler",
        action="store",
        choices=available_schedulers(),
        default=DEFAULT_SCHEDULER,
        help="Scheduler implementation to run.",
    )


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--all-configs"):
        skip = pytest.mark.skip(reason="use --all-configs to run")
        for item in items:
            if "6-free-slots" in item.nodeid or "7-free-slots" in item.nodeid:
                item.add_marker(skip)


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
def history():
    """The NonConfHistory loaded from the data file."""
    return NonConfHistory.load(HISTORY_PATH)
