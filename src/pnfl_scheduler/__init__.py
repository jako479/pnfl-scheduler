"""pnfl-scheduler package."""

from .app.run import generate_schedule
from .output.html_writer import HtmlScheduleWriter
from .output.report import TxtReportWriter
from .output.txt_schedule_writer import TxtScheduleWriter
from .output.writer import ScheduleWriter


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
