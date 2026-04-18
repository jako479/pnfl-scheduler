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

## How It Builds The Schedule

The scheduler works in 2 phases:

- Phase 1 builds the opponent inventory.
- Phase 2 places that inventory into weeks and assigns home/away while enforcing
  the schedule rules.

Opponent inventory comes from these sources:

- Divisional games: every divisional opponent twice.
- Conference games: every same-conference opponent outside the division once.
- Non-conference fixed games: 3 opponents from the conference ranking table.
- Extra 4-team-division game: one AFC East vs NFC East pairing chosen by closest
  rank gap, skipping fixed pairs.
- Final H2H game: one remaining AFC vs NFC pairing chosen from non-conference
  history plus pseudo-inverse rank cost. The final pairing targets
  `1v6, 2v7, 3v8, 4v9, 5v5, 6v1, 7v2, 8v3, 9v4`, with H2H weighted at
  `1.6x` the inverse-rank term.

That gives 5 non-conference games for 4-team divisions and 4 non-conference
games for 5-team divisions.

## CLI

```powershell
pnfl-scheduler --output season.html --season 2026
pnfl-scheduler --output season.txt --season 2026
pnfl-scheduler --output season.html --season 2026 --seed 123456
pnfl-scheduler --output season.out --format html --season 2026
pnfl-scheduler --output season.out --format txt --season 2026
pnfl-scheduler --output season.html --season 2026 --txt-report season-report.txt
```

If the console script is not available in the active environment, use:

```powershell
python -m pnfl_scheduler.app.cli --output season.html --season 2026
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
