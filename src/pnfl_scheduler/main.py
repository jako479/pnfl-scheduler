from __future__ import annotations

import time
from pathlib import Path

from pnfl_scheduler.config import load_league, load_settings
from pnfl_scheduler.domain.history import NonConfHistory
from pnfl_scheduler.schedulers import DEFAULT_SCHEDULER, get_scheduler
from pnfl_scheduler.schedulers.types import SchedulerResult
from pnfl_scheduler.writers import get_writer
from pnfl_scheduler.writers.report import TxtReportWriter, build_schedule_report

PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_HISTORY_PATH = PROJECT_DIR / "data" / "nonconf_history.json"


def generate_schedule(
    *,
    output: Path,
    output_format: str,
    season: int,
    scheduler: str = DEFAULT_SCHEDULER,
    config_path: Path,
    history_path: Path,
    report_path: Path,
    seed: int,
    time_limit: float | None,
    command_line: str,
) -> SchedulerResult:
    settings = load_settings(config_path)
    league = load_league(config_path)
    history = NonConfHistory.load(history_path)
    writer = get_writer(output_format, output)

    started = time.perf_counter()
    result = get_scheduler(scheduler)(
        league=league,
        history=history,
        season=season,
        seed=seed,
        time_limit=time_limit if time_limit is not None else settings.time_limit,
    )
    elapsed = time.perf_counter() - started

    writer.write(result.schedule)
    report = build_schedule_report(
        schedule=result.schedule,
        matchup_plan=result.matchup_plan,
        league=league,
        history=history,
        seed=seed,
        scheduler_kind=scheduler,
        config_path=config_path,
        history_path=history_path,
        elapsed_time_seconds=elapsed,
        command_line=command_line,
    )
    TxtReportWriter(report_path).write(report)
    print(f"Generated {len(result.schedule.games)} games -> {output}; report -> {report_path} (seed {seed})")
    return result
