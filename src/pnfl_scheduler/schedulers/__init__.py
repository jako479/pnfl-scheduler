from __future__ import annotations

from collections.abc import Callable

from ..domain.schedule import Schedule
from .two_phase import solve_schedule as solve_schedule_two_phase

SchedulerFunc = Callable[..., Schedule]

DEFAULT_SCHEDULER = "two-phase"

SCHEDULERS: dict[str, SchedulerFunc] = {
    DEFAULT_SCHEDULER: solve_schedule_two_phase,
}


def available_schedulers() -> tuple[str, ...]:
    return tuple(SCHEDULERS)


def get_scheduler(name: str) -> SchedulerFunc:
    try:
        return SCHEDULERS[name]
    except KeyError as exc:
        choices = ", ".join(sorted(SCHEDULERS))
        raise ValueError(f"Unknown scheduler '{name}'. Available schedulers: {choices}") from exc
