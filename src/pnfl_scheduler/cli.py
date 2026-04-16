from __future__ import annotations

import argparse
import random
import time
from collections.abc import Sequence
from pathlib import Path

from .html_writer import HtmlScheduleWriter
from .txt_schedule_writer import TxtScheduleWriter
from .config import find_config_path, load_config
from .history import NonConfHistory
from .report import TxtReportWriter, build_schedule_report
from .run import generate_schedule
from .run import DEFAULT_HISTORY_PATH


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
        "--history",
        type=Path,
        default=None,
        help="Path to the non-conference history JSON file.",
    )
    parser.add_argument(
        "--txt-report",
        type=Path,
        default=None,
        help="Optional override path for the human-readable text report. Defaults to <output-stem>-report.txt.",
    )
    parser.add_argument(
        "--time-limit",
        type=float,
        default=None,
        help="Override the configured solver time limit in seconds.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    writer = _resolve_writer(parser, args.output, args.format)
    report_path = args.txt_report or _default_report_path(args.output)
    config_path = args.config or find_config_path()
    history_path = args.history or DEFAULT_HISTORY_PATH
    config = load_config(config_path)
    history = NonConfHistory.load(history_path)
    seed = random.randint(0, 1_000_000)
    started_at = time.perf_counter()
    schedule = generate_schedule(
        seed=seed,
        time_limit=args.time_limit,
        config=config,
        history=history,
        writer=writer,
    )
    elapsed_time_seconds = time.perf_counter() - started_at
    report = build_schedule_report(
        schedule=schedule,
        conference_ranking=config.ConferenceRanking,
        history=history,
        seed=seed,
        scheduler_kind="two-phase",
        config_path=config_path,
        history_path=history_path,
        elapsed_time_seconds=elapsed_time_seconds,
    )
    TxtReportWriter(report_path).write(report)
    print(f"Generated {len(schedule.games)} games -> {args.output}; report -> {report_path} (seed {seed})")
    return 0
