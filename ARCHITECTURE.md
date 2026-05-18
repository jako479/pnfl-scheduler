# pnfl-scheduler — Architecture

CLI tool that generates a PNFL season schedule using OR-Tools constraint programming, writes the result in the requested format (HTML or TXT), and emits a companion human-readable report.

## Module layout

```
src/pnfl_scheduler/
├── __init__.py
├── cli.py                          # argparse + main()
├── main.py                         # generate_schedule() orchestration
├── config.py                       # Config dataclass, load_config(), load_league()
├── domain/
│   ├── league.py                   # League, Conference, Division, Team
│   ├── schedule.py                 # Schedule, Game, Week
│   └── history.py                  # NonConfHistory — past inter-conference matchups
├── schedulers/
│   ├── scheduler.py                # single-phase OR-Tools scheduler
│   ├── schedule_builder.py         # CP-SAT model + constraints
│   ├── matchup_builder.py          # opponent-set generation
│   ├── fixed_matchup_scheduler.py  # two-phase scheduler (matchups → weeks)
│   ├── fixed_matchup_builder.py    # phase-one matchup solver
│   ├── types.py                    # Scheduler protocol, SchedulerResult, registry
│   └── errors.py
└── writers/
    ├── writer.py                   # ScheduleWriter protocol + factory
    ├── html_writer.py              # HTML output
    ├── txt_writer.py               # plain-text output
    └── report.py                   # TxtReportWriter + build_schedule_report
```

## What this package does

- Provides a CLI: `pnfl generate-schedule --output FILE --season YEAR [--scheduler NAME] [--config FILE] [--history FILE] [--report FILE] [--seed INT] [--time-limit SECONDS]`
- Loads league structure (conferences, divisions, teams) and rule weights from an INI config
- Loads the non-conference history file (past inter-conference pairings to penalize / avoid)
- Solves the schedule with a registered scheduler (`fixed-matchup` default, or `two-phase-rank`)
- Writes the schedule in the format inferred from the output extension (`.html` → HTML; `.txt` → text)
- Writes a companion `<output-stem>-report.txt` summarizing the run (matchup plan, constraint slack, seed, elapsed time, command line)

## What this package assumes

- The history file is consistent with the league structure (every team referenced is a known team)
- The selected scheduler can solve within `time-limit`; if not, the partial / infeasible result surfaces via `SchedulerResult`

## What this package enforces

CLI-level (raise SystemExit via argparse):
- `--output` and `--season` provided
- `--output` extension is `.html` or `.txt`
- `--scheduler` is one of the registered names

Config (raise `ConfigError`):
- A config file is required — no discoverable file and no `--config` is an error; an explicit `--config` path must exist
- The `[Divisions]` and `[ConferenceRanking]` sections, and the `AFC`/`NFC` rankings, are required
- `TimeLimit` is optional and falls back to its default; a present-but-invalid value is an error
- Invalid INI, or league data that fails domain validation, surfaces as a `ConfigError`

Domain (raise `ValueError`):
- Each conference has the expected number of divisions; each division the expected number of teams
- League invariants (e.g., team count, division balance) are validated at load time

Solver (`SchedulerResult.feasible == False`):
- Infeasible models surface a structured failure rather than a crash; the writer is skipped and the report records why

## What this package does NOT do

- Persist league or history changes — both inputs are read-only
- Produce stat workbooks (lives in `pnfl-pdbtoexcel`) or play catalogs (lives in `pnfl-playcatalog`)
- Run the generated schedule against any game engine

## Scheduler dispatch

Schedulers register themselves in `schedulers/types.py` so the CLI can list and select by name. The two flavors today:

- `fixed-matchup` (default) — phase one builds the matchup inventory from divisional/conference rules, a fixed non-conference rank table, and history; phase two assigns each matchup to a week.
- `two-phase-rank` — phase one selects all non-conference matchups with a rank-only CP-SAT model that gives higher-ranked teams harder slates; phase two assigns weeks.

Both are two-phase, implement the `Scheduler` protocol, and return a `SchedulerResult` with the schedule and the matchup plan.

## Testing

- `tests/test_cli.py` / `test_config.py` — CLI parsing, config loading and validation
- `tests/test_schedule_structure.py` — schedule shape (game count, week count)
- `tests/test_two_phase_schedule_rules.py` — schedule constraint compliance
- `tests/test_two_phase_inventory.py` / `test_matchup_builder.py` — phase-one matchup inventory for both builders
- `tests/test_history_costs.py` — history-driven non-conference pair penalties
- `tests/test_report.py` — report row generation
- `tests/test_writers.py` — text/HTML writers and the writer registry

Heavy schedule-solve tests run against one config by default; pass `--all-configs` to run all three. The non-conference history snapshot lives in `tests/fixtures/`.
