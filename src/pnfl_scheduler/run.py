from __future__ import annotations

from pathlib import Path

from .config import AppConfig, PROJECT_DIR, load_config
from .history import NonConfHistory
from .schedule import Schedule
from .scheduler_two_phase import solve_schedule
from .writer import ScheduleWriter

DEFAULT_HISTORY_PATH = PROJECT_DIR / "data" / "nonconf_history.json"


def generate_schedule(
    *,
    seed: int = 0,
    time_limit: float | None = None,
    config: AppConfig | None = None,
    config_path: Path | None = None,
    history: NonConfHistory | None = None,
    history_path: Path | None = None,
    writer: ScheduleWriter | None = None,
) -> Schedule:
    """Generate a schedule and optionally hand it to an injected writer."""
    app_config = config or load_config(config_path)
    schedule = solve_schedule(
        seed=seed,
        time_limit=time_limit if time_limit is not None else app_config.Settings.TimeLimit,
        conference_ranking=app_config.ConferenceRanking,
        history=history or NonConfHistory.load(history_path or DEFAULT_HISTORY_PATH),
    )
    if writer is not None:
        writer.write(schedule)
    return schedule
