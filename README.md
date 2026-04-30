# pnfl-scheduler

Generates PNFL schedules with OR-Tools.

## Current Models

Two scheduler implementations are currently available. Both use the same
two-phase structure:

- Phase 1 builds the matchup inventory.
- Phase 2 builds the actual schedule from that matchup inventory.

Phase 1 differs by scheduler:

- `fixed-matchup`
  Builds the opponent inventory from divisional games, conference games,
  a fixed non-conference rank table, one extra AFC East vs NFC East rank-based
  pairing, and one final history-based AFC vs NFC pairing that uses pseudo-
  inverse rank cost and H2H history.
- `two-phase-rank`
  Replaces phase-1 non-conference selection with a rank-only CP-SAT model.
  That model chooses all 40 non-conference games together and enforces harder
  non-conference schedules for higher-ranked teams.

For both schedulers, H2H history lowers the cost of never-played and
long-unplayed matchups, with costs increasing as matchups become more recent.

## CLI

```powershell
pnfl generate-schedule --output season.html --season 2026
pnfl generate-schedule --scheduler two-phase-rank --output season.html --season 2026
```

The schedule writer is chosen from `--format` when provided, otherwise from
the output file extension. A text report is written by default alongside the
main output (`season.html` -> `season-report.txt`); use `--report` to override.

## Setup

```powershell
py -3.13 -m venv .venv
.venv\Scripts\activate
py -m pip install -e ".[dev]"
```

`ortools` is required at runtime.

## Config

Reads `generate-schedule.ini` from the working directory or a `config/`
subdirectory. Pass `--config /path/to/file.ini` to override. See
[`config/generate-schedule.ini`](config/generate-schedule.ini) for the full
list of settings.

## Testing

```powershell
pytest
pytest --all-configs
pytest tests/test_history_costs.py -v -x -vv --all-configs
```

## Legacy Models

Two older schedulers existed before the current two-phase implementations.
Neither lives in the codebase anymore — they are documented here for
historical context only. Note the filename collision: the current
`schedulers/scheduler.py` is the live two-phase-rank entrypoint, not the
legacy one described below.

- `scheduler.py` (legacy, removed)
  Original one-phase model. A single CP-SAT solve chose non-conference
  opponents, home/away, and weekly placement at the same time. Its
  non-conference strength-of-schedule rules were based on playoff buckets:
  division winners, wild cards, and ranked non-playoff teams.
- `scheduler_history.py` (legacy, removed)
  Clone of the original one-phase model with one added history step. Before the
  main CP-SAT solve, OR-Tools `LinearSumAssignment` picked 9 forced AFC/NFC
  pairings based on the most overdue non-conference matchups, while excluding
  pairs already implied by the playoff-based SOS rules.
