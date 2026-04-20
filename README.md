# pnfl-scheduler

Generates PNFL schedules with OR-Tools.

## Current Models

Two scheduler implementations are currently available:

- `two-phase`
  Baseline two-phase scheduler. Phase 1 builds the opponent inventory from
  divisional games, conference games, a fixed non-conference rank table, one
  extra AFC East vs NFC East rank-based pairing, and one final history-based
  AFC vs NFC pairing that also uses pseudo-inverse rank cost. The H2H term is
  gap-based from the current season, with never-played matchups scoring below
  the oldest played matchup.
- `two-phase-rank`
  Variant of the two-phase scheduler that keeps the same phase-2 placement
  model, but replaces phase-1 non-conference selection with a rank-only CP-SAT
  model. That model chooses all 40 non-conference games together and enforces
  harder non-conference schedules for higher-ranked teams.

## CLI

```powershell
pnfl-scheduler --output season.html --season 2026
pnfl-scheduler --output season.txt --season 2026
pnfl-scheduler --output season.html --season 2026 --scheduler two-phase-rank
pnfl-scheduler --output season.html --season 2026 --seed 123456
pnfl-scheduler --output season.out --format html --season 2026
pnfl-scheduler --output season.out --format txt --season 2026
pnfl-scheduler --output season.html --season 2026 --report season-report.txt
```

If the console script is not available in the active environment, use:

```powershell
python -m pnfl_scheduler.app.cli --output season.html --season 2026
```

The schedule writer is chosen from `--format` when provided, otherwise from the
output file extension.

Use `--scheduler` to choose the scheduling model:

- `two-phase` is the default
- `two-phase-rank` uses the rank-only non-conference inventory builder

A text report is written by default alongside the main output:

- `season.html` -> `season-report.txt`
- `season.txt` -> `season-report.txt`

Use `--report` only to override that default report path.

## Setup

```powershell
py -3.13 -m venv .venv
.venv\Scripts\activate
py -m pip install -e ".[dev]"
```

`ortools` is required at runtime.

## Config

The app reads `generate-schedule.ini` or `generate-schedule.dev.ini` from the
working directory or `config/`. That file controls solver settings, the season's
division alignment, and the prior season's conference rankings.

Use:

- `[Divisions]` for the current season's division membership
- `[ConferenceRanking]` for the current season's prior-year standings input

Historical `YYYY` sections that may exist in `generate-schedule.dev.ini` are
temporary analysis/backtesting inputs and are not used by the normal runtime
CLI path.

## Library Usage

```python
from pnfl_scheduler import generate_schedule

schedule = generate_schedule(season=2026)
```

## How It Builds The Schedule

Both current schedulers work in 2 phases:

- Phase 1 builds the opponent inventory.
- Phase 2 places that inventory into weeks and assigns home/away while enforcing
  the schedule rules.

### Phase 1

Shared inventory pieces for both schedulers:

- Divisional games: every divisional opponent twice.
- Conference games: every same-conference opponent outside the division once.

`two-phase` builds non-conference inventory like this:

- Fixed games: 3 opponents from the conference ranking table.
- Extra 4-team-division game: one AFC East vs NFC East pairing chosen by
  closest rank gap, skipping fixed pairs.
- Final H2H game: one remaining AFC vs NFC pairing chosen from non-conference
  history plus pseudo-inverse rank cost. The final pairing targets
  `1v6, 2v7, 3v8, 4v9, 5v5, 6v1, 7v2, 8v3, 9v4`. History uses actual gap from
  the scheduled season (`last season = 0`, older matchups go lower, and
  never-played is lower than the oldest played matchup), with H2H weighted at
  `1.0x` the inverse-rank term.

`two-phase-rank` builds non-conference inventory differently:

- All 40 AFC vs NFC games are chosen together in one CP-SAT model.
- Teams in 4-team divisions get 5 non-conference games; teams in 5-team
  divisions get 4.
- Higher-ranked teams are forced toward harder non-conference opponent sets, and
  lower-ranked teams toward easier ones.
- Each team must draw at least one opponent from the top half of the other
  conference ranking and at least one from the bottom half.

Both models still end phase 1 with the same schedule shape:

- 5 non-conference games for 4-team divisions.
- 4 non-conference games for 5-team divisions.
- 144 total pairings in the full season inventory.

### Phase 2

Phase 2 is the same for both current schedulers. It takes the fixed phase-1
inventory and uses CP-SAT to assign each matchup to a week and home/away slot.

Phase 2 enforces the full placement rules, including:

- each team plays exactly once per week and hosts exactly 8 games
- no back-to-back meetings between the same two teams
- divisional, conference, and non-conference home-balance rules
- home/away streak limits and 6-game home/away window balance
- divisional streak and density limits
- back-loaded divisional scheduling in the second half
- limits on non-interleaved divisional pairings
- Week 16 containing exactly 8 divisional games
- every team playing at least one divisional game in the final 2 weeks

## Package Layout

- `pnfl_scheduler.app`
  CLI, config loading, and top-level run plumbing.
- `pnfl_scheduler.domain`
  Teams, schedule data structures, and non-conference history data.
- `pnfl_scheduler.output`
  HTML, text schedule, and text report writers.
- `pnfl_scheduler.schedulers`
  Scheduler registry and the current scheduler implementations.

## Testing

```powershell
pytest
pytest tests/unit/test_two_phase_inventory.py
pytest tests/test_two_phase_schedule_rules.py
pytest --all-configs
```

## Legacy Models

Two older schedulers existed before the current two-phase implementation:

- `scheduler.py`
  Original one-phase model. A single CP-SAT solve chose non-conference
  opponents, home/away, and weekly placement at the same time. Its
  non-conference strength-of-schedule rules were based on playoff buckets:
  division winners, wild cards, and ranked non-playoff teams.
- `scheduler_history.py`
  Clone of the original one-phase model with one added history step. Before the
  main CP-SAT solve, OR-Tools `LinearSumAssignment` picked 9 forced AFC/NFC
  pairings based on the most overdue non-conference matchups, while excluding
  pairs already implied by the playoff-based SOS rules.
