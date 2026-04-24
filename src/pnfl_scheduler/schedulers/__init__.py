from collections.abc import Callable

from pnfl_scheduler.schedulers.fixed_matchup_scheduler import generate_schedule as fixed_matchup_scheduler
from pnfl_scheduler.schedulers.scheduler import generate_schedule as rank_scheduler
from pnfl_scheduler.schedulers.types import SchedulerResult

SchedulerFunc = Callable[..., SchedulerResult]

DEFAULT_SCHEDULER = "fixed-matchup"
RANK_ONLY_SCHEDULER = "two-phase-rank"

SCHEDULERS: dict[str, SchedulerFunc] = {
    DEFAULT_SCHEDULER: fixed_matchup_scheduler,
    RANK_ONLY_SCHEDULER: rank_scheduler,
}


def available_schedulers() -> tuple[str, ...]:
    return tuple(SCHEDULERS)


def get_scheduler(name: str) -> SchedulerFunc:
    try:
        return SCHEDULERS[name]
    except KeyError as exc:
        choices = ", ".join(sorted(SCHEDULERS))
        raise ValueError(f"Unknown scheduler '{name}'. Available schedulers: {choices}") from exc
