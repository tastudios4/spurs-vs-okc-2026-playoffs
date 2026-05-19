"""Clean and enrich the raw H2H data from 01_fetch_data.py.

Reads `data/regular_season_h2h.csv` and `data/player_h2h_box.csv`, adds the
context flags we established during exploration (Wemby's post-injury minutes
restriction, SGA's Feb-4 DNP, NBA Cup neutral-site game, blowout flag), and
derives the canonical "four factors" stats plus possessions / pace / OffRtg /
DefRtg from the raw box scores.

Writes:
  - data/team_h2h_clean.csv     (10 rows: 2 per game x 5 games, enriched)
  - data/player_h2h_clean.csv   ( 9 rows: 4 SGA + 5 Wemby; game-level flags joined on)

The raw CSVs are not modified.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from tabulate import tabulate

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

RAW_TEAM = DATA_DIR / "regular_season_h2h.csv"
RAW_PLAYER = DATA_DIR / "player_h2h_box.csv"

CLEAN_TEAM = DATA_DIR / "team_h2h_clean.csv"
CLEAN_PLAYER = DATA_DIR / "player_h2h_clean.csv"


# ---------------------------------------------------------------------------
# Game-level context. Keyed by GAME_DATE (a natural human-readable join).
# These flags came out of the exploration in the 01_fetch step — see the
# README and the wemby-injury memory note for the reasoning.
# ---------------------------------------------------------------------------

GAME_CONTEXT = {
    "2025-12-13": {"wemby_status": "restricted", "sga_played": True,  "is_cup_knockout": True,  "is_neutral_site": True},
    "2025-12-23": {"wemby_status": "restricted", "sga_played": True,  "is_cup_knockout": False, "is_neutral_site": False},
    "2025-12-25": {"wemby_status": "restricted", "sga_played": True,  "is_cup_knockout": False, "is_neutral_site": False},
    "2026-01-13": {"wemby_status": "ramping",    "sga_played": True,  "is_cup_knockout": False, "is_neutral_site": False},
    "2026-02-04": {"wemby_status": "normal",     "sga_played": False, "is_cup_knockout": False, "is_neutral_site": False},
}


# ---------------------------------------------------------------------------
# Cleaning steps
# ---------------------------------------------------------------------------

def add_team_context(team: pd.DataFrame) -> pd.DataFrame:
    """Date normalization + signed margin + blowout flag + game-level context."""
    team = team.copy()
    team["GAME_DATE"] = pd.to_datetime(team["GAME_DATE"]).dt.strftime("%Y-%m-%d")

    # Self-join on GAME_ID to bring in opponent's points (for margin).
    opp_pts = team[["GAME_ID", "TEAM_ABBREVIATION", "PTS"]].rename(
        columns={"TEAM_ABBREVIATION": "_OPP", "PTS": "OPP_PTS"}
    )
    team = team.merge(opp_pts, on="GAME_ID")
    team = team[team["TEAM_ABBREVIATION"] != team["_OPP"]].drop(columns=["_OPP"]).copy()

    team["MARGIN"] = team["PTS"] - team["OPP_PTS"]
    team["is_blowout"] = team["MARGIN"].abs() >= 10

    flags = (
        pd.DataFrame.from_dict(GAME_CONTEXT, orient="index")
        .reset_index()
        .rename(columns={"index": "GAME_DATE"})
    )
    team = team.merge(flags, on="GAME_DATE")
    return team


def add_four_factors_and_ratings(team: pd.DataFrame) -> pd.DataFrame:
    """Possessions, pace, OffRtg/DefRtg/NetRtg, and the four factors.

    Possessions follow basketball-reference's canonical formula
    (average of the two teams' estimates). The four factors are Dean
    Oliver's: eFG%, TOV%, OREB%, FT rate.
    """
    team = team.copy()

    # Pull in opponent FGA/FTA/OREB/DREB/TOV (needed for possessions + OREB%).
    opp_box = team[["GAME_ID", "TEAM_ABBREVIATION", "FGA", "FTA", "OREB", "DREB", "TOV"]].rename(
        columns={
            "TEAM_ABBREVIATION": "_OPP",
            "FGA": "OPP_FGA", "FTA": "OPP_FTA",
            "OREB": "OPP_OREB", "DREB": "OPP_DREB", "TOV": "OPP_TOV",
        }
    )
    team = team.merge(opp_box, on="GAME_ID")
    team = team[team["TEAM_ABBREVIATION"] != team["_OPP"]].drop(columns=["_OPP"]).copy()

    # Possessions: average of the two teams' estimates (basketball-reference
    # simplified formula).
    poss_team = team["FGA"] + 0.44 * team["FTA"] - team["OREB"] + team["TOV"]
    poss_opp  = team["OPP_FGA"] + 0.44 * team["OPP_FTA"] - team["OPP_OREB"] + team["OPP_TOV"]
    team["POSS"] = 0.5 * (poss_team + poss_opp)

    # Pace: possessions per 48 minutes. team MIN is total player-minutes
    # (240 for a regulation game; more for OT). 240 * POSS / MIN normalizes.
    team["PACE"] = 240 * team["POSS"] / team["MIN"]

    team["OFF_RATING"] = 100 * team["PTS"] / team["POSS"]
    team["DEF_RATING"] = 100 * team["OPP_PTS"] / team["POSS"]
    team["NET_RATING"] = team["OFF_RATING"] - team["DEF_RATING"]

    # Four factors (Dean Oliver, 2003).
    team["EFG_PCT"]  = (team["FGM"] + 0.5 * team["FG3M"]) / team["FGA"]
    team["TOV_PCT"]  = team["TOV"] / team["POSS"]
    team["OREB_PCT"] = team["OREB"] / (team["OREB"] + team["OPP_DREB"])
    team["FT_RATE"]  = team["FTM"] / team["FGA"]

    return team


def add_player_context(player: pd.DataFrame, team_clean: pd.DataFrame) -> pd.DataFrame:
    """Strip GAME_DATE time + join the game-level context flags."""
    player = player.copy()
    player["GAME_DATE"] = pd.to_datetime(player["GAME_DATE"]).dt.strftime("%Y-%m-%d")

    flags = team_clean.drop_duplicates(subset=["GAME_ID"])[[
        "GAME_ID", "wemby_status", "sga_played",
        "is_cup_knockout", "is_neutral_site", "is_blowout",
    ]]
    return player.merge(flags, on="GAME_ID")


# ---------------------------------------------------------------------------
# Print helpers (mirrors 01_fetch_data.py's style for visual consistency)
# ---------------------------------------------------------------------------

TFMT = "psql"


def _print_titled(title: str, body: str) -> None:
    print(f"\n{title}")
    print(body)


def _format_team_four_factors(team: pd.DataFrame) -> str:
    """Build the grouped-by-game four-factors table string."""
    ff = team[[
        "GAME_DATE", "TEAM_ABBREVIATION", "WL", "MARGIN",
        "PACE", "OFF_RATING", "DEF_RATING", "NET_RATING",
        "EFG_PCT", "TOV_PCT", "OREB_PCT", "FT_RATE",
    ]].copy()
    ff = ff.sort_values(["GAME_DATE", "TEAM_ABBREVIATION"]).reset_index(drop=True)

    disp = ff.copy()
    disp["MARGIN"]     = disp["MARGIN"].map(lambda x: f"{x:+d}")
    disp["PACE"]       = disp["PACE"].map("{:.1f}".format)
    disp["OFF_RATING"] = disp["OFF_RATING"].map("{:.1f}".format)
    disp["DEF_RATING"] = disp["DEF_RATING"].map("{:.1f}".format)
    disp["NET_RATING"] = disp["NET_RATING"].map(lambda x: f"{x:+.1f}")
    for col in ("EFG_PCT", "TOV_PCT", "OREB_PCT"):
        disp[col] = disp[col].map("{:.1%}".format)
    disp["FT_RATE"]    = disp["FT_RATE"].map("{:.3f}".format)

    raw = tabulate(
        disp, headers="keys", tablefmt=TFMT, showindex=False,
        disable_numparse=True,
        colalign=("left", "center", "center", "right",
                  "right", "right", "right", "right",
                  "right", "right", "right", "right"),
    )
    # Inject a header-separator line between game groups.
    lines = raw.split("\n")
    top, header, sep = lines[0], lines[1], lines[2]
    *data, bottom = lines[3:]
    out = [top, header, sep]
    prev = None
    for line, date in zip(data, ff["GAME_DATE"]):
        if prev is not None and date != prev:
            out.append(sep)
        out.append(line)
        prev = date
    out.append(bottom)
    return "\n".join(out)


def _format_game_context(team: pd.DataFrame) -> str:
    """One row per game showing the context flags (SAS perspective)."""
    ctx = (
        team[team["TEAM_ABBREVIATION"] == "SAS"][[
            "GAME_DATE", "MATCHUP", "MARGIN", "is_blowout",
            "wemby_status", "sga_played", "is_cup_knockout", "is_neutral_site",
        ]]
        .sort_values("GAME_DATE")
        .reset_index(drop=True)
    )
    disp = ctx.copy()
    disp["MARGIN"] = disp["MARGIN"].map(lambda x: f"{x:+d}")
    for c in ("is_blowout", "sga_played", "is_cup_knockout", "is_neutral_site"):
        disp[c] = disp[c].map(lambda v: "yes" if v else "no")

    return tabulate(
        disp, headers="keys", tablefmt=TFMT, showindex=False,
        disable_numparse=True,
        colalign=("left", "left", "right",
                  "center", "center", "center", "center", "center"),
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    print("Reading raw data...")
    team_raw = pd.read_csv(RAW_TEAM)
    player_raw = pd.read_csv(RAW_PLAYER)

    print("Adding team context flags + margin + blowout flag...")
    team = add_team_context(team_raw)

    print("Deriving four factors, pace, and ratings...")
    team = add_four_factors_and_ratings(team)

    print("Joining game-level flags onto player rows...")
    player = add_player_context(player_raw, team)

    team.to_csv(CLEAN_TEAM, index=False)
    player.to_csv(CLEAN_PLAYER, index=False)
    print(f"  -> wrote {len(team)} rows to {CLEAN_TEAM.relative_to(DATA_DIR.parent)}")
    print(f"  -> wrote {len(player)} rows to {CLEAN_PLAYER.relative_to(DATA_DIR.parent)}")

    _print_titled("Per-game context flags:", _format_game_context(team))
    _print_titled("Team four factors + ratings per game:", _format_team_four_factors(team))


if __name__ == "__main__":
    main()
