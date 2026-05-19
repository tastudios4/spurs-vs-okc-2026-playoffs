# Spurs vs Thunder — 2026 Western Conference Finals

*A regular-season-vs-playoff analytics study, updated game-by-game.*

## The question

The San Antonio Spurs went **4-1** against the Oklahoma City Thunder in five
regular season meetings during the 2025-26 season.
OKC is the defending West-leading powerhouse built around back-to-back MVP
Shai Gilgeous-Alexander, and the Spurs are the league's youngest contender
with DPOY candidate Victor Wembanyama anchoring the defense.

May 18, 2026 the two teams open the Western Conference Finals.

This repo asks a single question:

> **Based on those five regular-season games, what should we actually expect
> in this series and which of the regular-season patterns are predictive
> versus noise?**

## Headline finding

The single strongest signal in the H2H sample isn't Wembanyama's box score
— it's **Shai Gilgeous-Alexander's shooting efficiency collapsing against
the Spurs at unchanged usage**.

| | Season avg (n=68) | vs SAS (n=4) | Δ |
|---|---:|---:|---:|
| Usage rate | 32.1% | 31.8% | −0.3 pp |
| **True shooting %** | **68.2%** | **58.7%** | **−9.5 pp** |
| Effective FG % | 61.9% | 52.4% | −9.5 pp |
| Net rating (on/off) | +17.5 | −1.4 | **−18.9** |

Same shot diet, way worse shots going in. eFG% and TS% drop the same
amount, ruling out a free-throw-driven artifact — this is pure shot
quality, the fingerprint of a high-end interior defense in front of him.

That alone reframes the series. SGA is the best player on the floor either
way, but a meaningful share of OKC's +9.4 regular-season Net Rating
depends on him being a 68%-TS scorer. Against this specific defense, in
this specific sample, he hasn't been.

## What we should expect in the WCF

A few claims of varying confidence:

1. **High confidence:** SGA's efficiency against this defense is genuinely
   suppressed (replicated across 4 separate games, same direction every
   time). Expect his TS% to land 5-10 pp below his season norm in the WCF.
2. **Medium confidence:** The team-level series is closer than 4-1
   suggests. SAS averaged a +5.4 Net Rating across the five games — the
   point differential says **coin-flip-plus-a-bit**, not blowout
   favorite. Three Spurs wins were by 15+; one was by 2.
3. **Low confidence:** That a healthy Wembanyama widens the gap. Three of
   the five H2H games happened during his post-calf-strain minutes
   restriction, and SAS won those by *more* on average (+12.3) than the
   one game where he was at normal minutes (+10). Tiny sample, but it
   doesn't support the obvious "Wemby is back, brace for impact" framing.

## Methodology

**Data source:** the `nba_api` Python package, pulling team and player
game logs straight from `stats.nba.com`.

