from __future__ import annotations

from typing import Protocol

from .schedule import Schedule


class ScheduleWriter(Protocol):
    """Output boundary for persisting or exporting a generated schedule."""

    def write(self, schedule: Schedule) -> None:
        ...
