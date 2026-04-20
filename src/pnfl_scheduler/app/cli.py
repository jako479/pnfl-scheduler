from __future__ import annotations

import argparse
import random
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from .config import find_config_path, load_config
from .run import DEFAULT_HISTORY_PATH, generate_schedule
from ..domain.history import NonConfHistory
from ..writers.html_writer import HtmlScheduleWriter
from ..writers.report import TxtReportWriter, build_schedule_report
from ..writers.txt_schedule_writer import TxtScheduleWriter
from ..schedulers import DEFAULT_SCHEDULER, available_schedulers


def _resolve_writer(parser: argparse.ArgumentParser, output: Path, output_format: str | None):
    fmt = output_format.lower() if output_format is not None else output.suffix.lower().lstrip(".")
    if fmt == "":
        parser.error("Could not infer output format from file extension; use --format.")
    if fmt in {"html", "htm"}:
        return HtmlScheduleWriter(output)
    if fmt == "txt":
        return TxtScheduleWriter(output)
    parser.error(f"Unsupported output format: {fmt}")


def _default_report_path(output: Path) -> Path:
    return output.with_name(f"{output.stem}-report.txt")


def _command_line(argv: Sequence[str] | None, prog: str) -> str:
    if argv is None:
        return subprocess.list2cmdline([prog, *sys.argv[1:]])
    return subprocess.list2cmdline([prog, *argv])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pnfl-scheduler",
        description="Generates the seasonal game schedule for the PNFL.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Required output path for the generated schedule.",
    )
    parser.add_argument(
        "--format",
        choices=("html", "txt"),
        default=None,
        help="Optional output format override. Defaults to inferring from --output.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to the generate-schedule.ini file. Defaults to the standard search order.",
    )
    parser.add_argument(
        "--scheduler",
        choices=available_schedulers(),
        default=DEFAULT_SCHEDULER,
        help="Scheduler implementation to run.",
    )
    parser.add_argument(
        "--history",
        type=Path,
        default=None,
        help="Path to the non-conference history JSON file.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        dest="report",
        default=None,
        help="Optional override path for the human-readable text report. Defaults to <output-stem>-report.txt.",
    )
    parser.add_argument(
        "--time-limit",
        type=float,
        default=None,
        help="Override the configured solver time limit in seconds.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional random seed override for deterministic schedule generation.",
    )
    parser.add_argument(
        "--season",
        type=int,
        required=True,
        help="The season year being scheduled (e.g. 2026). Used to compute non-conference matchup drought costs.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command_line = _command_line(argv, parser.prog)
    writer = _resolve_writer(parser, args.output, args.format)
    report_path = args.report or _default_report_path(args.output)
    config_path = args.config or find_config_path()
    history_path = args.history or DEFAULT_HISTORY_PATH
    config = load_config(config_path)
    history = NonConfHistory.load(history_path)
    seed = args.seed if args.seed is not None else random.randint(0, 1_000_000)
    started_at = time.perf_counter()
    schedule = generate_schedule(
        scheduler=args.scheduler,
        seed=seed,
        time_limit=args.time_limit,
        config=config,
        history=history,
        season=args.season,
        writer=writer,
    )
    elapsed_time_seconds = time.perf_counter() - started_at
    report = build_schedule_report(
        schedule=schedule,
        conference_rankings=config.ConferenceRankings,
        history=history,
        seed=seed,
        scheduler_kind=args.scheduler,
        command_line=command_line,
        config_path=config_path,
        history_path=history_path,
        elapsed_time_seconds=elapsed_time_seconds,
    )
    TxtReportWriter(report_path).write(report)
    print(f"Generated {len(schedule.games)} games -> {args.output}; report -> {report_path} (seed {seed})")
    return 0
