"""
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

from collections import Counter
from collections.abc import Sequence

from ortools.sat.python import cp_model

from pnfl_scheduler.config import DEFAULT_TIME_LIMIT
from pnfl_scheduler.domain.league import Team
from pnfl_scheduler.domain.schedule import HOME_GAMES_PER_TEAM, NUM_WEEKS, WEEK_16_DIVISIONAL_GAMES, Game, Schedule
from pnfl_scheduler.schedulers.types import Matchup, Matchups, make_matchup


class ScheduleBuilder:
    """Shared CP-SAT phase-2 placement model for schedulers with fixed matchups."""

    def __init__(self, teams: Sequence[Team], error_cls: type[RuntimeError]) -> None:
        self.model = cp_model.CpModel()
        self.teams = tuple(teams)
        self.error_cls = error_cls

        self.weeks = range(NUM_WEEKS)
        self.home_games_per_team = HOME_GAMES_PER_TEAM

        self.div_opponents: dict[Team, list[Team]] = {}
        for team in self.teams:
            self.div_opponents[team] = [opp for opp in self.teams if opp.division == team.division and opp != team]

        self.four_team_set: set[Team] = {t for t in self.teams if t.division.expected_size == 4}
        self.five_team_set: set[Team] = {t for t in self.teams if t.division.expected_size == 5}

        self.divisional_pairs: list[Matchup] = []
        self.conference_pairs: list[Matchup] = []
        self.non_conference_pairs: list[Matchup] = []
        for idx, team_i in enumerate(self.teams):
            for team_j in self.teams[idx + 1 :]:
                pair = make_matchup(team_i, team_j)
                if team_i.division == team_j.division:
                    self.divisional_pairs.append(pair)
                elif team_i.conference == team_j.conference:
                    self.conference_pairs.append(pair)
                else:
                    self.non_conference_pairs.append(pair)

        self.x: dict[tuple[Team, Team, int], cp_model.IntVar] = {}
        for team_i in self.teams:
            for team_j in self.teams:
                if team_i == team_j:
                    continue
                for w in self.weeks:
                    self.x[team_i, team_j, w] = self.model.new_bool_var(f"x_{team_i.metro}_{team_j.metro}_w{w}")

        self.h: dict[tuple[Team, int], cp_model.IntVar] = {}
        for team_i in self.teams:
            for w in self.weeks:
                self.h[team_i, w] = self.model.new_bool_var(f"h_{team_i.metro}_w{w}")
                self.model.add(self.h[team_i, w] == sum(self.x[team_i, team_j, w] for team_j in self.teams if team_j != team_i))

        self.d: dict[tuple[Team, int], cp_model.IntVar] = {}
        for team_i in self.teams:
            for w in self.weeks:
                self.d[team_i, w] = self.model.new_bool_var(f"d_{team_i.metro}_w{w}")
                self.model.add(
                    self.d[team_i, w] == sum(self.x[team_i, opp, w] + self.x[opp, team_i, w] for opp in self.div_opponents[team_i])
                )

    def _constraint_one_game_per_week(self) -> None:
        # Require each team to play exactly 1 game in each of the 16 weeks.
        for team_i in self.teams:
            for w in self.weeks:
                self.model.add(sum(self.x[team_i, team_j, w] + self.x[team_j, team_i, w] for team_j in self.teams if team_j != team_i) == 1)

    def _constraint_home_balance(self) -> None:
        # Require each team to host exactly 8 home games.
        for team_i in self.teams:
            self.model.add(
                sum(self.x[team_i, team_j, w] for team_j in self.teams if team_j != team_i for w in self.weeks) == self.home_games_per_team
            )

    def _constraint_no_four_straight_home_or_away(self) -> None:
        # Every 4-game window must contain at least 1 home and at least 1 away game.
        for team_i in self.teams:
            for w in range(NUM_WEEKS - 3):
                self.model.add(self.h[team_i, w] + self.h[team_i, w + 1] + self.h[team_i, w + 2] + self.h[team_i, w + 3] <= 3)
            for w in range(NUM_WEEKS - 3):
                self.model.add(self.h[team_i, w] + self.h[team_i, w + 1] + self.h[team_i, w + 2] + self.h[team_i, w + 3] >= 1)

    def _constraint_home_away_balance_in_six_game_windows(self) -> None:
        # Every 6-game window must have between 2 and 4 home games, which also forces 2 to 4 away games.
        for team_i in self.teams:
            for w in range(NUM_WEEKS - 5):
                six_game_home_total = sum(self.h[team_i, w + k] for k in range(6))
                self.model.add(six_game_home_total <= 4)
                self.model.add(six_game_home_total >= 2)

    def _constraint_no_three_game_home_or_away_streak_at_season_start_or_end(self) -> None:
        # The first and last 3 games must each contain at least 1 home and at least 1 away game.
        for team_i in self.teams:
            self.model.add(self.h[team_i, 0] + self.h[team_i, 1] + self.h[team_i, 2] <= 2)
            self.model.add(self.h[team_i, 0] + self.h[team_i, 1] + self.h[team_i, 2] >= 1)
            self.model.add(self.h[team_i, NUM_WEEKS - 3] + self.h[team_i, NUM_WEEKS - 2] + self.h[team_i, NUM_WEEKS - 1] <= 2)
            self.model.add(self.h[team_i, NUM_WEEKS - 3] + self.h[team_i, NUM_WEEKS - 2] + self.h[team_i, NUM_WEEKS - 1] >= 1)

    def _constraint_max_one_total_three_game_home_or_away_streak(self) -> None:
        # Allow at most one 3-game streak total, counting both home and away streaks together.
        for team_i in self.teams:
            streak3h: list[cp_model.IntVar] = []
            for w in range(NUM_WEEKS - 2):
                streak = self.model.new_bool_var(f"s3h_{team_i.metro}_w{w}")
                self.model.add_bool_and([self.h[team_i, w], self.h[team_i, w + 1], self.h[team_i, w + 2]]).only_enforce_if(streak)
                self.model.add_bool_or([self.h[team_i, w].Not(), self.h[team_i, w + 1].Not(), self.h[team_i, w + 2].Not()]).only_enforce_if(
                    streak.Not()
                )
                streak3h.append(streak)

            streak3a: list[cp_model.IntVar] = []
            for w in range(NUM_WEEKS - 2):
                streak = self.model.new_bool_var(f"s3a_{team_i.metro}_w{w}")
                self.model.add_bool_and(
                    [self.h[team_i, w].Not(), self.h[team_i, w + 1].Not(), self.h[team_i, w + 2].Not()]
                ).only_enforce_if(streak)
                self.model.add_bool_or([self.h[team_i, w], self.h[team_i, w + 1], self.h[team_i, w + 2]]).only_enforce_if(streak.Not())
                streak3a.append(streak)

            self.model.add(sum(streak3h) + sum(streak3a) <= 1)

    def _constraint_no_back_to_back(self) -> None:
        # Prevent any pair of teams from playing in consecutive weeks.
        for idx, team_i in enumerate(self.teams):
            for team_j in self.teams[idx + 1 :]:
                for w in range(NUM_WEEKS - 1):
                    self.model.add(
                        self.x[team_i, team_j, w]
                        + self.x[team_j, team_i, w]
                        + self.x[team_i, team_j, w + 1]
                        + self.x[team_j, team_i, w + 1]
                        <= 1
                    )

    def _constraint_phase_one_inventory(self, phase_one_inventory: Matchups) -> None:
        # Force phase II to schedule each team pair exactly as many times as phase I selected: 0, 1, or 2 meetings.
        expected_counts = Counter(phase_one_inventory)
        all_pairs = self.divisional_pairs + self.conference_pairs + self.non_conference_pairs

        unknown_pairs = set(expected_counts) - set(all_pairs)
        if unknown_pairs:
            pretty = sorted((a.metro, b.metro) for a, b in unknown_pairs)
            raise self.error_cls(f"Phase-1 inventory contains unknown team pairs: {pretty}")

        for team_i, team_j in all_pairs:
            total_meetings = sum(self.x[team_i, team_j, w] + self.x[team_j, team_i, w] for w in self.weeks)
            self.model.add(total_meetings == expected_counts.get((team_i, team_j), 0))

    def _constraint_divisional_home_balance(self) -> None:
        # Split each divisional home-and-home into exactly 1 home game and 1 away game for each team.
        for team_i, team_j in self.divisional_pairs:
            self.model.add(sum(self.x[team_i, team_j, w] for w in self.weeks) == 1)
            self.model.add(sum(self.x[team_j, team_i, w] for w in self.weeks) == 1)

    def _constraint_conference_home_balance(self) -> None:
        # Require 5-team division teams to host exactly 2 conference cross-division games and 4-team teams to host 2 or 3.
        for team_i in self.teams:
            conference_opponents = [
                team_j
                for team_j in self.teams
                if team_j != team_i and team_j.conference == team_i.conference and team_j.division != team_i.division
            ]
            conf_home_games = sum(self.x[team_i, team_j, w] for team_j in conference_opponents for w in self.weeks)

            if team_i in self.five_team_set:
                self.model.add(conf_home_games == 2)
            else:
                self.model.add(conf_home_games >= 2)
                self.model.add(conf_home_games <= 3)

    def _constraint_nonconference_home_balance(self) -> None:
        # Require teams in 5-team divisions to host 2 non-conference games and teams in 4-team divisions to host 2 or 3.
        for team_i in self.teams:
            non_conference_opponents = [team_j for team_j in self.teams if team_j.conference != team_i.conference]
            non_conf_home_games = sum(self.x[team_i, team_j, w] for team_j in non_conference_opponents for w in self.weeks)

            if team_i in self.five_team_set:
                self.model.add(non_conf_home_games == 2)
            else:
                self.model.add(non_conf_home_games >= 2)
                self.model.add(non_conf_home_games <= 3)

    def _constraint_max_consecutive_division(self) -> None:
        # Allow at most 3 straight divisional games but forbid any 4-game divisional streak.
        for team_i in self.teams:
            for w in range(NUM_WEEKS - 3):
                self.model.add(self.d[team_i, w] + self.d[team_i, w + 1] + self.d[team_i, w + 2] + self.d[team_i, w + 3] <= 3)

    def _constraint_no_back_to_back_divisional_games_to_open_season(self) -> None:
        # Allow either 0 teams or exactly 2 teams to open with divisional games in both weeks 1 and 2.
        opening_back_to_back: list[cp_model.IntVar] = []
        for team_i in self.teams:
            opens_with_two_div = self.model.new_bool_var(f"open2div_{team_i.metro}")
            self.model.add(opens_with_two_div <= self.d[team_i, 0])
            self.model.add(opens_with_two_div <= self.d[team_i, 1])
            self.model.add(opens_with_two_div >= self.d[team_i, 0] + self.d[team_i, 1] - 1)
            opening_back_to_back.append(opens_with_two_div)

        has_opening_pair = self.model.new_bool_var("has_opening_divisional_pair")
        self.model.add(sum(opening_back_to_back) == 2 * has_opening_pair)

    def _constraint_no_three_game_divisional_streak_at_season_start_or_end(self) -> None:
        # Forbid teams from starting or ending the season with 3 straight divisional games.
        for team_i in self.teams:
            self.model.add(self.d[team_i, 0] + self.d[team_i, 1] + self.d[team_i, 2] <= 2)
            self.model.add(self.d[team_i, NUM_WEEKS - 3] + self.d[team_i, NUM_WEEKS - 2] + self.d[team_i, NUM_WEEKS - 1] <= 2)

    def _constraint_max_one_total_three_game_divisional_streak(self) -> None:
        # Allow each team at most 1 total 3-game divisional streak across the season.
        for team_i in self.teams:
            streak3d: list[cp_model.IntVar] = []
            for w in range(NUM_WEEKS - 2):
                streak = self.model.new_bool_var(f"s3d_{team_i.metro}_w{w}")
                self.model.add_bool_and([self.d[team_i, w], self.d[team_i, w + 1], self.d[team_i, w + 2]]).only_enforce_if(streak)
                self.model.add_bool_or([self.d[team_i, w].Not(), self.d[team_i, w + 1].Not(), self.d[team_i, w + 2].Not()]).only_enforce_if(
                    streak.Not()
                )
                streak3d.append(streak)
            self.model.add(sum(streak3d) <= 1)

    def _constraint_division_density(self) -> None:
        # Cap divisional clustering at 7 in 10 and forbid 7 in 9 for 5-team divisions;
        # cap at 5 in 8 and forbid 4 in 7 for 4-team divisions.
        for team_i in self.five_team_set:
            for w in range(NUM_WEEKS - 9):
                self.model.add(sum(self.d[team_i, w + k] for k in range(10)) <= 7)
            for w in range(NUM_WEEKS - 8):
                self.model.add(sum(self.d[team_i, w + k] for k in range(9)) <= 6)
        for team_i in self.four_team_set:
            for w in range(NUM_WEEKS - 7):
                self.model.add(sum(self.d[team_i, w + k] for k in range(8)) <= 5)
            for w in range(NUM_WEEKS - 6):
                self.model.add(sum(self.d[team_i, w + k] for k in range(7)) <= 3)

    def _constraint_second_half_division(self) -> None:
        # Put at least half of each team's divisional games in weeks 9-16: 4 of 8 for 5-team divisions and 3 of 6 for 4-team divisions.
        second_half = range(NUM_WEEKS // 2, NUM_WEEKS)
        for team_i in self.five_team_set:
            self.model.add(sum(self.d[team_i, w] for w in second_half) >= 4)
        for team_i in self.four_team_set:
            self.model.add(sum(self.d[team_i, w] for w in second_half) >= 3)

    def _constraint_max_two_non_interleaved_divisional_opponents(self) -> None:
        # Count a divisional opponent as interleaved if another rival's first or second meeting
        # falls between the team's first and second meeting with that opponent.
        for team_i in self.teams:
            opps = self.div_opponents[team_i]
            first_meet: dict[Team, cp_model.IntVar] = {}
            second_meet: dict[Team, cp_model.IntVar] = {}
            for opp in opps:
                wh = self.model.new_int_var(0, NUM_WEEKS - 1, f"wh_{team_i.metro}_{opp.metro}")
                wa = self.model.new_int_var(0, NUM_WEEKS - 1, f"wa_{team_i.metro}_{opp.metro}")
                self.model.add(wh == sum(w * self.x[team_i, opp, w] for w in self.weeks))
                self.model.add(wa == sum(w * self.x[opp, team_i, w] for w in self.weeks))
                w1 = self.model.new_int_var(0, NUM_WEEKS - 1, f"fm_{team_i.metro}_{opp.metro}")
                w2 = self.model.new_int_var(0, NUM_WEEKS - 1, f"sm_{team_i.metro}_{opp.metro}")
                self.model.add_min_equality(w1, [wh, wa])
                self.model.add_max_equality(w2, [wh, wa])
                first_meet[opp] = w1
                second_meet[opp] = w2

            interleaved: list[cp_model.IntVar] = []
            for opp in opps:
                il = self.model.new_bool_var(f"il_{team_i.metro}_{opp.metro}")
                between_vars: list[cp_model.IntVar] = []
                for other in opps:
                    if other == opp:
                        continue
                    bk1 = self.model.new_bool_var(f"btw_{team_i.metro}_{opp.metro}_{other.metro}_1")
                    self.model.add(first_meet[other] > first_meet[opp]).only_enforce_if(bk1)
                    self.model.add(first_meet[other] < second_meet[opp]).only_enforce_if(bk1)
                    between_vars.append(bk1)
                    bk2 = self.model.new_bool_var(f"btw_{team_i.metro}_{opp.metro}_{other.metro}_2")
                    self.model.add(second_meet[other] > first_meet[opp]).only_enforce_if(bk2)
                    self.model.add(second_meet[other] < second_meet[opp]).only_enforce_if(bk2)
                    between_vars.append(bk2)
                self.model.add_bool_or(between_vars).only_enforce_if(il)
                interleaved.append(il)

            # Allow at most 2 non-interleaved divisional opponents per team.
            self.model.add(sum(interleaved) >= len(opps) - 2)

    def _constraint_week_16_matchups(self) -> None:
        # Require exactly 8 of the 9 games in the final week to be divisional.
        last_week = NUM_WEEKS - 1
        self.model.add(
            sum(self.x[team_i, team_j, last_week] + self.x[team_j, team_i, last_week] for team_i, team_j in self.divisional_pairs)
            == WEEK_16_DIVISIONAL_GAMES
        )

    def _constraint_late_divisional_presence(self) -> None:
        # Ensure every team has at least 1 divisional game across the last 2 weeks.
        for team_i in self.teams:
            self.model.add(self.d[team_i, NUM_WEEKS - 2] + self.d[team_i, NUM_WEEKS - 1] >= 1)

    def _populate_model(self, matchups: Matchups) -> None:
        self._constraint_one_game_per_week()
        self._constraint_home_balance()
        self._constraint_no_four_straight_home_or_away()
        self._constraint_home_away_balance_in_six_game_windows()
        self._constraint_no_three_game_home_or_away_streak_at_season_start_or_end()
        self._constraint_max_one_total_three_game_home_or_away_streak()
        self._constraint_no_back_to_back()
        self._constraint_phase_one_inventory(matchups)
        self._constraint_divisional_home_balance()
        self._constraint_conference_home_balance()
        self._constraint_nonconference_home_balance()
        self._constraint_max_consecutive_division()
        self._constraint_no_back_to_back_divisional_games_to_open_season()
        self._constraint_no_three_game_divisional_streak_at_season_start_or_end()
        self._constraint_max_one_total_three_game_divisional_streak()
        self._constraint_division_density()
        self._constraint_second_half_division()
        self._constraint_max_two_non_interleaved_divisional_opponents()
        self._constraint_week_16_matchups()
        self._constraint_late_divisional_presence()

    def _solve_model(self, seed: int = 0, time_limit: float = DEFAULT_TIME_LIMIT) -> Schedule:
        solver = cp_model.CpSolver()
        solver.parameters.random_seed = seed
        solver.parameters.randomize_search = True
        solver.parameters.num_search_workers = 1
        solver.parameters.max_time_in_seconds = time_limit

        status = solver.solve(self.model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            raise self.error_cls(f"CP-SAT returned status {solver.status_name(status)} - no feasible schedule")

        games: list[Game] = []
        for (team_i, team_j, w), var in self.x.items():
            if solver.value(var) == 1:
                games.append(Game(week=w + 1, home=team_i, away=team_j))

        return Schedule(games=tuple(games))

    def build_schedule(self, matchups: Matchups, seed: int = 0, time_limit: float = DEFAULT_TIME_LIMIT) -> Schedule:
        self._populate_model(matchups=matchups)
        return self._solve_model(seed=seed, time_limit=time_limit)
