"""Compute the headline deltas: H2H vs season averages.

Reads the cleaned team and player data, computes the deltas that the
README headline references, and prints summary tables. The intent is
that you can re-run this script after each playoff game and immediately
see how the WCF series is tracking vs the regular-season H2H pattern.

Outputs:
  - data/analysis_summary.csv  (flat player-metric table for README citations)
"""

from __future__ import annotations

import math
from math import comb
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

def player_delta_table(
    player_h2h: pd.DataFrame,
    season_avg: pd.DataFrame,
    season_type: str = "Regular Season",
) -> pd.DataFrame:
    """Long-form table: one row per (player, metric) with season / H2H / delta.

    `season_type` filters the H2H rows to that slice ("Regular Season" or
    "Playoffs"). The season-average baseline is always the player's
    full-regular-season mean (set in 01_fetch_data.py).
    """
    h2h = player_h2h[player_h2h["SEASON_TYPE"] == season_type].copy()
    if h2h.empty:
        return pd.DataFrame()
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
    """Aggregate four factors + ratings across H2H games, by team and slice.

    Regular Season and Playoffs are kept separate (rather than mashed
    together) because the whole project's question is about how the two
    samples diverge.
    """
    slices = []
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


def predicted_vs_observed(team_clean: pd.DataFrame, player_clean: pd.DataFrame) -> pd.DataFrame:
    """Side-by-side: regular-season H2H expectation vs playoff H2H actual.

    Returns rows for both teams' four factors / ratings AND for each
    tracked player's key metrics. Empty if no playoff H2H games exist.

    The "expectation" framing: what the regular-season sample predicted.
    The "actual" framing: what's been observed in the WCF so far.
    DELTA > 0 means the playoff actual is *higher* than the regular-season
    expectation; sign is the same on both sides.
    """
    po_team = team_clean[team_clean["SEASON_TYPE"] == "Playoffs"]
    if po_team.empty:
        return pd.DataFrame()

    rows: list[dict] = []

    # Team-level four factors / ratings
    for team_abbr in ("SAS", "OKC"):
        reg = team_clean[(team_clean["TEAM_ABBREVIATION"] == team_abbr) & (team_clean["SEASON_TYPE"] == "Regular Season")]
        po  = team_clean[(team_clean["TEAM_ABBREVIATION"] == team_abbr) & (team_clean["SEASON_TYPE"] == "Playoffs")]
        if reg.empty or po.empty:
            continue
        for metric in TEAM_METRICS:
            rows.append({
                "SUBJECT": team_abbr,
                "METRIC":  metric,
                "EXPECTED": reg[metric].mean(),
                "ACTUAL":   po[metric].mean(),
                "DELTA":    po[metric].mean() - reg[metric].mean(),
                "EXP_N":    int(len(reg)),
                "ACT_N":    int(len(po)),
            })

    # Player-level (only metrics present on both sides)
    reg_player = player_clean[player_clean["SEASON_TYPE"] == "Regular Season"]
    po_player  = player_clean[player_clean["SEASON_TYPE"] == "Playoffs"]
    for name in po_player["PLAYER_LABEL"].unique():
        reg_p = reg_player[reg_player["PLAYER_LABEL"] == name]
        po_p  = po_player[po_player["PLAYER_LABEL"] == name]
        if reg_p.empty or po_p.empty:
            continue
        for metric in PLAYER_METRICS:
            if metric not in po_p.columns or metric not in reg_p.columns:
                continue
            rows.append({
                "SUBJECT": name,
                "METRIC":  metric,
                "EXPECTED": reg_p[metric].mean(),
                "ACTUAL":   po_p[metric].mean(),
                "DELTA":    po_p[metric].mean() - reg_p[metric].mean(),
                "EXP_N":    int(len(reg_p)),
                "ACT_N":    int(len(po_p)),
            })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Simple series prediction
# ---------------------------------------------------------------------------

