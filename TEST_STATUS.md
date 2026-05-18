# pnfl-scheduler — Test Status

**Test Status: More Tests Needed**

## Covered by automated tests

- CLI argument parsing and error handling for missing/invalid output, season, and config.
- Config loading and validation: time limit, division/ranking sections, invalid INI and league data.
- Phase-one matchup inventory for both the `fixed-matchup` and rank-only builders.
- Two-phase schedule structure and constraint compliance (game counts, home/away balance, divisional density and placement rules).
- History-driven non-conference pair cost calculation.
- Report row generation and the HTML/text writers and writer registry.

## Needs tests

- End-to-end run of `cli.main()` producing non-empty schedule and report files.
