"""Compute the headline deltas: H2H vs season averages.

Reads the cleaned team and player data, computes the deltas that the
README headline references, and prints summary tables. The intent is
that you can re-run this script after each playoff game and immediately
see how the WCF series is tracking vs the regular-season H2H pattern.

Outputs:
  - data/analysis_summary.csv  (flat player-metric table for README citations)
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from tabulate import tabulate

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

TEAM_CLEAN          = DATA_DIR / "team_h2h_clean.csv"
PLAYER_CLEAN        = DATA_DIR / "player_h2h_clean.csv"
PLAYER_SEASON_AVG   = DATA_DIR / "player_season_averages.csv"
SUMMARY_OUT         = DATA_DIR / "analysis_summary.csv"

# Metrics we surface in the player delta table, in display order.
PLAYER_METRICS = [
    "MIN", "PTS", "REB", "AST", "TOV", "USG_PCT", "TS_PCT", "EFG_PCT",
    "OFF_RATING", "DEF_RATING", "NET_RATING", "PLUS_MINUS",
]

TEAM_METRICS = [
    "PACE", "OFF_RATING", "DEF_RATING", "NET_RATING",
    "EFG_PCT", "TOV_PCT", "OREB_PCT", "FT_RATE",
]


# ---------------------------------------------------------------------------
# Analysis steps
# ---------------------------------------------------------------------------

def player_delta_table(player_h2h: pd.DataFrame, season_avg: pd.DataFrame) -> pd.DataFrame:
    """Long-form table: one row per (player, metric) with season / H2H / delta.

    H2H is restricted to Regular Season games so the comparison is
    apples-to-apples with the season-average baseline. Once playoff
    games exist, a separate slice will surface them.
    """
    h2h = player_h2h[player_h2h["SEASON_TYPE"] == "Regular Season"].copy()
    metric_cols = [c for c in PLAYER_METRICS if c in h2h.columns and c in season_avg.columns]

    h2h_avg = h2h.groupby("PLAYER_LABEL")[metric_cols].mean().reset_index()
    h2h_games = h2h.groupby("PLAYER_LABEL").size().reset_index(name="H2H_N")
    h2h_avg = h2h_avg.merge(h2h_games, on="PLAYER_LABEL")

    rows = []
    for _, p in season_avg.iterrows():
        name = p["PLAYER_LABEL"]
        h2h_row = h2h_avg[h2h_avg["PLAYER_LABEL"] == name]
        if h2h_row.empty:
            continue
        h2h_row = h2h_row.iloc[0]
        for col in metric_cols:
            season_val = p[col]
            h2h_val = h2h_row[col]
            rows.append({
                "PLAYER": name,
                "TEAM": p["TEAM_LABEL"],
                "METRIC": col,
                "SEASON_AVG": season_val,
                "H2H_AVG": h2h_val,
                "DELTA": h2h_val - season_val,
                "SEASON_N": int(p["GAMES_PLAYED"]),
                "H2H_N": int(h2h_row["H2H_N"]),
            })
    return pd.DataFrame(rows)


def team_h2h_summary(team_clean: pd.DataFrame) -> pd.DataFrame:
    """Aggregate four factors + ratings across H2H games, by team and slice."""
    slices = [("All H2H", team_clean)]
    for label, st in [("Regular Season H2H", "Regular Season"), ("Playoff H2H", "Playoffs")]:
        df = team_clean[team_clean["SEASON_TYPE"] == st]
        if not df.empty:
            slices.append((label, df))

    rows = []
    for label, df in slices:
        for team_abbr in ("SAS", "OKC"):
            sub = df[df["TEAM_ABBREVIATION"] == team_abbr]
            if sub.empty:
                continue
            agg = {col: sub[col].mean() for col in TEAM_METRICS}
            agg.update({
                "SAMPLE": label,
                "TEAM": team_abbr,
                "N_GAMES": int(len(sub)),
                "RECORD": f"{(sub['WL']=='W').sum()}-{(sub['WL']=='L').sum()}",
            })
            rows.append(agg)
    return pd.DataFrame(rows)


def wemby_status_split(team_clean: pd.DataFrame) -> pd.DataFrame:
    """SAS results bucketed by Wemby's health status."""
    sas = team_clean[team_clean["TEAM_ABBREVIATION"] == "SAS"]
    return (
        sas.groupby("wemby_status", sort=False)
        .agg(
            N_GAMES=("GAME_ID", "count"),
            RECORD=("WL", lambda x: f"{(x=='W').sum()}-{(x=='L').sum()}"),
            AVG_MARGIN=("MARGIN", "mean"),
            AVG_OFF_RATING=("OFF_RATING", "mean"),
            AVG_DEF_RATING=("DEF_RATING", "mean"),
            AVG_NET_RATING=("NET_RATING", "mean"),
        )
        .reset_index()
    )


