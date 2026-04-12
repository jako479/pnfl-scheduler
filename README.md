# pnfl-scheduler

Generates the seasonal game schedule for the PNFL.

Uses Google OR-Tools CP-SAT to solve a constraint model that enforces
division matchups, home/away balance, streak limits, strength-of-schedule
rules, and final-week pairings.

## Setup

```bash
py -3.13 -m venv .venv
.venv\Scripts\activate
py -m pip install -e ".[dev]"
```

## Usage

Library only for now. The public entry point is `solve_schedule()`:

```python
from pnfl_scheduler.scheduler import PlayoffTeams, solve_schedule

schedule = solve_schedule(
    seed=0,
    playoffs=PlayoffTeams(
        division_winners=("New England", "Cincinnati", "Washington", "Chicago"),
        wild_cards=("Pittsburgh", "Denver", "Atlanta", "Minnesota"),
    ),
    last_place=("Las Vegas", "Seattle"),
    non_playoff_ranked=[
        "Miami", "Buffalo", "Jacksonville", "Los Angeles", "Las Vegas",
        "New York", "Philadelphia", "San Francisco", "Green Bay", "Seattle",
    ],
)

for game in schedule.games:
    print(f"Week {game.week:2d}: {game.away.city:15s} @ {game.home.city}")
```

## Testing

```bash
pytest
```
