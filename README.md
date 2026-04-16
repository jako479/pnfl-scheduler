# pnfl-scheduler

Generates PNFL schedules.

This repo contains three scheduler implementations:

- `scheduler_two_phase.py`
  Current default. Phase I builds the opponent inventory; Phase II places it with CP-SAT.
- `scheduler_history.py`
  Legacy history-aware scheduler.
- `scheduler.py`
  Original one-phase scheduler.

The package-level runner, CLI, and default pytest path use the two-phase scheduler.

## Setup

```powershell
py -3.13 -m venv .venv
.venv\Scripts\activate
py -m pip install -e ".[dev]"
```

`ortools` is a required runtime dependency.

## Config

The default runner reads `generate-schedule.ini` or `generate-schedule.dev.ini`
from the working directory or `config/`.

The config currently provides:

- solver settings
- conference ranking input for the two-phase scheduler

Legacy schedulers do not read that file directly; they take their lower-level
inputs through their Python APIs.

## CLI

The CLI requires a main output path:

```powershell
pnfl-scheduler --output season.html
pnfl-scheduler --output season.txt
pnfl-scheduler --output season.out --format html
pnfl-scheduler --output season.out --format txt
pnfl-scheduler --output season.out --format txt --txt-report schedule-report.txt
```

The writer is chosen from `--format` if provided, otherwise from the output
file extension.

A text report is also written by default:

- `season.html` -> `season-report.txt`
- `season.txt` -> `season-report.txt`

Use `--txt-report` only to override that report path.

## Library Usage

Default runner:

```python
from pnfl_scheduler import generate_schedule

schedule = generate_schedule()
```

Low-level two-phase entry point:

```python
from pnfl_scheduler.scheduler_two_phase import solve_schedule
```

## Testing

```powershell
pytest
pytest tests/unit/test_two_phase_inventory.py
pytest tests/test_two_phase_schedule_rules.py
pytest --history
pytest --no-history
pytest --all-configs
```
