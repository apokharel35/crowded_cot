What each label means

ES / NQ – E-mini S&P 500 / E-mini Nasdaq-100.

AM – Asset Managers (real-money).

LF – Leveraged Funds (CTAs/specs).

(Optional extras you enabled) DI = Dealers, OR = Other Reportables, NR = Non-Reportables.

The line you’ll see

```bash
ES: AM z=+0.89 (pct 66th, conf3w False); LF z=-0.77 (pct 13th, conf3w True)
  TRADE: YES (LONG) — LF extreme short confirmed 3w
```

How to read it (in order)

TRADE:

YES (LONG) → specs (LF) are crowded short (or your rules say so) and that signal held for the last confirm-weeks.

YES (SHORT) → real-money (AM) are crowded long and confirmed.

YES (CONFLICT) → both sides extreme; review manually.

NO → no confirmed extreme.

Percentile (pct): how today’s net position ranks vs the past window (lookback-weeks).

Rough guide (defaults): ≥90th = crowded long, ≤10th = crowded short.

z-score (z): how many standard deviations from “typical”.

Rough guide: ±2 ≈ extreme. Use it alongside pct (some people key off whichever triggers first).

conf3w True/False: the signal (AM long or LF short) has been true for 3 consecutive reports (or whatever you set with --confirm-weeks).

Confirmation is a simple “held for N weeks” check to avoid one-week blips.

AM vs LF roles:

AM crowded long → contrarian short setup.

LF crowded short → contrarian long setup.

Use with price: wait for a news-failure (market moves against the headline) to time entries; use the reversal bar/level for risk.

Quick examples

LF z=-2.3 (pct 4th, conf2w True) → specs very short and it persisted → contrarian long backdrop.

AM z=+2.1 (pct 96th, conf2w False) → real-money very long but not confirmed → watch, not a green light yet.

Why you might see nan

Not enough history to compute a z-score (needs at least min-required-weeks, default ~156).

Fix: start earlier or run with --lookback-weeks 52 --min-required-weeks 26 for short spans.

Percentiles can still show with short history; z-scores need more data.

Default thresholds (changeable)

Crowding by percentile: --am-long-pct 90, --lf-short-pct 10.

Crowding by z: --extreme-threshold 2.0 (AM ≥ +2, LF ≤ −2).

Confirmation: --confirm-weeks 2.

History window: --lookback-weeks 260 (~5y), minimum to compute z: --min-required-weeks 156 (~3y).

One-sentence cheat sheet

LONG bias when LF is at/under your short percentile or z ≤ −threshold and confirmed;

SHORT bias when AM is at/above your long percentile or z ≥ +threshold and confirmed;

then wait for a news-failure price tell to actually pull the trigger.