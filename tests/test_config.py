from __future__ import annotations

from pathlib import Path

import pytest

from pnfl_scheduler import config
from pnfl_scheduler.config import ConfigError, find_config_path, load_config, load_league
from pnfl_scheduler.domain.league import League

# ---------------------------------------------------------------------------
# A complete, valid config. Tests derive invalid variants from this.
# ---------------------------------------------------------------------------

VALID_CONFIG = """\
[Settings]
TimeLimit = 120

[ConferenceRanking]
AFC =
    New England
    Miami
    Jacksonville
    Buffalo
    Cincinnati
    Pittsburgh
    Denver
    Los Angeles
    Las Vegas
NFC =
    Washington
    Atlanta
    New York
    Philadelphia
    Chicago
    Minnesota
    San Francisco
    Green Bay
    Seattle

[Divisions]
AFC_EAST =
    Buffalo
    Jacksonville
    Miami
    New England
AFC_WEST =
    Cincinnati
    Denver
    Las Vegas
    Los Angeles
    Pittsburgh
NFC_EAST =
    Atlanta
    New York
    Philadelphia
    Washington
NFC_WEST =
    Chicago
    Green Bay
    Minnesota
    San Francisco
    Seattle
"""


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def _valid_config(tmp_path: Path) -> Path:
    return _write(tmp_path / "generate-schedule.ini", VALID_CONFIG)


# ---------------------------------------------------------------------------
# load_config — TimeLimit
# ---------------------------------------------------------------------------


def test_load_config_reads_time_limit(tmp_path: Path) -> None:
    cfg = load_config(_valid_config(tmp_path))
    assert cfg.time_limit == 120.0


def test_load_config_defaults_time_limit_when_missing(tmp_path: Path) -> None:
    ini = _write(tmp_path / "generate-schedule.ini", VALID_CONFIG.replace("TimeLimit = 120\n", ""))
    assert load_config(ini).time_limit == config.DEFAULT_TIME_LIMIT


def test_load_config_defaults_time_limit_when_settings_section_missing(tmp_path: Path) -> None:
    ini = _write(tmp_path / "generate-schedule.ini", VALID_CONFIG.replace("[Settings]\nTimeLimit = 120\n\n", ""))
    assert load_config(ini).time_limit == config.DEFAULT_TIME_LIMIT


def test_load_config_errors_on_invalid_time_limit(tmp_path: Path) -> None:
    ini = _write(tmp_path / "generate-schedule.ini", VALID_CONFIG.replace("TimeLimit = 120", "TimeLimit = fast"))
    with pytest.raises(ConfigError):
        load_config(ini)


# ---------------------------------------------------------------------------
# load_config / load_league — config file resolution
# ---------------------------------------------------------------------------


def test_load_config_errors_when_explicit_path_missing(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_config(tmp_path / "nonexistent.ini")


def test_load_config_errors_when_no_config_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "CONFIG_CANDIDATES", [tmp_path / "generate-schedule.ini"])
    with pytest.raises(ConfigError):
        load_config()


def test_load_config_succeeds_with_explicit_path_when_no_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "CONFIG_CANDIDATES", [tmp_path / "missing-default.ini"])
    cfg = load_config(_valid_config(tmp_path))
    assert cfg.time_limit == 120.0


def test_find_config_path_errors_when_none_exist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "CONFIG_CANDIDATES", [tmp_path / "generate-schedule.ini"])
    with pytest.raises(ConfigError):
        find_config_path()


def test_find_config_path_resolves_first_existing_candidate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    missing = tmp_path / "generate-schedule.dev.ini"
    present = _valid_config(tmp_path)
    monkeypatch.setattr(config, "CONFIG_CANDIDATES", [missing, present])
    assert find_config_path() == present


# ---------------------------------------------------------------------------
# load_league — required sections and keys
# ---------------------------------------------------------------------------


def test_load_league_reads_valid_config(tmp_path: Path) -> None:
    league = load_league(_valid_config(tmp_path))
    assert isinstance(league, League)
    assert len(league.teams) == 18


def test_load_league_errors_when_divisions_section_missing(tmp_path: Path) -> None:
    text = VALID_CONFIG[: VALID_CONFIG.index("[Divisions]")]
    ini = _write(tmp_path / "generate-schedule.ini", text)
    with pytest.raises(ConfigError):
        load_league(ini)


def test_load_league_errors_when_conference_ranking_section_missing(tmp_path: Path) -> None:
    text = VALID_CONFIG[: VALID_CONFIG.index("[ConferenceRanking]")] + VALID_CONFIG[VALID_CONFIG.index("[Divisions]") :]
    ini = _write(tmp_path / "generate-schedule.ini", text)
    with pytest.raises(ConfigError):
        load_league(ini)


def test_load_league_errors_when_afc_ranking_key_missing(tmp_path: Path) -> None:
    afc_block = VALID_CONFIG[VALID_CONFIG.index("AFC =") : VALID_CONFIG.index("NFC =")]
    ini = _write(tmp_path / "generate-schedule.ini", VALID_CONFIG.replace(afc_block, ""))
    with pytest.raises(ConfigError):
        load_league(ini)


def test_load_league_errors_when_afc_ranking_empty(tmp_path: Path) -> None:
    afc_block = VALID_CONFIG[VALID_CONFIG.index("AFC =") : VALID_CONFIG.index("NFC =")]
    ini = _write(tmp_path / "generate-schedule.ini", VALID_CONFIG.replace(afc_block, "AFC =\n"))
    with pytest.raises(ConfigError):
        load_league(ini)


def test_load_league_errors_on_invalid_league_data(tmp_path: Path) -> None:
    # Drop a team from AFC_EAST so the division is the wrong size.
    ini = _write(tmp_path / "generate-schedule.ini", VALID_CONFIG.replace("    New England\nAFC_WEST =", "AFC_WEST ="))
    with pytest.raises(ConfigError):
        load_league(ini)


def test_load_league_errors_on_invalid_ini(tmp_path: Path) -> None:
    ini = _write(tmp_path / "generate-schedule.ini", "[Divisions\nbroken")
    with pytest.raises(ConfigError):
        load_league(ini)


# ---------------------------------------------------------------------------
# find_history_path — first existing candidate, no error on absence
# ---------------------------------------------------------------------------


def test_find_history_path_resolves_first_existing_candidate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    missing = tmp_path / "nonconf_history.json"
    present = _write(tmp_path / "data_history.json", "{}")
    monkeypatch.setattr(config, "HISTORY_CANDIDATES", [missing, present])
    assert config.find_history_path() == present


def test_find_history_path_falls_back_to_first_candidate_when_none_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = tmp_path / "nonconf_history.json"
    monkeypatch.setattr(config, "HISTORY_CANDIDATES", [first, tmp_path / "data.json"])
    assert config.find_history_path() == first