# ---------------------------------------------------------------------------
# Pretty printing (mirrors 01/02 style)
# ---------------------------------------------------------------------------

TFMT = "psql"


def _print_titled(title: str, body: str) -> None:
    print(f"\n{title}")
    print(body)


def _fmt(v, kind: str) -> str:
    """Single-value formatter — kind in {pct, rate, int, signed_int, sint1, float1}."""
    if pd.isna(v):
        return "—"
    if kind == "pct":
        return f"{v:.1%}"
    if kind == "rate":
        return f"{v:.3f}"
    if kind == "int":
        return f"{int(round(v))}"
    if kind == "signed_int":
        return f"{int(round(v)):+d}"
    if kind == "sint1":
        return f"{v:+.1f}"
    if kind == "float1":
        return f"{v:.1f}"
    return str(v)


# Per-metric formatting and a friendly label for display.
METRIC_DISPLAY = {
    "MIN":          ("float1", "MIN"),
    "PTS":          ("float1", "PTS"),
    "REB":          ("float1", "REB"),
    "AST":          ("float1", "AST"),
    "TOV":          ("float1", "TOV"),
    "USG_PCT":      ("pct",    "USG%"),
    "TS_PCT":       ("pct",    "TS%"),
    "EFG_PCT":      ("pct",    "eFG%"),
    "OFF_RATING":   ("float1", "OffRtg"),
    "DEF_RATING":   ("float1", "DefRtg"),
    "NET_RATING":   ("sint1",  "NetRtg"),
    "PLUS_MINUS":   ("sint1",  "+/-"),
    "PACE":         ("float1", "PACE"),
    "TOV_PCT":      ("pct",    "TOV%"),
    "OREB_PCT":     ("pct",    "OREB%"),
    "FT_RATE":      ("rate",   "FT rate"),
}


def _format_player_delta(deltas: pd.DataFrame) -> str:
    """Build the player x metric delta table grouped by player."""
    rows = []
    for _, r in deltas.iterrows():
        kind, label = METRIC_DISPLAY.get(r["METRIC"], ("float1", r["METRIC"]))
        delta_kind = "sint1" if kind in ("float1", "sint1") else ("pct" if kind == "pct" else "rate")
        # For percentages, format the delta in absolute percentage points.
        if kind == "pct":
            delta_str = f"{(r['DELTA'])*100:+.1f} pp"
        elif kind == "rate":
            delta_str = f"{r['DELTA']:+.3f}"
        else:
            delta_str = f"{r['DELTA']:+.1f}"
        rows.append({
            "PLAYER":    r["PLAYER"],
            "TEAM":      r["TEAM"],
            "METRIC":    label,
            "SEASON":    _fmt(r["SEASON_AVG"], kind),
            "H2H":       _fmt(r["H2H_AVG"], kind),
            "Δ":         delta_str,
            "SEASON N":  r["SEASON_N"],
            "H2H N":     r["H2H_N"],
        })
    out = pd.DataFrame(rows)

    # Tabulate + game-style grouping: print rows for one player, separator,
    # then next player.
    table = tabulate(
        out, headers="keys", tablefmt=TFMT, showindex=False,
        disable_numparse=True,
        colalign=("left", "center", "left", "right", "right", "right", "right", "right"),
    )
    lines = table.split("\n")
    top, header, sep = lines[0], lines[1], lines[2]
    *data_lines, bottom = lines[3:]
    grouped = [top, header, sep]
    prev = None
    for line, player in zip(data_lines, out["PLAYER"]):
        if prev is not None and player != prev:
            grouped.append(sep)
        grouped.append(line)
        prev = player
    grouped.append(bottom)
    return "\n".join(grouped)


