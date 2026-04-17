"""pnfl-scheduler package."""

from .app.run import generate_schedule
from .writers.html_writer import HtmlScheduleWriter
from .writers.report import TxtReportWriter
from .writers.txt_schedule_writer import TxtScheduleWriter
from .writers.writer import ScheduleWriter


def main(argv=None):
    from .app.cli import main as _main

    return _main(argv)


__all__ = [
    "main",
    "generate_schedule",
    "ScheduleWriter",
    "HtmlScheduleWriter",
    "TxtScheduleWriter",
    "TxtReportWriter",
]
