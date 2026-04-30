"""Writer protocol and registry of schedule writers, keyed by output-format extension."""

from __future__ import annotations

from collections.abc import Callable
from os import PathLike
from typing import Protocol

from pnfl_scheduler.domain.schedule import Schedule
from pnfl_scheduler.writers.html_writer import HtmlScheduleWriter
from pnfl_scheduler.writers.txt_writer import TxtScheduleWriter

StrPath = str | PathLike[str]


class ScheduleWriter(Protocol):
    """Output boundary for persisting or exporting a generated schedule."""

    def write(self, schedule: Schedule) -> None: ...


WriterFactory = Callable[[StrPath], ScheduleWriter]

WRITERS: dict[str, WriterFactory] = {
    "html": HtmlScheduleWriter,
    "htm": HtmlScheduleWriter,
    "txt": TxtScheduleWriter,
}


def available_writer_formats() -> tuple[str, ...]:
    """Return the file-extension tokens callers may pass to `get_writer`."""
    return tuple(sorted(set(WRITERS)))


def get_writer(fmt: str, output: StrPath) -> ScheduleWriter:
    """Return a writer for `fmt` bound to `output`. Raises ValueError if unsupported."""
    try:
        factory = WRITERS[fmt.lower()]
    except KeyError as exc:
        choices = ", ".join(available_writer_formats())
        raise ValueError(f"Unsupported output format {fmt!r}. Available: {choices}") from exc
    return factory(output)
