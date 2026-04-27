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
pnfl generate-schedule --output season.txt --season 2026
pnfl generate-schedule --scheduler two-phase-rank --output season.html --season 2026
pnfl generate-schedule --output season.html --season 2026 --seed 123456
pnfl generate-schedule --output season.out --format html --season 2026
pnfl generate-schedule --output season.out --format txt --season 2026
pnfl generate-schedule --output season.html --report season-report.txt --season 2026
```

The schedule writer is chosen from `--format` when provided, otherwise from the
output file extension.

Use `--scheduler` to choose the scheduling model:

- `fixed-matchup` is the default
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
working directory or a `config/` subdirectory of the working directory, via
`Path.cwd()` lookups. Pass `--config /path/to/file.ini` to override.

Relevant `.ini` sections:

- `[Settings]` — solver settings (`TimeLimit`).
- `[Divisions]` — current season's division membership.
- `[ConferenceRanking]` — current season's prior-year standings input.

Config loading is split across two functions in `pnfl_scheduler.config`:

- `load_settings(path) -> Settings` — reads `[Settings]`.
- `load_league(path) -> League` — reads `[Divisions]` + `[ConferenceRanking]`,
  delegates to `pnfl_scheduler.domain.league.build_league` for domain
  validation, and returns a fully-constructed `League` object (teams +
  `ConferenceRankings`).

Historical `YYYY` sections that may exist in `generate-schedule.dev.ini` are
temporary analysis/backtesting inputs and are not used by the normal runtime
CLI path.

## How It Builds The Schedule

Both current schedulers work in 2 phases:

- Phase 1 builds the opponent inventory.
- Phase 2 places that inventory into weeks and assigns home/away while enforcing
  the schedule rules.

### Phase 1

Shared inventory pieces for both schedulers:

- Divisional games: every divisional opponent twice.
- Conference games: every same-conference opponent outside the division once.

`fixed-matchup` builds non-conference inventory like this:

- Fixed games: 3 opponents from the fixed rank table (e.g. 1 vs 1, 2, and 3)
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

- `pnfl_scheduler.cli` — argparse CLI entry point (`pnfl generate-schedule` subcommand).
- `pnfl_scheduler.main` — `generate_schedule()` orchestrator that loads config,
  runs the chosen scheduler, and invokes the writers.
- `pnfl_scheduler.config` — `load_settings`, `load_league`, and `find_config_path`.
- `pnfl_scheduler.domain`
  Teams, the `League` aggregate (with `ConferenceRankings`), schedule data
  structures, and non-conference history. Domain types have no knowledge of
  config files. `domain.league.build_league` performs all semantic validation
  (ranking size/coverage, cross-conference reuse, consistency with divisions).
- `pnfl_scheduler.writers`
  HTML, text schedule, and text report writers.
- `pnfl_scheduler.schedulers`
  Scheduler registry and the current scheduler implementations. Schedulers
  accept a pre-validated `League` and populate the non-conference pair
  categories on `MatchupPlan` directly — the report reads them as data rather
  than recomputing.

## Testing

```powershell
pytest
pytest tests/unit/test_history_costs.py -v -x -vv --all-configs
pytest tests/unit/test_two_phase_inventory.py
pytest tests/test_two_phase_schedule_rules.py
pytest --all-configs
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
