"""pnfl-scheduler package."""

from .html_writer import HtmlScheduleWriter
from .report import TxtReportWriter
from .run import generate_schedule
from .txt_schedule_writer import TxtScheduleWriter
from .writer import ScheduleWriter


def main(argv=None):
    from .cli import main as _main

    return _main(argv)


__all__ = [
    "main",
    "generate_schedule",
    "ScheduleWriter",
    "HtmlScheduleWriter",
    "TxtScheduleWriter",
    "TxtReportWriter",
]