**Sample:** five regular-season Spurs vs Thunder games (Dec 13, 23, 25;
Jan 13; Feb 4 — see [Per-game context](#per-game-context) below). One
of those (Dec 13) was the NBA Cup semifinal — played at T-Mobile Arena
in Las Vegas under playoff-intensity rotations, with a winner-advances
stake. It counts for the regular-season record but is flagged separately.

**Player baselines:** for SGA and Wemby, each player's per-game averages
across all of their regular-season games (n=68 and n=64 respectively).
Computed straight from `playergamelogs` (Base + Advanced measure types),
*excluding* playoff games so the baseline stays stable to compare H2H
games against.

**Derived team stats** (`02_clean.py`):

- **Possessions**, via the basketball-reference simplified formula:
  `POSS = FGA + 0.44·FTA − OREB + TOV`, averaged across both teams.
- **Pace**: possessions per 48 minutes.
- **Off / Def / Net Rating**: points per 100 possessions (so pace doesn't
  confound efficiency).
- **Four factors** (Dean Oliver, 2003): eFG%, TOV%, OREB%, FT rate.

**Context flags** on each game: `wemby_status`
(`restricted`/`ramping`/`normal`), `sga_played` (False on Feb 4),
`is_cup_knockout`, `is_neutral_site`, `is_blowout` (|margin| ≥ 10).

## Per-game context

| Date | Matchup | Margin (SAS) | Wemby | SGA | Cup | Neutral |
|---|---|---:|---|---|---|---|
| 2025-12-13 | SAS @ OKC | +2 | restricted¹ | played | yes (SF) | yes |
| 2025-12-23 | SAS vs. OKC | +20 | restricted¹ | played | — | — |
| 2025-12-25 | SAS @ OKC | +15 | restricted¹ | played | — | — |
| 2026-01-13 | SAS @ OKC | −21 | ramping | played | — | — |
| 2026-02-04 | SAS vs. OKC | +10 | normal | DNP | — | — |

¹ *Wemby missed 12 games from Nov 14 to Dec 12 with a left calf strain
(diagnosed Nov 17, returned Dec 13 in the Cup semi on a strict minutes
restriction; ramp continued through Dec 25). Sources:
[NBA.com](https://www.nba.com/news/spurs-victor-wembanyama-out-calf-strain),
[Bleacher Report](https://bleacherreport.com/articles/25254645-victor-wembanyama-injury-update-latest-news-spurs-star-and-timeline-return),
[Sports Illustrated](https://www.si.com/nba/spurs/onsi/news/wembanyama-s-injury-highlights-absurdity-of-65-game-minimum-for-awards).*

## Charts

*Will be embedded after `04_charts.py` is built (post-Game 1, so the
first chart can include playoff data side-by-side with regular season).*

## Limitations

- **n = 5.** Five games is below the threshold where any single-stat
  delta should be taken as a stable estimate. The SGA TS% drop replicates
  across all four games he played (every single one was below his season
  norm), which is the strongest defense against "this is random." The
  team-level four-factor splits don't replicate as cleanly.
- **One game is missing SGA.** The Feb 4 result (SAS +10) is real, but
  it isn't evidence of how OKC plays *with* SGA. The 4-1 series record
  is better understood as 3-1 with SGA + 1-0 without him.
- **Three games are missing healthy Wemby.** Three of the five fell
  inside his post-injury minutes restriction. His per-minute production
  was intact, but the team-level dynamics in the absence of his usual
  ~34 MPG of rim protection are different.
- **One game is neutral-site, near-playoff intensity.** The Dec 13 Cup
  semifinal had no home court advantage and was played with shorter,
  starter-heavy rotations. Treating it as a "regular" regular-season
  game would over-credit SAS for an away win that wasn't really away.
- **Season averages don't adjust for opponent strength.** SGA's 68.2% TS
  was earned against an average NBA defense; the Spurs aren't an
  average defense. Some of the −9.5 pp delta is opponent-strength
  signal, but it's hard to isolate without per-game opponent-adjusted
  stats.

## Repo layout

```
scripts/
  01_fetch_data.py   # pull from nba_api, cache to data/ (idempotent)
  02_clean.py        # add context flags + derive four factors / ratings
  03_analyze.py      # H2H vs season-avg deltas + Wemby-status split
  04_charts.py       # write PNGs to charts/ (TBD)
data/                # cached + derived CSVs (committed for reproducibility)
charts/              # output PNG/SVG
analysis/            # optional Jupyter exploration
```

## Running it

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python scripts/01_fetch_data.py   # safe to re-run; updates the cache
python scripts/02_clean.py
python scripts/03_analyze.py
```

`01_fetch_data.py` also exposes `add_playoff_game(game_id)` for adding a
single WCF box score in-place; the full re-run path above is what gets
called after each game during the series.

## Series predictions log

Each row is a snapshot of the live prediction from `03_analyze.py`,
captured **after** the corresponding trigger event (a new H2H game).
The first row is the pre-WCF baseline; every subsequent row is what the
model thinks heading into the next game, given everything observed so far.

Predictions are deliberately simple: avg per-game H2H margin → normal CDF
with a 13-pt single-game margin SD → per-game P → negative-binomial
rollup to series probability conditioned on the current playoff state.
Method docstring is in `predict_series()` in `scripts/03_analyze.py`.

| Snapshot | Trigger | Sample | P(SAS next game) | Series state | P(SAS series) |
|---|---|---|---|---|---|
| Pre-WCF (no PO data) | — | 5 reg + 0 PO | 65.5% | SAS 0-0 OKC | 80.9% |

After each WCF game, re-run `python scripts/03_analyze.py` — the script
prints a copy-pasteable markdown row to append to this table.

## Per-game result log

| Game | Date | Score | Notable swings vs regular-season expectation |
|---|---|---|---|
| 1 | 2026-05-18 | *TBD — game in progress at time of writing* | — |

*Filled in after each game.*