def _format_team_summary(summary: pd.DataFrame) -> str:
    disp = summary.copy()
    disp["PACE"]       = disp["PACE"].map(lambda v: _fmt(v, "float1"))
    disp["OFF_RATING"] = disp["OFF_RATING"].map(lambda v: _fmt(v, "float1"))
    disp["DEF_RATING"] = disp["DEF_RATING"].map(lambda v: _fmt(v, "float1"))
    disp["NET_RATING"] = disp["NET_RATING"].map(lambda v: _fmt(v, "sint1"))
    for c in ("EFG_PCT", "TOV_PCT", "OREB_PCT"):
        disp[c] = disp[c].map(lambda v: _fmt(v, "pct"))
    disp["FT_RATE"]    = disp["FT_RATE"].map(lambda v: _fmt(v, "rate"))

    cols = ["SAMPLE", "TEAM", "N_GAMES", "RECORD", *TEAM_METRICS]
    return tabulate(
        disp[cols], headers="keys", tablefmt=TFMT, showindex=False,
        disable_numparse=True,
        colalign=("left", "center", "right", "center",
                  "right", "right", "right", "right",
                  "right", "right", "right", "right"),
    )


def _format_wemby_split(split: pd.DataFrame) -> str:
    disp = split.copy()
    disp["AVG_MARGIN"]     = disp["AVG_MARGIN"].map(lambda v: _fmt(v, "sint1"))
    disp["AVG_OFF_RATING"] = disp["AVG_OFF_RATING"].map(lambda v: _fmt(v, "float1"))
    disp["AVG_DEF_RATING"] = disp["AVG_DEF_RATING"].map(lambda v: _fmt(v, "float1"))
    disp["AVG_NET_RATING"] = disp["AVG_NET_RATING"].map(lambda v: _fmt(v, "sint1"))
    return tabulate(
        disp, headers="keys", tablefmt=TFMT, showindex=False,
        disable_numparse=True,
        colalign=("left", "right", "center", "right", "right", "right", "right"),
    )


# ---------------------------------------------------------------------------
# Headline-ready story numbers
# ---------------------------------------------------------------------------

def headline_numbers(player_deltas: pd.DataFrame, team_clean: pd.DataFrame) -> dict[str, str]:
    """Boil it down to the few numbers the README opens with."""
    out: dict[str, str] = {}

    sga_ts = player_deltas[(player_deltas.PLAYER == "Shai Gilgeous-Alexander") & (player_deltas.METRIC == "TS_PCT")]
    if not sga_ts.empty:
        r = sga_ts.iloc[0]
        out["sga_ts_season"] = f"{r['SEASON_AVG']:.1%}"
        out["sga_ts_h2h"] = f"{r['H2H_AVG']:.1%}"
        out["sga_ts_delta_pp"] = f"{(r['DELTA'])*100:+.1f}"
        out["sga_h2h_n"] = str(r['H2H_N'])

    sas_reg = team_clean[(team_clean.TEAM_ABBREVIATION == "SAS") & (team_clean.SEASON_TYPE == "Regular Season")]
    out["sas_record"] = f"{(sas_reg['WL']=='W').sum()}-{(sas_reg['WL']=='L').sum()}"
    out["sas_avg_margin"] = f"{sas_reg['MARGIN'].mean():+.1f}"
    out["sas_net_rating_h2h"] = f"{sas_reg['NET_RATING'].mean():+.1f}"

    restricted = sas_reg[sas_reg["wemby_status"] == "restricted"]
    if not restricted.empty:
        out["sas_record_wemby_restricted"] = f"{(restricted['WL']=='W').sum()}-{(restricted['WL']=='L').sum()}"
        out["wemby_restricted_n"] = str(len(restricted))

    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    team = pd.read_csv(TEAM_CLEAN)
    player = pd.read_csv(PLAYER_CLEAN)
    season_avg = pd.read_csv(PLAYER_SEASON_AVG)

    deltas = player_delta_table(player, season_avg)
    team_summary = team_h2h_summary(team)
    split = wemby_status_split(team)
    headline = headline_numbers(deltas, team)

    deltas.to_csv(SUMMARY_OUT, index=False)
    print(f"Wrote {len(deltas)} player-metric rows to {SUMMARY_OUT.relative_to(DATA_DIR.parent)}")

    _print_titled("Headline numbers:", "\n".join(f"  {k:30s} = {v}" for k, v in headline.items()))
    _print_titled("Player H2H vs season averages:", _format_player_delta(deltas))
    _print_titled("Team H2H four factors + ratings (aggregated):", _format_team_summary(team_summary))
    _print_titled("SAS results by Wemby status (regular season H2H):", _format_wemby_split(split))


if __name__ == "__main__":
    main()
