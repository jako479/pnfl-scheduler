# Non-Conference Matchup History

`nonconf_history*.json` files track the last season each non-conference pair played, used by the scheduler to space out rematches.

> **Note:** Only `nonconf_history.json` is up-to-date with the current convention. The year-suffixed files still use `null` for pairs whose coaches haven't played each other.

## Format

```json
{
  "matchups": {
    "Buffalo|Atlanta": 2046,
    ...
  }
}
```

- Keys are `"AFC metro|NFC metro"`. **AFC teams drive the rows** — every key starts with an AFC team and ends with an NFC team.
- The year is the season the two **coaches** (not the teams) last played each other.

## When coaches haven't played each other

The year recorded is the season _prior to_ the starting season of whichever coach started most recently.

## Coach gaps

A coach's career may have breaks:

- **Short gaps (1–4 years)** are ignored — treat the coach as continuous.
- **Long gaps (5+ years)** — use the season prior to the coach's most recent start season.
