# pnfl-scheduler — Status

**Status: In Progress**

CLI tool that generates a PNFL season schedule using OR-Tools constraint programming and writes it as HTML or text alongside a human-readable report.

## Implemented

- `generate-schedule` CLI with config discovery, season/output/format/seed/time-limit flags, and registered scheduler selection.
- INI config loading with strict validation of league structure, conference rankings, and rule weights.
- Non-conference history loading used to penalize recent inter-conference matchups.
- Two two-phase schedulers — `fixed-matchup` (default) and `two-phase-rank` — that build a matchup inventory and then assign matchups to weeks.
- HTML and text schedule writers selected by `--format` or output extension, plus a companion text report.

## Remaining

- Decide on the final scheduler and consolidate the scattered scheduler notes.
- Refine `two-phase-rank` non-conference difficulty (bell-curve target, spread caps, mix guardrails).
- Replace the `fixed-matchup` extra East and final H2H steps with a single joint non-conference solve.
- Add an end-to-end CLI integration test and automate `pytest` via pre-commit or GitHub Actions.
- Consider switching config handling to Pydantic.
