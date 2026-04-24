"""Two-phase PNFL scheduler with rank-only non-conference selection.

Phase 1 builds the full opponent inventory before any week placement:
divisional home-and-homes, same-conference cross-division games, then all 40
non-conference games are selected together by a single rank-only CP-SAT model.
That model assigns 5 non-conference games to teams in the four-team divisions
and 4 non-conference games to teams in the five-team divisions while forcing
the conference rank ordering of schedule strength.

Phase 2 uses CP-SAT to place that full inventory into the calendar while keeping the
existing weekly/home-away sequencing constraints.

Schedule requirements enforced by this scheduler:

Basic schedule structure and inventory requirements:
- Each team plays 16 total games, exactly 1 in each week.
- Each team hosts exactly 8 games.
- No pair of teams may play each other in back-to-back weeks.

Home/away sequencing requirements:
- No 4 straight home or away games.
- At most 1 total 3-game home/away streak per team.
- No 3-game home/away streak to start or end the season.
- Every 6-game span must contain between 2 and 4 home games.

Divisional scheduling requirements:
- Each team plays every divisional opponent twice, once at home and once away.
- No 4 straight divisional games.
- Either 0 teams or exactly 2 teams may open the season with back-to-back divisional games.
- No 3 straight divisional games to start or end the season.
- At most 1 total 3-game divisional streak per team.
- 5-team divisions: max 7 divisional games in any 10-game span and no 7 in any 9-game span.
- 4-team divisions: max 5 divisional games in any 8-game span and no 4 in any 7-game span.
- At least half of each team's divisional games must occur in the second half of the season.
- At most 2 divisional opponents may be non-interleaved between a team's 2 meetings with that rival.
- Every team must play at least 1 divisional game in the final 2 weeks.
- Week 16 must contain exactly 8 divisional games.

Conference scheduling requirements:
- Each team plays every same-conference opponent outside its division exactly once.
- Conference home balance:
  - 5-team division teams host exactly 2 of 4.
  - In each 4-team division, the 5 conference games split 2, 2, 3, 3 across the 4 teams.

Non-conference scheduling requirements:
- After divisional and same-conference games are assigned, the remaining schedule slots are
  non-conference games.
- 5-team division teams play 4 non-conference games.
- 4-team division teams play 5 non-conference games.
- Non-conference home balance:
  - 5-team division teams host exactly 2 of 4.
  - In each 4-team division, the 5 non-conference games split 2, 2, 3, 3 across the 4 teams.

NFL guideposts based on 5-team division data from 1999-2001 and 4-team division data
from 2016-2025:

Home/away:
- 3-game home/away streaks are common, so the model allows them but prevents multiple for any 1 team.
- 3-game home/away streaks at the start or end of the season are very rare, so the model forbids them.
- 5-of-6 home/away windows are rare, so every 6-game span is capped at 4 home or away games. However,
  common to have 4 in a 5-game span, so that's allowed.

Divisional:
- Modern NFL averages 3.4 teams/season open the season with back-to-back divisional games, and it's
  exceptionally rare for just 1 team, so allows at most 1 pair of teams to open the season with
  back-to-back divisional games.
- 3 straight divisional games are common, so the model allows them but prevents multiple for any 1 team.
- 3 straight divisional games at the start or end of the season are rare, so the model forbids them.
- For 5-team divisions, very rare to have 8 div games in a 10-game span, so capping at 7 in 10 games
  and preventing 7 in 9 games.
- For 4-team divisions, very rare to have all 6 div games in an 8-game span, so capping at 5 in 8 games
  and preventing 4 in 7 games.
- Modern NFL tries to back-load divisional games to the last half of the season, so at least
  half of each team's divisional games must occur in the second half of the season.

PNFL policy choices layered on top of those guideposts:
- All teams have at least one divisional game in the final two weeks.
- Week 16 is forced to have 8 divisional games (the most possible) and a single non-conference game.
"""

from __future__ import annotations

from pnfl_scheduler.domain.history import NonConfHistory
from pnfl_scheduler.domain.league import League
from pnfl_scheduler.schedulers.errors import SchedulerError
from pnfl_scheduler.schedulers.matchup_builder import MatchupBuilder
from pnfl_scheduler.schedulers.schedule_builder import ScheduleBuilder
from pnfl_scheduler.schedulers.types import SchedulerResult


def generate_schedule(
    league: League,
    history: NonConfHistory,
    season: int,
    seed: int = 0,
    time_limit: float = 900.0,
) -> SchedulerResult:
    """Build matchups, then build the final schedule."""
    matchup_plan = MatchupBuilder(
        teams=league.teams,
        rankings=league.rankings,
        history=history,
        season=season,
    ).build_matchup_plan()

    schedule_builder = ScheduleBuilder(teams=league.teams, error_cls=SchedulerError)
    schedule = schedule_builder.build_schedule(
        matchups=matchup_plan.matchups,
        seed=seed,
        time_limit=time_limit,
    )
    return SchedulerResult(schedule=schedule, matchup_plan=matchup_plan)
