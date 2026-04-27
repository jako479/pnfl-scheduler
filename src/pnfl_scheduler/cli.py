from __future__ import annotations

import argparse
import random
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from pnfl_scheduler.config import find_config_path
from pnfl_scheduler.main import DEFAULT_HISTORY_PATH, generate_schedule
from pnfl_scheduler.schedulers import DEFAULT_SCHEDULER, available_schedulers
from pnfl_scheduler.writers import available_writer_formats


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pnfl generate-schedule",
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
        choices=available_writer_formats(),
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


def _default_report_path(output: Path) -> Path:
    return output.with_name(f"{output.stem}-report.txt")


def _command_line(argv: Sequence[str] | None, prog: str) -> str:
    if argv is None:
        return subprocess.list2cmdline([prog, *sys.argv[1:]])
    return subprocess.list2cmdline([prog, *argv])


def _infer_format(parser: argparse.ArgumentParser, output: Path, output_format: str | None) -> str:
    fmt = (output_format or output.suffix.lstrip(".")).lower()
    if not fmt:
        parser.error("Could not infer output format from file extension; use --format.")
    if fmt not in available_writer_formats():
        parser.error(f"Unsupported output format: {fmt}")
    return fmt


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    fmt = _infer_format(parser, args.output, args.format)
    config_path = args.config or find_config_path()
    history_path = args.history or DEFAULT_HISTORY_PATH
    report_path = args.report or _default_report_path(args.output)
    seed = args.seed if args.seed is not None else random.randint(0, 1_000_000)

    generate_schedule(
        output=args.output,
        output_format=fmt,
        season=args.season,
        scheduler=args.scheduler,
        config_path=config_path,
        history_path=history_path,
        report_path=report_path,
        seed=seed,
        time_limit=args.time_limit,
        command_line=_command_line(argv, parser.prog),
    )
    return 0
