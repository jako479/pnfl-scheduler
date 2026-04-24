"""Schedule export and report writers."""

from collections.abc import Callable
from pathlib import Path

from pnfl_scheduler.writers.html_writer import HtmlScheduleWriter
from pnfl_scheduler.writers.txt_writer import TxtScheduleWriter
from pnfl_scheduler.writers.writer import ScheduleWriter

WriterFactory = Callable[[Path | str], ScheduleWriter]

WRITERS: dict[str, WriterFactory] = {
    "html": HtmlScheduleWriter,
    "htm": HtmlScheduleWriter,
    "txt": TxtScheduleWriter,
}


def available_writer_formats() -> tuple[str, ...]:
    return tuple(sorted(set(WRITERS)))


def get_writer(fmt: str, output: Path) -> ScheduleWriter:
    try:
        factory = WRITERS[fmt.lower()]
    except KeyError as exc:
        choices = ", ".join(available_writer_formats())
        raise ValueError(f"Unsupported output format {fmt!r}. Available: {choices}") from exc
    return factory(output)
