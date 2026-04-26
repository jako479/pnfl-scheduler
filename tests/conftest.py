import random
from collections.abc import Sequence
from pathlib import Path

import pytest

from pnfl_scheduler.domain.history import NonConfHistory
from pnfl_scheduler.domain.league import Division, League, build_league
from pnfl_scheduler.schedulers import DEFAULT_SCHEDULER, available_schedulers, get_scheduler
from pnfl_scheduler.schedulers.types import SchedulerResult
from pnfl_scheduler.writers.report import TxtReportWriter, build_schedule_report

HISTORY_PATH = Path(__file__).resolve().parent.parent / "data" / "nonconf_history.json"
TEST_SEASON = 2048


_DIVISIONS: dict[str, Sequence[str]] = {
    Division.AFC_EAST.name: ("New England", "Buffalo", "Miami", "Jacksonville"),
    Division.AFC_WEST.name: ("Cincinnati", "Denver", "Los Angeles", "Las Vegas", "Pittsburgh"),
    Division.NFC_EAST.name: ("Philadelphia", "Washington", "New York", "Atlanta"),
    Division.NFC_WEST.name: ("Chicago", "Green Bay", "Minnesota", "Seattle", "San Francisco"),
}


def _make_league(afc_standings: Sequence[str], nfc_standings: Sequence[str]) -> League:
    return build_league(_DIVISIONS, tuple(afc_standings), tuple(nfc_standings))


# Baseline conference ranking variant.
LEAGUE_5_SLOTS = _make_league(
    ("New England", "Cincinnati", "Pittsburgh", "Denver", "Miami", "Buffalo", "Jacksonville", "Los Angeles", "Las Vegas"),
    ("Washington", "Chicago", "Minnesota", "San Francisco", "Atlanta", "New York", "Philadelphia", "Green Bay", "Seattle"),
)

# Alternate conference ranking variant.
LEAGUE_6_SLOTS = _make_league(
    ("New England", "Cincinnati", "Miami", "Pittsburgh", "Buffalo", "Jacksonville", "Denver", "Los Angeles", "Las Vegas"),
    ("Washington", "Chicago", "Atlanta", "Minnesota", "New York", "Philadelphia", "San Francisco", "Green Bay", "Seattle"),
)

# Alternate conference ranking variant.
LEAGUE_7_SLOTS = _make_league(
    ("New England", "Cincinnati", "Miami", "Buffalo", "Jacksonville", "Pittsburgh", "Denver", "Los Angeles", "Las Vegas"),
    ("Washington", "Chicago", "Atlanta", "New York", "Philadelphia", "Minnesota", "San Francisco", "Green Bay", "Seattle"),
)


_ALL_LEAGUES = [
    pytest.param(LEAGUE_5_SLOTS, id="5-free-slots"),
    pytest.param(LEAGUE_6_SLOTS, id="6-free-slots"),
    pytest.param(LEAGUE_7_SLOTS, id="7-free-slots"),
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


_solve_cache: dict[tuple[int, str], SchedulerResult] = {}


@pytest.fixture(params=_ALL_LEAGUES, scope="session")
def league(request) -> League:
    return request.param


@pytest.fixture(scope="session")
def teams(league: League):
    return league.teams


@pytest.fixture(scope="session")
def scheduler_result(league, request, tmp_path_factory) -> SchedulerResult:
    scheduler_kind = request.config.getoption("--scheduler")
    cache_key = (id(league), scheduler_kind)
    if cache_key not in _solve_cache:
        seed = random.randint(0, 1_000_000)
        print(f"\nScheduler seed ({scheduler_kind}): {seed}")
        history = NonConfHistory.load(HISTORY_PATH)
        scheduler = get_scheduler(scheduler_kind)
        result = scheduler(league=league, seed=seed, history=history, season=TEST_SEASON)
        _solve_cache[cache_key] = result

        report = build_schedule_report(
            schedule=result.schedule,
            matchup_plan=result.matchup_plan,
            league=league,
            history=history,
            seed=seed,
            scheduler_kind=scheduler_kind,
            config_path=Path("test-config.ini"),
            history_path=HISTORY_PATH,
            elapsed_time_seconds=0.0,
        )
        report_path = tmp_path_factory.mktemp("schedule_report") / "report.txt"
        TxtReportWriter(str(report_path)).write(report)
        print(f"Schedule report: {report_path}")
    return _solve_cache[cache_key]


@pytest.fixture(scope="session")
def schedule(scheduler_result):
    return scheduler_result.schedule


@pytest.fixture(scope="session")
def matchup_plan(scheduler_result):
    return scheduler_result.matchup_plan


@pytest.fixture(scope="session")
def history():
    return NonConfHistory.load(HISTORY_PATH)
