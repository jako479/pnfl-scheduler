# How It Builds The Schedule

## Phase 1

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

## Phase 2

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