# Empirical NBA standard deviation of single-game point margin around the
# expected value. A defensible default in the 11-14 range; 13 is what the
# 2024-25 regular-season residuals worked out to. Lower SD = more confident
# in the H2H sample; higher SD = more humble.
DEFAULT_MARGIN_SD = 13.0


def _norm_cdf(z: float) -> float:
    """Standard-normal CDF using math.erf — avoids a scipy dependency."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _series_win_prob(p_game: float, wins: int = 0, losses: int = 0, length: int = 7) -> float:
    """P(team wins a best-of-`length` series given current state and per-game prob).

    Uses the negative-binomial formulation: sum over series-ending paths of
    the probability that the team gets its `need`-th win on the n-th remaining
    game.
    """
    target = (length + 1) // 2  # 4 for best-of-7
    need = target - wins
    opp_need = target - losses
    if need <= 0:
        return 1.0
    if opp_need <= 0:
        return 0.0
    total = 0.0
    for n in range(need, need + opp_need):
        total += comb(n - 1, need - 1) * (p_game ** need) * ((1 - p_game) ** (n - need))
    return total


def predict_series(team_clean: pd.DataFrame, margin_sd: float = DEFAULT_MARGIN_SD) -> dict[str, str]:
    """Predict P(SAS wins next game) and P(SAS wins series) from H2H sample.

    Margin estimate uses ALL H2H games available (regular + playoff so far);
    series probability conditions on the current playoff state.

    Method (called out so the README can cite it honestly):
      1. avg_margin = mean of SAS's per-game point margin in H2H games
      2. p_game = normal CDF of (avg_margin / margin_sd) — i.e., P(margin > 0)
      3. p_series = P(SAS wins 4 before OKC, given current state) via the
         negative-binomial formula
    """
    sas = team_clean[team_clean["TEAM_ABBREVIATION"] == "SAS"]
    sas_reg = sas[sas["SEASON_TYPE"] == "Regular Season"]
    sas_po  = sas[sas["SEASON_TYPE"] == "Playoffs"]

    sas_po_wins   = int((sas_po["WL"] == "W").sum())
    sas_po_losses = int((sas_po["WL"] == "L").sum())

    if sas_po.empty:
        sample = sas_reg
        sample_desc = f"{len(sas_reg)} regular-season H2H games"
    else:
        sample = sas
        sample_desc = f"{len(sas_reg)} regular-season + {len(sas_po)} playoff H2H games"

    avg_margin = sample["MARGIN"].mean()
    p_game     = _norm_cdf(avg_margin / margin_sd)
    p_series   = _series_win_prob(p_game, sas_po_wins, sas_po_losses)

    return {
        "Sample":                    sample_desc,
        "Avg SAS margin (pts/game)": f"{avg_margin:+.1f}",
        "Margin SD assumed":         f"{margin_sd:.1f}",
        "P(SAS wins next game)":     f"{p_game:.1%}",
        "Current series state":      f"SAS {sas_po_wins}-{sas_po_losses} OKC",
        "P(SAS wins series)":        f"{p_series:.1%}",
    }


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


def _delta_cell(delta: float, kind: str) -> str:
    """Format a single delta value with the right unit and sign."""
    if pd.isna(delta):
        return "—"
    if kind == "pct":
        return f"{delta*100:+.1f} pp"
    if kind == "rate":
        return f"{delta:+.3f}"
    return f"{delta:+.1f}"


def _format_player_delta(deltas: pd.DataFrame) -> str:
    """Wide format: one row per player, one column per metric (delta values).

    Absolute Season / H2H values are intentionally not shown here — they're
    available in data/analysis_summary.csv when you need them. This view is
    optimized for scanning the *surprise* across all metrics at a glance.
    """
    if deltas.empty:
        return "(no delta data)"

    metric_order = [m for m in PLAYER_METRICS if m in deltas["METRIC"].values]

    rows = []
    for player, group in deltas.groupby("PLAYER", sort=False):
        team = group["TEAM"].iloc[0]
        row = {"PLAYER": player, "TEAM": team}
        for metric in metric_order:
            sub = group[group["METRIC"] == metric]
            if sub.empty:
                row[METRIC_DISPLAY[metric][1]] = "—"
                continue
            kind, label = METRIC_DISPLAY.get(metric, ("float1", metric))
            row[label] = _delta_cell(sub.iloc[0]["DELTA"], kind)
        row["H2H N"] = int(group["H2H_N"].iloc[0])
        rows.append(row)
    out = pd.DataFrame(rows)

    return tabulate(
        out, headers="keys", tablefmt=TFMT, showindex=False,
        disable_numparse=True,
        colalign=("left", "center") + ("right",) * (len(out.columns) - 2),
    )


def _format_predicted_vs_observed(df: pd.DataFrame) -> str:
    """Reg-season H2H expectation vs Playoff H2H actual, grouped by subject."""
    if df.empty:
        return "(no playoff H2H games yet — this table populates after Game 1)"

    rows = []
    for _, r in df.iterrows():
        kind, label = METRIC_DISPLAY.get(r["METRIC"], ("float1", r["METRIC"]))
        if kind == "pct":
            delta_str = f"{(r['DELTA'])*100:+.1f} pp"
        elif kind == "rate":
            delta_str = f"{r['DELTA']:+.3f}"
        else:
            delta_str = f"{r['DELTA']:+.1f}"
        rows.append({
            "SUBJECT":  r["SUBJECT"],
            "METRIC":   label,
            "EXPECTED": _fmt(r["EXPECTED"], kind),
            "ACTUAL":   _fmt(r["ACTUAL"], kind),
            "Δ":        delta_str,
            "EXP N":    r["EXP_N"],
            "ACT N":    r["ACT_N"],
        })
    out = pd.DataFrame(rows)
    table = tabulate(
        out, headers="keys", tablefmt=TFMT, showindex=False,
        disable_numparse=True,
        colalign=("left", "left", "right", "right", "right", "right", "right"),
    )
    lines = table.split("\n")
    top, header, sep = lines[0], lines[1], lines[2]
    *data_lines, bottom = lines[3:]
    grouped = [top, header, sep]
    prev = None
    for line, subj in zip(data_lines, out["SUBJECT"]):
        if prev is not None and subj != prev:
            grouped.append(sep)
        grouped.append(line)
        prev = subj
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

def headline_numbers(
    reg_player_deltas: pd.DataFrame,
    team_clean: pd.DataFrame,
    po_player_deltas: pd.DataFrame | None = None,
    pred_vs_obs: pd.DataFrame | None = None,
) -> dict[str, str]:
    """Boil it down to the few numbers the README opens with.

    Always emits the regular-season headline (SGA TS% drop, SAS record).
    When playoff H2H data exists, also emits the playoff actuals + the
    deltas vs the regular-season H2H expectation.
    """
    out: dict[str, str] = {}

    sga_ts = reg_player_deltas[(reg_player_deltas.PLAYER == "Shai Gilgeous-Alexander") & (reg_player_deltas.METRIC == "TS_PCT")]
    if not sga_ts.empty:
        r = sga_ts.iloc[0]
        out["sga_ts_season"]    = f"{r['SEASON_AVG']:.1%}"
        out["sga_ts_reg_h2h"]   = f"{r['H2H_AVG']:.1%}"
        out["sga_ts_delta_pp"]  = f"{(r['DELTA'])*100:+.1f}"
        out["sga_reg_h2h_n"]    = str(r['H2H_N'])

    sas_reg = team_clean[(team_clean.TEAM_ABBREVIATION == "SAS") & (team_clean.SEASON_TYPE == "Regular Season")]
    out["sas_reg_record"]      = f"{(sas_reg['WL']=='W').sum()}-{(sas_reg['WL']=='L').sum()}"
    out["sas_reg_avg_margin"]  = f"{sas_reg['MARGIN'].mean():+.1f}"
    out["sas_reg_net_rating"]  = f"{sas_reg['NET_RATING'].mean():+.1f}"

    restricted = sas_reg[sas_reg["wemby_status"] == "restricted"]
    if not restricted.empty:
        out["sas_record_wemby_restricted"] = f"{(restricted['WL']=='W').sum()}-{(restricted['WL']=='L').sum()}"
        out["wemby_restricted_n"] = str(len(restricted))

    # Playoff side (only when at least one WCF H2H game exists)
    if po_player_deltas is not None and not po_player_deltas.empty:
        sga_po = po_player_deltas[(po_player_deltas.PLAYER == "Shai Gilgeous-Alexander") & (po_player_deltas.METRIC == "TS_PCT")]
        if not sga_po.empty:
            r = sga_po.iloc[0]
            out["sga_ts_po_h2h"]               = f"{r['H2H_AVG']:.1%}"
            out["sga_ts_po_h2h_n"]             = str(r['H2H_N'])
            out["sga_ts_po_vs_season_pp"]      = f"{(r['DELTA'])*100:+.1f}"

    if pred_vs_obs is not None and not pred_vs_obs.empty:
        sga_pvo = pred_vs_obs[(pred_vs_obs.SUBJECT == "Shai Gilgeous-Alexander") & (pred_vs_obs.METRIC == "TS_PCT")]
        if not sga_pvo.empty:
            r = sga_pvo.iloc[0]
            out["sga_ts_po_vs_reg_h2h_pp"] = f"{(r['DELTA'])*100:+.1f}"
        sas_nr = pred_vs_obs[(pred_vs_obs.SUBJECT == "SAS") & (pred_vs_obs.METRIC == "NET_RATING")]
        if not sas_nr.empty:
            r = sas_nr.iloc[0]
            out["sas_netrtg_po_vs_reg_h2h"] = f"{r['DELTA']:+.1f}"

        sas_po_team = team_clean[(team_clean.TEAM_ABBREVIATION == "SAS") & (team_clean.SEASON_TYPE == "Playoffs")]
        if not sas_po_team.empty:
            out["sas_po_record"]    = f"{(sas_po_team['WL']=='W').sum()}-{(sas_po_team['WL']=='L').sum()}"
            out["sas_po_avg_margin"] = f"{sas_po_team['MARGIN'].mean():+.1f}"

    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    team = pd.read_csv(TEAM_CLEAN)
    player = pd.read_csv(PLAYER_CLEAN)
    season_avg = pd.read_csv(PLAYER_SEASON_AVG)

    reg_deltas    = player_delta_table(player, season_avg, season_type="Regular Season")
    po_deltas     = player_delta_table(player, season_avg, season_type="Playoffs")
    team_summary  = team_h2h_summary(team)
    pred_vs_obs   = predicted_vs_observed(team, player)
    split         = wemby_status_split(team)
    prediction    = predict_series(team)
    headline      = headline_numbers(reg_deltas, team, po_deltas, pred_vs_obs)

    reg_deltas.to_csv(SUMMARY_OUT, index=False)
    print(f"Wrote {len(reg_deltas)} player-metric rows to {SUMMARY_OUT.relative_to(DATA_DIR.parent)}")

    _print_titled("Headline numbers:", "\n".join(f"  {k:32s} = {v}" for k, v in headline.items()))
    _print_titled("Player H2H vs season averages (Regular Season):", _format_player_delta(reg_deltas))
    if not po_deltas.empty:
        _print_titled("Player H2H vs season averages (Playoffs):", _format_player_delta(po_deltas))
    _print_titled("Team H2H four factors + ratings (aggregated):", _format_team_summary(team_summary))
    _print_titled("Reg-season H2H expectation vs Playoff H2H actual:", _format_predicted_vs_observed(pred_vs_obs))
    _print_titled("SAS results by Wemby status (regular season H2H):", _format_wemby_split(split))
    _print_titled(
        "Series prediction (live; re-runs with each new H2H game):",
        tabulate(
            [(k, v) for k, v in prediction.items()],
            headers=["Metric", "Value"],
            tablefmt=TFMT, disable_numparse=True,
            colalign=("left", "right"),
        ),
    )


if __name__ == "__main__":
    main()
