# TODO

- Remove legacy schedulers
- Improve two-phase scheduler to integrate SOS in with H2H matchup determinination.
  Currently, bad teams can end up with super difficult schedules, and vice-versa.
- Add another scheduler based on an exact copy of scheduler_two_phase.py that
  fully-utilizes SOS algorithm rather than a fixed-matchup table for SOS.
