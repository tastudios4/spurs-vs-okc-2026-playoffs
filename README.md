# Spurs vs Thunder — 2026 Western Conference Finals

*A regular-season-vs-playoff analytics study, updated game-by-game.*

> **Status:** Setup in progress. Headline finding and charts will be filled in once
> the regular-season data has been fetched and analyzed.

## The question

The San Antonio Spurs went **4-1** against the Oklahoma City Thunder in five
regular season meetings during the 2025-26 season — an unusual result, given
OKC is the defending West-leading powerhouse built around back-to-back MVP
Shai Gilgeous-Alexander, and the Spurs are the league's youngest contender
with DPOY candidate Victor Wembanyama anchoring the defense.

Tonight (May 18, 2026), the two teams open the Western Conference Finals.

This repo asks a single question:

> **Based on those five regular-season games, what should we actually expect
> in this series — and which of the regular-season patterns are predictive
> versus noise?**

## Headline finding

*To be filled in after analysis.*

## Methodology

*To be filled in.*

## Charts

*Embedded after `04_charts.py` runs.*

## Limitations

*To be filled in. (Spoiler: n=5 is a tiny sample.)*

## Repo layout

```
scripts/
  01_fetch_data.py   # pull from nba_api, cache to data/
  02_clean.py        # tidy + derive advanced stats
  03_analyze.py      # H2H vs season-avg comparisons
  04_charts.py       # write PNGs to charts/
data/                # cached CSVs (committed for reproducibility)
charts/              # output PNG/SVG
analysis/            # optional Jupyter exploration
```

## Running it

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python scripts/01_fetch_data.py   # idempotent; safe to re-run
python scripts/02_clean.py
python scripts/03_analyze.py
python scripts/04_charts.py
```

## Series log (updated after each game)

*Will be appended after each WCF game.*
