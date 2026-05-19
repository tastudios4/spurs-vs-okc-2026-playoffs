"""Fetch and cache Spurs vs Thunder game data.

Pulls all head-to-head games (regular season + any cached playoff games)
between the San Antonio Spurs and Oklahoma City Thunder, and saves them
as CSVs under data/.

Designed to be idempotent: re-running will refresh, but the
`add_playoff_game(game_id)` helper at the bottom lets you append a single
WCF game without re-fetching everything.
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
from nba_api.stats.endpoints import leaguegamefinder, playergamelogs
from nba_api.stats.static import players, teams
from tabulate import tabulate

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SPURS_ID = 1610612759
THUNDER_ID = 1610612760
SEASON = "2025-26"

# Players we track season-long + per-H2H-game. Start small; add rotation
# players (Holmgren, Castle, Vassell, J. Williams, etc.) here as we go.
TRACKED_PLAYERS = {
    "Victor Wembanyama": {"id": 1641705, "team": "SAS"},
    "Shai Gilgeous-Alexander": {"id": 1628983, "team": "OKC"},
}

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

REG_SEASON_CSV = DATA_DIR / "regular_season_h2h.csv"
PLAYOFF_CSV = DATA_DIR / "playoff_h2h.csv"
PLAYER_H2H_CSV = DATA_DIR / "player_h2h_box.csv"
PLAYER_SEASON_LOG_CSV = DATA_DIR / "player_season_log.csv"
PLAYER_SEASON_AVG_CSV = DATA_DIR / "player_season_averages.csv"

# nba_api endpoints rate-limit aggressively; small pauses between calls.
SLEEP_BETWEEN_CALLS = 0.6


# ---------------------------------------------------------------------------
# Sanity check that the static team IDs match what nba_api thinks
# ---------------------------------------------------------------------------

def _verify_team_ids() -> None:
    spurs = teams.find_team_by_abbreviation("SAS")
    thunder = teams.find_team_by_abbreviation("OKC")
    assert spurs and spurs["id"] == SPURS_ID, f"Spurs ID mismatch: {spurs}"
    assert thunder and thunder["id"] == THUNDER_ID, f"Thunder ID mismatch: {thunder}"


def _verify_player_ids() -> None:
    for name, info in TRACKED_PLAYERS.items():
        last_name = name.split()[-1]
        matches = players.find_players_by_full_name(last_name)
        ids = {m["id"] for m in matches}
        assert info["id"] in ids, (
            f"Player {name} (id {info['id']}) not found via name lookup. "
            f"Matches for '{last_name}': {[(m['id'], m['full_name']) for m in matches]}"
        )


# ---------------------------------------------------------------------------
# Core fetchers
# ---------------------------------------------------------------------------

def fetch_team_games(team_id: int, season: str, season_type: str) -> pd.DataFrame:
    """All games for one team in one season (regular season or playoffs).

    Returns the raw team-level box score rows that nba_api gives us.
    """
    finder = leaguegamefinder.LeagueGameFinder(
        team_id_nullable=team_id,
        season_nullable=season,
        season_type_nullable=season_type,
    )
    df = finder.get_data_frames()[0]
    time.sleep(SLEEP_BETWEEN_CALLS)
    return df


def head_to_head_team_box(season: str, season_type: str) -> pd.DataFrame:
    """Spurs-vs-Thunder games for the given season + season type.

    Returns a tidy DataFrame with two rows per game (one per team).
    """
    spurs_games = fetch_team_games(SPURS_ID, season, season_type)
    thunder_games = fetch_team_games(THUNDER_ID, season, season_type)

    # Spurs rows where the opponent was OKC
    spurs_vs_okc = spurs_games[spurs_games["MATCHUP"].str.contains("OKC")]
    # Thunder rows where the opponent was SAS
    okc_vs_spurs = thunder_games[thunder_games["MATCHUP"].str.contains("SAS")]

    h2h = pd.concat([spurs_vs_okc, okc_vs_spurs], ignore_index=True)
    h2h = h2h.sort_values(["GAME_DATE", "TEAM_ABBREVIATION"]).reset_index(drop=True)
    return h2h


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def fetch_regular_season() -> pd.DataFrame:
    print(f"Fetching {SEASON} regular season Spurs vs Thunder team box scores...")
    df = head_to_head_team_box(SEASON, "Regular Season")
    df.to_csv(REG_SEASON_CSV, index=False)
    print(f"  -> wrote {len(df)} rows ({df['GAME_ID'].nunique()} games) to {REG_SEASON_CSV.relative_to(DATA_DIR.parent)}")
    return df


def fetch_playoffs() -> pd.DataFrame:
    print(f"Fetching {SEASON} playoff Spurs vs Thunder team box scores...")
    df = head_to_head_team_box(SEASON, "Playoffs")
    if df.empty:
        print("  -> no playoff H2H games found yet (expected pre-Game 1).")
        # Write an empty file with a clear shape so downstream scripts can no-op.
        df.to_csv(PLAYOFF_CSV, index=False)
        return df
    df.to_csv(PLAYOFF_CSV, index=False)
    print(f"  -> wrote {len(df)} rows ({df['GAME_ID'].nunique()} games) to {PLAYOFF_CSV.relative_to(DATA_DIR.parent)}")
    return df


# ---------------------------------------------------------------------------
# Player-level fetch
# ---------------------------------------------------------------------------

# Columns we want from the Advanced game log (Base supplies the rest).
# PlayerGameLogs returns percentages already normalized (e.g. USG_PCT in [0,1]).
_ADV_COLS_TO_KEEP = [
    "GAME_ID",
    "USG_PCT",
    "TS_PCT",
    "EFG_PCT",
    "OFF_RATING",
    "DEF_RATING",
    "NET_RATING",
    "AST_PCT",
    "OREB_PCT",
    "DREB_PCT",
    "REB_PCT",
    "TM_TOV_PCT",
    "PACE",
]


def _player_season_log(player_id: int, measure_type: str, season_type: str = "Regular Season") -> pd.DataFrame:
    """One season's game log for one player, for a given measure type + season type."""
    log = playergamelogs.PlayerGameLogs(
        player_id_nullable=player_id,
        season_nullable=SEASON,
        season_type_nullable=season_type,
        measure_type_player_game_logs_nullable=measure_type,
    ).get_data_frames()[0]
    time.sleep(SLEEP_BETWEEN_CALLS)
    return log


