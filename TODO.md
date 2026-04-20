# TODO

- Replace the extra AFC East vs NFC East rank step and final H2H step in
  `two-phase` with one joint solve over the remaining 13 non-conference games.
- Revisit `NEVER_PLAYED_COST_BONUS` after more H2H backtesting.
- For `two-phase-rank`, consider replacing the strict hardest-to-easiest rank
  ladder with a compressed "bell curve" target so middle-ranked teams stay near
  average non-conference difficulty and the top/bottom teams are only somewhat
  harder/easier, not maximally extreme.
- For `two-phase-rank`, consider guardrails on non-conference difficulty such
  as a spread cap between the hardest/easiest slates or mix constraints that
  keep teams from drawing all-top or all-bottom opponents.
- Decide on final scheduler
- Move \_ScheduleModel to separate module?
