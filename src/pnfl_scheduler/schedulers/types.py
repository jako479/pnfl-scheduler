"""Shared scheduler types and the registry of available scheduler implementations."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from pnfl_scheduler.domain.league import Team
from pnfl_scheduler.domain.schedule import Schedule

Matchup = tuple[Team, Team]
Matchups = Sequence[Matchup]


def make_matchup(team_a: Team, team_b: Team) -> Matchup:
    a, b = sorted((team_a, team_b), key=lambda t: t.metro)
    return (a, b)


@dataclass(frozen=True)
class MatchupPlan:
    matchups: Matchups
    fixed_nonconference_pairs: frozenset[Matchup] = frozenset()
    extra_nonconference_pairs: frozenset[Matchup] = frozenset()
    history_nonconference_pairs: frozenset[Matchup] = frozenset()


@dataclass(frozen=True)
class SchedulerResult:
    schedule: Schedule
    matchup_plan: MatchupPlan


SchedulerFunc = Callable[..., SchedulerResult]

DEFAULT_SCHEDULER = "fixed-matchup"
RANK_ONLY_SCHEDULER = "two-phase-rank"

_SCHEDULER_NAMES = (DEFAULT_SCHEDULER, RANK_ONLY_SCHEDULER)


def available_schedulers() -> tuple[str, ...]:
    """Return the registered scheduler keys."""
    return _SCHEDULER_NAMES


def get_scheduler(name: str) -> SchedulerFunc:
    """Return the scheduler function for `name`. Raises ValueError if unknown.

    Implementations are imported lazily here so this module stays a leaf —
    schedulers depend on `SchedulerResult` defined above, so an eager import
    at module level would form a cycle.
    """
    if name == DEFAULT_SCHEDULER:
        from pnfl_scheduler.schedulers.fixed_matchup_scheduler import generate_schedule

        return generate_schedule
    if name == RANK_ONLY_SCHEDULER:
        from pnfl_scheduler.schedulers.scheduler import generate_schedule

        return generate_schedule
    choices = ", ".join(_SCHEDULER_NAMES)
    raise ValueError(f"Unknown scheduler '{name}'. Available schedulers: {choices}")