def _combined_player_log(player_id: int) -> pd.DataFrame:
    """Regular Season + Playoffs game logs, Base + Advanced merged on GAME_ID.

    A SEASON_TYPE column distinguishes the two; downstream code can split
    on it (e.g., compute season averages from Regular Season only).
    """
    parts: list[pd.DataFrame] = []
    for season_type in ("Regular Season", "Playoffs"):
        base = _player_season_log(player_id, "Base", season_type)
        if base.empty:
            continue
        adv = _player_season_log(player_id, "Advanced", season_type)
        adv_cols = [c for c in _ADV_COLS_TO_KEEP if c in adv.columns]
        merged = base.merge(adv[adv_cols], on="GAME_ID", how="left")
        merged["SEASON_TYPE"] = season_type
        parts.append(merged)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def fetch_player_data(h2h_game_ids: set[str]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Pull tracked players' season logs and derive H2H + season-average tables.

    Writes three CSVs:
      - player_season_log.csv     (every game, every tracked player)
      - player_h2h_box.csv        (just the H2H subset)
      - player_season_averages.csv (one row per player; simple per-game means)

    Returns (full_log, h2h_box, season_avg) for convenience.
    """
    all_logs: list[pd.DataFrame] = []

    for name, info in TRACKED_PLAYERS.items():
        print(f"Fetching player log: {name} ({info['team']}, id={info['id']})...")
        log = _combined_player_log(info["id"])
        log = log.assign(PLAYER_LABEL=name, TEAM_LABEL=info["team"])
        all_logs.append(log)

    full_log = pd.concat(all_logs, ignore_index=True)
    h2h_box = full_log[full_log["GAME_ID"].astype(str).isin(h2h_game_ids)].copy()
    h2h_box = h2h_box.sort_values(["GAME_DATE", "PLAYER_LABEL"]).reset_index(drop=True)

    # Season averages: simple per-game mean over numeric columns. Computed
    # from REGULAR SEASON ONLY so they're a stable baseline to compare H2H
    # (and eventually playoff) games against. For shooting %s and rate
    # stats, a minutes-weighted recompute is more correct — done in
    # 02_clean.py / 03_analyze.py.
    stat_cols = [
        "MIN", "PTS", "REB", "AST", "STL", "BLK", "TOV", "PF",
        "FGM", "FGA", "FG_PCT", "FG3M", "FG3A", "FG3_PCT", "FTM", "FTA", "FT_PCT",
        "OREB", "DREB", "PLUS_MINUS",
        "USG_PCT", "TS_PCT", "EFG_PCT", "OFF_RATING", "DEF_RATING", "NET_RATING",
        "AST_PCT", "OREB_PCT", "DREB_PCT", "REB_PCT", "TM_TOV_PCT", "PACE",
    ]
    stat_cols = [c for c in stat_cols if c in full_log.columns]

    reg_only = full_log[full_log["SEASON_TYPE"] == "Regular Season"]
    season_avg = (
        reg_only.groupby(["PLAYER_LABEL", "TEAM_LABEL"])[stat_cols]
        .mean()
        .reset_index()
    )
    games_played = (
        reg_only.groupby(["PLAYER_LABEL", "TEAM_LABEL"])
        .size()
        .reset_index(name="GAMES_PLAYED")
    )
    season_avg = season_avg.merge(games_played, on=["PLAYER_LABEL", "TEAM_LABEL"])

    full_log.to_csv(PLAYER_SEASON_LOG_CSV, index=False)
    h2h_box.to_csv(PLAYER_H2H_CSV, index=False)
    season_avg.to_csv(PLAYER_SEASON_AVG_CSV, index=False)

    print(f"  -> wrote {len(full_log)} rows to {PLAYER_SEASON_LOG_CSV.name}")
    print(f"  -> wrote {len(h2h_box)} H2H player-game rows to {PLAYER_H2H_CSV.name}")
    print(f"  -> wrote {len(season_avg)} player season-avg rows to {PLAYER_SEASON_AVG_CSV.name}")

    return full_log, h2h_box, season_avg


def add_playoff_game(game_id: str) -> None:
    """Append a single playoff game to the cached CSV.

    Idempotent: if the game_id is already cached, it will be replaced
    rather than duplicated. Use this after each WCF game tips off and
    the box score has settled on stats.nba.com.
    """
    print(f"Refreshing playoff cache and adding game {game_id}...")
    fresh = head_to_head_team_box(SEASON, "Playoffs")
    if game_id not in set(fresh["GAME_ID"].astype(str)):
        raise ValueError(
            f"Game {game_id} not found in the NBA playoff feed yet. "
            "Wait a few minutes after the final buzzer and try again."
        )
    fresh.to_csv(PLAYOFF_CSV, index=False)
    print(f"  -> playoff cache now has {fresh['GAME_ID'].nunique()} games.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    _verify_team_ids()
    _verify_player_ids()
    reg = fetch_regular_season()
    po = fetch_playoffs()

    h2h_game_ids = set(reg["GAME_ID"].astype(str))
    if not po.empty:
        h2h_game_ids |= set(po["GAME_ID"].astype(str))
    _, h2h_box, season_avg = fetch_player_data(h2h_game_ids)

    # ----- Friendly summaries to stdout. CSVs keep full precision. -----

    def _print_titled(title: str, body: str) -> None:
        # psql table borders (top + bottom) frame the body — no extra outer
        # dashes needed.
        print(f"\n{title}")
        print(body)

    # Tabulate format: "psql" gives full outer borders + vertical column
    # separators + header underline (no row-by-row separators).
    TFMT = "psql"

    # Team H2H: one row per game with both scores, margin, and winner.
    sas = reg[reg.TEAM_ABBREVIATION == "SAS"][["GAME_ID", "GAME_DATE", "MATCHUP", "PTS"]].rename(columns={"PTS": "SAS"})
    okc = reg[reg.TEAM_ABBREVIATION == "OKC"][["GAME_ID", "PTS"]].rename(columns={"PTS": "OKC"})
    summary = sas.merge(okc, on="GAME_ID").sort_values("GAME_DATE")
    summary["MARGIN"] = (summary["SAS"] - summary["OKC"]).map(lambda x: f"{x:+d}")
    summary["WINNER"] = summary.apply(lambda r: "SAS" if r["SAS"] > r["OKC"] else "OKC", axis=1)
    summary = summary[["GAME_DATE", "MATCHUP", "SAS", "OKC", "WINNER", "MARGIN"]]
    _print_titled(
        "Regular season head-to-head summary (n=5):",
        tabulate(summary, headers="keys", tablefmt=TFMT, showindex=False,
                 disable_numparse=True,
                 colalign=("left", "left", "right", "right", "center", "right")),
    )

    # Player H2H: clean date, 1-decimal minutes, percent-formatted rates.
    # Grouped by game with a separator between games for readability.
    ph = h2h_box[["GAME_DATE", "PLAYER_LABEL", "MIN", "PTS", "REB", "AST", "USG_PCT", "TS_PCT"]].copy()
    ph["GAME_DATE"] = pd.to_datetime(ph["GAME_DATE"]).dt.strftime("%Y-%m-%d")
    ph = ph.sort_values(["GAME_DATE", "PLAYER_LABEL"]).reset_index(drop=True)
    # Pre-format columns that need % or fixed-decimal formatting.
    ph_display = ph.copy()
    ph_display["MIN"] = ph_display["MIN"].map("{:.1f}".format)
    ph_display["USG_PCT"] = ph_display["USG_PCT"].map("{:.1%}".format)
    ph_display["TS_PCT"] = ph_display["TS_PCT"].map("{:.1%}".format)
    ph_table = tabulate(
        ph_display, headers="keys", tablefmt=TFMT, showindex=False,
        disable_numparse=True,
        colalign=("left", "left", "right", "right", "right", "right", "right", "right"),
    )
    # Inject the header-separator line between game groups.
    # psql layout: [top_border, header_row, header_sep, ...data_rows..., bottom_border]
    lines = ph_table.split("\n")
    top_border, header_row, header_sep = lines[0], lines[1], lines[2]
    *data_lines, bottom_border = lines[3:]
    grouped = [top_border, header_row, header_sep]
    prev_date = None
    for line, date in zip(data_lines, ph["GAME_DATE"]):
        if prev_date is not None and date != prev_date:
            grouped.append(header_sep)
        grouped.append(line)
        prev_date = date
    grouped.append(bottom_border)
    _print_titled("Player H2H box (key cols):", "\n".join(grouped))

    # Player season averages: 1-decimal stats, percent-formatted rates.
    sa = season_avg[["PLAYER_LABEL", "TEAM_LABEL", "GAMES_PLAYED",
                     "MIN", "PTS", "REB", "AST", "USG_PCT", "TS_PCT"]].copy()
    sa_display = sa.copy()
    sa_display["GAMES_PLAYED"] = sa_display["GAMES_PLAYED"].map("{:.0f}".format)
    for col in ("MIN", "PTS", "REB", "AST"):
        sa_display[col] = sa_display[col].map("{:.1f}".format)
    for col in ("USG_PCT", "TS_PCT"):
        sa_display[col] = sa_display[col].map("{:.1%}".format)
    _print_titled(
        "Player season averages (key cols):",
        tabulate(sa_display, headers="keys", tablefmt=TFMT, showindex=False,
                 disable_numparse=True,
                 colalign=("left", "left", "right", "right", "right", "right", "right", "right", "right")),
    )
