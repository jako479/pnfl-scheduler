# pnfl-scheduler

Generates PNFL schedules with the current two-phase OR-Tools scheduler.

The repo keeps scheduler-selection plumbing in place so another scheduler can be
added later, but only the two-phase scheduler is currently implemented.

Package layout:

- `pnfl_scheduler.app`
  CLI, config loading, and top-level run plumbing.
- `pnfl_scheduler.domain`
  Teams, schedule data structures, and non-conference history data.
- `pnfl_scheduler.output`
  HTML, text schedule, and text report writers.
- `pnfl_scheduler.schedulers`
  Scheduler registry and the current two-phase scheduler.

## Setup

```powershell
py -3.13 -m venv .venv
.venv\Scripts\activate
py -m pip install -e ".[dev]"
```

`ortools` is required at runtime.

## Config

The app reads `generate-schedule.ini` or `generate-schedule.dev.ini` from the
working directory or `config/`. That file controls solver settings and the
conference ranking input used by the scheduler.

## CLI

```powershell
pnfl-scheduler --output season.html
pnfl-scheduler --output season.txt
pnfl-scheduler --output season.out --format html
pnfl-scheduler --output season.out --format txt
pnfl-scheduler --output season.html --txt-report season-report.txt
```

If the console script is not available in the active environment, use:

```powershell
python -m pnfl_scheduler.app.cli --output season.html
```

The schedule writer is chosen from `--format` when provided, otherwise from the
output file extension.

A text report is written by default alongside the main output:

- `season.html` -> `season-report.txt`
- `season.txt` -> `season-report.txt`

Use `--txt-report` only to override that default report path.

## Library Usage

```python
from pnfl_scheduler import generate_schedule

schedule = generate_schedule()
```

## Testing

```powershell
pytest
pytest tests/unit/test_two_phase_inventory.py
pytest tests/test_two_phase_schedule_rules.py
pytest --all-configs
```
