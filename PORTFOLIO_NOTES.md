# Portfolio notes

A standalone context document for this project — useful as:

- A self-contained briefing for recruiters, hiring managers, or anyone
  reviewing the work
- Source material for resume bullets and interview talking points
- A reference for myself to remember the analytical and engineering
  decisions I made

---

## Project

**Title:** Spurs vs Thunder — 2026 Western Conference Finals analysis
**Repo:** https://github.com/tastudios4/spurs-vs-okc-2026-playoffs
**My background:** Software engineer transitioning into the sports analytics
industry. This is my first sports analytics project, built as a portfolio
piece during the WCF (started May 18, 2026).

## The analytical question

The San Antonio Spurs went 4-1 against the Oklahoma City Thunder in five
regular-season games. The Thunder are the defending West powerhouse with
back-to-back MVP Shai Gilgeous-Alexander; the Spurs are built around DPOY
candidate Victor Wembanyama. Based on those five games, what should we
expect in the WCF — and which patterns are predictive vs noise?

## Stack and engineering

- **Python 3.9** (venv), pandas, numpy, **nba_api** (NBA Stats endpoints), tabulate
- 4-stage numbered pipeline: `01_fetch_data` → `02_clean` → `03_analyze` → `04_charts`
- **Makefile** so per-game updates are one command (`make`)
- All cached data committed for **reproducibility** (no API hits for re-runs)
- Idempotent design: `add_playoff_game(game_id)` helper + a **WL-flag filter**
  that excludes live in-progress games from analysis (caught a real bug
  where a 22-22 Q1 snapshot was contaminating the prediction)
- Git / GitHub, VS Code; runnable on any machine via `make setup`

## Analytical content

### Derived stats from raw box scores (in `02_clean.py`)

- **Possessions** via basketball-reference simplified formula
  (`POSS = FGA + 0.44·FTA − OREB + TOV`, averaged across both teams)
- **Pace** (poss / 48 min), **OffRtg / DefRtg / NetRtg** (per 100 poss)
- **Dean Oliver's four factors**: eFG%, TOV%, OREB%, FT rate

### Context flags to support honest comparisons

- `wemby_status` — `restricted` / `ramping` / `normal`, tied to his Nov 2025
  calf strain (verified via news search: NBA.com, Bleacher Report, SI)
- `sga_played` — False on one H2H game (Feb 4 DNP)
- `is_cup_knockout`, `is_neutral_site` — Dec 13 NBA Cup semifinal at
  T-Mobile Arena, played under playoff-intensity rotations
- `is_blowout` — `|margin| ≥ 10`

### Comparison tables (in `03_analyze.py`)

- **Player deltas**: SGA / Wemby H2H vs full-season averages (wide format,
  one row per player, one column per metric)
- **Team H2H aggregated four factors**, split by Regular Season vs Playoff
- **Predicted-vs-observed**: regular-season H2H expectation vs playoff H2H
  actual, with deltas on every metric
- **SAS results split by Wemby's health status** (3 games restricted, 1
  ramping, 1 normal)

### Live series prediction

- Average H2H margin → standard-normal CDF (13-pt empirical NBA single-game
  margin SD) → per-game P → **negative-binomial rollup** conditioned on the
  current series state (Bo7, target=4)
- Auto-updates with each new H2H game; prints a copy-pasteable markdown row
  for the README's series-predictions log

## Key analytical findings

1. **Headline:** SGA's True Shooting % dropped **9.5 percentage points**
   against the Spurs (68.2% season → 58.7% H2H) at unchanged usage. eFG%
   dropped the same amount, ruling out a free-throw-driven artifact — pure
   shot quality, the fingerprint of a high-end interior defense.
2. SGA's on-court Net Rating swung **−18.9** (from +17.5 season to −1.4
   vs SAS).
3. Wemby's per-minute production was essentially identical in H2H games
   (USG −1.0 pp, eFG **−0.1 pp**); his lower volume was entirely a minutes
   story (he played 4 fewer MPG, attributable to the calf injury + 3 SAS
   blowouts).
4. The Wemby calf injury confounds 3 of the 5 H2H games — important
   context for any "what to expect in WCF" claim.
5. **Counter-intuitive:** SAS performed *better* against OKC with Wemby
   restricted (+12.3 avg margin in 3 games) than at normal minutes (+10
   in 1 game) — the (tiny) sample rejects the obvious "healthy Wemby
   widens the gap" hypothesis.
6. **Pre-WCF live prediction:** SAS 65.5% per game, 80.9% for the series.

## What I want to be honest about

- n=5 is a tiny sample; the SGA TS% drop replicates across all 4 games
  he played in, which is its strongest defense against being noise
- Three of five games had Wemby on injury restriction
- One game was missing SGA (DNP Feb 4)
- One game was at a neutral site (NBA Cup semifinal)
- No opponent-strength adjustment in the player baselines

## What's still open (post-Game-1 work)

- `04_charts.py` — visual artifacts (margin chart, stat-shift heatmap,
  player scatter)
- More rotation players in `TRACKED_PLAYERS` (Holmgren, Castle, Vassell,
  J. Williams)
- Team season averages (currently only player season averages exist as
  baselines)

## How to use this doc

Share it with anyone who needs project context quickly — a recruiter, a
hiring manager, a reference, an interviewer. It's designed to stand on
its own without requiring the reader to clone the repo or read the code.

For my own use, this is also the doc I work from when drafting resume
bullets, interview talking points, or portfolio-page copy — everything
the resume cites is sourced from claims here.
