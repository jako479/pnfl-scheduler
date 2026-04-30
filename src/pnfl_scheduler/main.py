"""Orchestrate schedule generation: load config, run a scheduler, write outputs."""

from __future__ import annotations

import time
from os import PathLike
from pathlib import Path

from pnfl_scheduler.config import load_config, load_league
from pnfl_scheduler.domain.history import NonConfHistory
from pnfl_scheduler.schedulers.types import DEFAULT_SCHEDULER, SchedulerResult, get_scheduler
from pnfl_scheduler.writers.report import TxtReportWriter, build_schedule_report
from pnfl_scheduler.writers.writer import get_writer

StrPath = str | PathLike[str]


def default_report_path(output: StrPath) -> Path:
    """Return `<output-stem>-report.txt` next to `output`."""
    output = Path(output)
    return output.with_name(f"{output.stem}-report.txt")


def generate_schedule(
    *,
    output: StrPath,
    output_format: str,
    season: int,
    scheduler: str = DEFAULT_SCHEDULER,
    config_path: StrPath,
    history_path: StrPath,
    report_path: StrPath,
    seed: int,
    time_limit: float | None,
    command_line: str,
) -> SchedulerResult:
    """Run the chosen scheduler and persist its schedule + report.

    Loads league + non-conference history from the given paths, solves with
    the selected scheduler (subject to `time_limit`), writes the schedule via
    the format-appropriate writer, and writes a human-readable text report.
    """
    config = load_config(Path(config_path))
    league = load_league(config_path)
    history = NonConfHistory.load(history_path)
    writer = get_writer(output_format, output)

    started = time.perf_counter()
    result = get_scheduler(scheduler)(
        league=league,
        history=history,
        season=season,
        seed=seed,
        time_limit=time_limit if time_limit is not None else config.time_limit,
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
