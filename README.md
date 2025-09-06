# crowded_cot

Contrarian positioning signals from the CFTC **Commitments of Traders — Traders in Financial Futures (TFF)** data for index futures (**E-mini S&P 500** and **E-mini Nasdaq-100**).

The tool:
- Pulls TFF data for **ES** and **NQ** from the official CFTC Socrata API  
- Computes **Net % of Open Interest** for **Asset Managers (AM)** and **Leveraged Funds (LF)**  
- Normalizes via **rolling z-scores** and **percentile ranks**  
- Flags **crowding extremes** with user-tunable thresholds and **N-week confirmation**  
- Prints a clear human summary and writes tidy **CSV/JSON**

> Trading philosophy: look for **crowded positioning** + may be a **news-failure** (price moves opposite the catalyst) for contrarian entries, with tight invalidation.

---

## Quick Start

```bash
# 1) From repo root
python -m venv .venv
source .venv/bin/activate
pip install -U pip pandas numpy requests python-dateutil

# 2) Latest 5y view (default 260-week window)
crowded-cot cftc --start-date 2018-01-01   --output-csv out/es_nq_5y.csv   --output-json out/es_nq_5y.json
```

Example console output:
```
Latest report date: 2025-09-02
ES: AM z=+1.14 (pct 80th, conf2w False); LF z=-0.76 (pct 14th, conf2w False)
  TRADE: NO
NQ: AM z=-0.99 (pct 9th, conf2w False); LF z=+0.44 (pct 69th, conf2w False)
  TRADE: NO
```

---

## Installation

```bash
git clone <your-repo-url>
cd crowded_cot
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install pandas numpy requests python-dateutil
```

If the `crowded-cot` command isn’t on your PATH, run via module:
```bash
python -m crowded_cot.cli --help
```

---

## Data Source (CFTC Socrata)

- **Host**: `https://publicreporting.cftc.gov`  
- **Dataset**: **TFF – Futures Only**, id **`gpe5-46if`** (this is the default wired in code)

> ⚠️ Don’t mix dataset ids and domains. The HUB dataset (`yw9f-hn96`) lives on `https://publicreportinghub.cftc.gov` and won’t work unless you also change the base URL in code.

**Optional:** If you have a Socrata app token:
```bash
--api-token "<YOUR_TOKEN>"
```

---

## What the Tool Computes

For each contract (**ES**, **NQ**):

1) **Net % of Open Interest** for a group **G** (AM or LF)
```
G_net_pct_oi = 100 * (G_long − G_short) / open_interest
```

2) **Rolling z-score** over `--lookback-weeks` (default: 260 ≈ 5y).  
   Implementation uses `ddof=1` and allows z-scores with ≥ **3y** of data to avoid NaNs.

3) **Percentile rank** (0–100, inclusive) of today’s net%OI within the trailing window.

4) **Crowding rules (user-tunable):**
- **AM crowded long** if `AM_pct ≥ --am-long-pct` **or** `AM_z ≥ --extreme-threshold`  
- **LF crowded short** if `LF_pct ≤ --lf-short-pct` **or** `LF_z ≤ −--extreme-threshold`  
- **Confirmation**: rule must hold for the last `--confirm-weeks` reports (default 2)

5) **TRADE decision**  
- `YES (LONG)` if **LF crowded short** is confirmed and AM isn’t simultaneously confirmed  
- `YES (SHORT)` if **AM crowded long** is confirmed and LF isn’t simultaneously confirmed  
- `YES (CONFLICT)` if both confirmed (manual review)  
- `NO` otherwise

---

## CLI Usage

### Subcommands
- `cftc` — load from the CFTC API  
- `csv`  — load from local CSVs you provide

### Common flags (both subcommands)
- `--output-csv PATH` Write tidy CSV  
- `--output-json PATH` Write tidy JSON  
- `--lookback-weeks N` Rolling window in weeks (default **260**)  
- `--extreme-threshold X` Z extreme (default **2.0**)  
- `--am-long-pct P` AM crowded-long percentile (default **90**)  
- `--lf-short-pct P` LF crowded-short percentile (default **10**)  
- `--confirm-weeks K` Consecutive weeks for confirmation (default **2**)

### `cftc` subcommand
- `--start-date YYYY-MM-DD` (required)  
- `--end-date YYYY-MM-DD` (optional; omit to pull through latest)  
- `--api-token TOKEN` (optional)  
- `--dataset-id` (optional; default is the futures-only dataset `gpe5-46if` on `publicreporting`)

**Examples**
```bash
# 5y window (defaults)
crowded-cot cftc --start-date 2018-01-01   --output-csv out/es_nq_5y.csv   --output-json out/es_nq_5y.json

# 3y window and stricter extremes + 3-week confirmation
crowded-cot cftc --start-date 2020-01-01   --lookback-weeks 156   --am-long-pct 95 --lf-short-pct 5 --extreme-threshold 2.5 --confirm-weeks 3   --output-csv out/es_nq_strict.csv   --output-json out/es_nq_strict.json
```

### `csv` subcommand (Local CSV mode)
```bash
crowded-cot csv   --path "./data/*.csv"   --lookback-weeks 260   --output-csv out/from_csv.csv   --output-json out/from_csv.json
```

**CSV expectations** (min columns):
- `report_date` (date), `market_name` (string)
- `open_interest`
- `asset_mgr_long`, `asset_mgr_short`
- `lev_fund_long`,  `lev_fund_short`
- If `contract` is missing, the loader infers it from `market_name`.

---

## Interpreting the Console Summary

```
ES: AM z=+0.89 (pct 66th, conf3w False); LF z=-0.77 (pct 13th, conf3w True)
  TRADE: YES (LONG) — LF extreme short confirmed 3w
NQ: AM z=-1.60 (pct 4th, conf3w False); LF z=+0.45 (pct 63th, conf3w False)
  TRADE: NO
```

- **AM/LF z** — how unusual today’s net%OI is vs its history (0 ~ normal, ±2 ~ extreme)  
- **pct** — inclusive percentile rank within the trailing window  
- **confKw** — whether the rule held for **K** consecutive reports  
- **TRADE** — directional suggestion per your thresholds and confirmation window

Pair this with a **news-failure** on catalyst days (CPI, NFP, FOMC, major earnings): if the headline is bearish yet price holds/rallies (or vice-versa), that’s your contrarian trigger with tight invalidation.

---

## Output Files

Both CSV and JSON include, per week and contract:

- `report_date, contract, market_name, open_interest`  
- Raw positions: `asset_mgr_long, asset_mgr_short, lev_fund_long, lev_fund_short`  
- Nets: `am_net_pct_oi, lf_net_pct_oi`  
- Normalized: `asset_mgr_z, lev_fund_z, asset_mgr_pct, lev_fund_pct`  
- Flags: `is_extreme_am_long, is_extreme_lev_short, is_confirmed_extreme_am_long, is_confirmed_extreme_lev_short`  
- `extreme_crowding` (legacy aggregate flag)

---

## Verify the Math (Copy/Paste)

This script independently recomputes **Net % OI**, **z-scores**, **percentiles**, and **signal flags**, then compares them to the tool’s output for the **latest week**.

> **How to run:** copy the whole block and paste into your terminal from the repo root (venv activated).

```bash
python - <<'PY'
# ===============================
# crowded_cot — verification tool
# ===============================
# 1) Loads raw CFTC data via your loader
# 2) Recomputes Net % OI, rolling z-scores, and percentile ranks independently
# 3) Re-applies your trade rules and confirmation window
# 4) Compares to crowded_cot.metrics output (latest week per contract)

import datetime as dt, numpy as np, pandas as pd
from crowded_cot.data_source import CftcPRELoader
from crowded_cot.metrics import compute_positioning_metrics

# -------- Tunables (match your CLI run) --------
START_DATE       = dt.date(2018, 1, 1)   # start far enough back
LOOKBACK_WEEKS   = 260                   # e.g., 260 (≈5y) or 156 (≈3y)
MIN_REQUIRED     = 156                   # allow z-scores with ≥3y data to avoid NaNs
EXTREME_Z        = 2.0                   # CLI: --extreme-threshold
AM_LONG_PCT      = 90.0                  # CLI: --am-long-pct
LF_SHORT_PCT     = 10.0                  # CLI: --lf-short-pct
CONFIRM_WEEKS    = 2                     # CLI: --confirm-weeks
TOL_Z            = 1e-6                  # z-score numeric tolerance
TOL_PCT          = 1e-6                  # percentile numeric tolerance
# -----------------------------------------------

def pct_rank_inc(window_vals: np.ndarray, x: float) -> float:
    vals = window_vals[~np.isnan(window_vals)]
    if vals.size == 0 or np.isnan(x):
        return np.nan
    return 100.0 * (np.searchsorted(np.sort(vals), x, side="right") / vals.size)

def rolling_stats(series: pd.Series, lookback: int, min_required: int) -> tuple[pd.Series, pd.Series]:
    min_required = min(lookback, min_required)
    mean = series.rolling(lookback, min_periods=min_required).mean()
    std  = series.rolling(lookback, min_periods=min_required).std(ddof=1)
    return mean, std

def rolling_pct(series: pd.Series, lookback: int) -> pd.Series:
    out = np.full(series.shape[0], np.nan, dtype=float)
    arr = series.to_numpy(dtype=float)
    for i in range(series.shape[0]):
        lo = max(0, i - lookback + 1)
        out[i] = pct_rank_inc(arr[lo:i+1], arr[i])
    return pd.Series(out, index=series.index, dtype=float)

# 1) Load raw + tool metrics
loader = CftcPRELoader(start_date=START_DATE)
raw = loader.load().sort_values(['contract','report_date']).reset_index(drop=True)
tool = compute_positioning_metrics(raw, threshold=EXTREME_Z, lookback_weeks=LOOKBACK_WEEKS)

if raw.empty or tool.empty:
    print("No data returned. Check your start date / connectivity.")
    raise SystemExit(0)

# 2) Independent recompute from raw
num_cols = ['open_interest','asset_mgr_long','asset_mgr_short','lev_fund_long','lev_fund_short']
for c in num_cols:
    raw[c] = pd.to_numeric(raw[c], errors='coerce')

oi = raw['open_interest'].replace(0, np.nan)
raw['am_net_pct_oi'] = 100.0 * (raw['asset_mgr_long'] - raw['asset_mgr_short']) / oi
raw['lf_net_pct_oi'] = 100.0 * (raw['lev_fund_long']  - raw['lev_fund_short'])  / oi

parts = []
for c, g in raw.groupby('contract', sort=False):
    g = g.copy()
    # AM
    am_mean, am_std = rolling_stats(g['am_net_pct_oi'], LOOKBACK_WEEKS, MIN_REQUIRED)
    g['asset_mgr_z_chk']   = (g['am_net_pct_oi'] - am_mean) / am_std
    g['asset_mgr_pct_chk'] = rolling_pct(g['am_net_pct_oi'], LOOKBACK_WEEKS)
    # LF
    lf_mean, lf_std = rolling_stats(g['lf_net_pct_oi'], LOOKBACK_WEEKS, MIN_REQUIRED)
    g['lev_fund_z_chk']    = (g['lf_net_pct_oi'] - lf_mean) / lf_std
    g['lev_fund_pct_chk']  = rolling_pct(g['lf_net_pct_oi'], LOOKBACK_WEEKS)
    # Rules (today-only flags; confirmation handled below)
    g['is_extreme_am_long_chk']  = (g['asset_mgr_pct_chk'] >= AM_LONG_PCT) | (g['asset_mgr_z_chk'] >= EXTREME_Z)
    g['is_extreme_lev_short_chk'] = (g['lev_fund_pct_chk'] <= LF_SHORT_PCT) | (g['lev_fund_z_chk'] <= -EXTREME_Z)
    parts.append(g)

chk = pd.concat(parts, ignore_index=True)

# 3) Compare latest week per contract
latest = tool['report_date'].max()
tool_latest = (tool[tool['report_date'] == latest]
               .sort_values(['contract','report_date'])
               .groupby('contract', as_index=False).tail(1).set_index('contract'))
chk_latest  = (chk[chk['report_date'] == latest]
               .sort_values(['contract','report_date'])
               .groupby('contract', as_index=False).tail(1).set_index('contract'))

contracts = sorted(tool_latest.index.unique())

print(f"Verify against latest week: {latest}\n")

def pretty(x): 
    return "nan" if (x is None or pd.isna(x)) else f"{x:.6f}"

mismatches = 0

for c in contracts:
    print(f"=== {c} ===")
    # z-scores
    z_am_tool = float(tool_latest.loc[c, 'asset_mgr_z'])
    z_lf_tool = float(tool_latest.loc[c, 'lev_fund_z'])
    z_am_chk  = float(chk_latest.loc[c, 'asset_mgr_z_chk'])
    z_lf_chk  = float(chk_latest.loc[c, 'lev_fund_z_chk'])
    dz_am = abs(z_am_tool - z_am_chk) if (pd.notna(z_am_tool) and pd.notna(z_am_chk)) else np.nan
    dz_lf = abs(z_lf_tool - z_lf_chk) if (pd.notna(z_lf_tool) and pd.notna(z_lf_chk)) else np.nan
    print(f" AM z  tool / chk : {pretty(z_am_tool)} / {pretty(z_am_chk)} (|Δ|={pretty(dz_am)})")
    print(f" LF z  tool / chk : {pretty(z_lf_tool)} / {pretty(z_lf_chk)} (|Δ|={pretty(dz_lf)})")

    # percentiles (if present in tool)
    am_pct_tool = tool_latest.get('asset_mgr_pct')
    lf_pct_tool = tool_latest.get('lev_fund_pct')
    if am_pct_tool is not None and lf_pct_tool is not None:
        p_am_tool = float(am_pct_tool.loc[c])
        p_lf_tool = float(lf_pct_tool.loc[c])
        p_am_chk  = float(chk_latest.loc[c, 'asset_mgr_pct_chk'])
        p_lf_chk  = float(chk_latest.loc[c, 'lev_fund_pct_chk'])
        dp_am = abs(p_am_tool - p_am_chk) if (pd.notna(p_am_tool) and pd.notna(p_am_chk)) else np.nan
        dp_lf = abs(p_lf_tool - p_lf_chk) if (pd.notna(p_lf_tool) and pd.notna(p_lf_chk)) else np.nan
        print(f" AM %  tool / chk : {pretty(p_am_tool)} / {pretty(p_am_chk)} (|Δ|={pretty(dp_am)})")
        print(f" LF %  tool / chk : {pretty(p_lf_tool)} / {pretty(p_lf_chk)} (|Δ|={pretty(dp_lf)})")

    # N-week confirmation check (match CLI rules exactly)
    g_tool = tool[tool['contract'] == c].sort_values('report_date').tail(CONFIRM_WEEKS)
    ok_am = ((g_tool['asset_mgr_pct'] >= AM_LONG_PCT) | (g_tool['asset_mgr_z'] >= EXTREME_Z)).fillna(False).astype(bool)
    ok_lf = ((g_tool['lev_fund_pct'] <= LF_SHORT_PCT) | (g_tool['lev_fund_z'] <= -EXTREME_Z)).fillna(False).astype(bool)
    am_conf_tool = bool(ok_am.all()) and (len(g_tool) == CONFIRM_WEEKS)
    lf_conf_tool = bool(ok_lf.all()) and (len(g_tool) == CONFIRM_WEEKS)
    print(f" conf{CONFIRM_WEEKS}w AM={am_conf_tool} LF={lf_conf_tool}")

    fail = False
    if pd.notna(dz_am) and dz_am > TOL_Z: fail = True
    if pd.notna(dz_lf) and dz_lf > TOL_Z: fail = True
    if am_pct_tool is not None and pd.notna(dp_am) and dp_am > TOL_PCT: fail = True
    if lf_pct_tool is not None and pd.notna(dp_lf) and dp_lf > TOL_PCT: fail = True
    print(" PASS" if not fail else " FAIL", "\n")
    mismatches += int(fail)

if mismatches == 0:
    print("All contracts match within tolerance.")
else:
    print(f"{mismatches} contract(s) exceeded tolerance. See diffs above.")
PY
```

**Good output:** tool/check values are nearly identical (tiny float differences ok), and confirmation booleans reflect your chosen thresholds and window.

If you see discrepancies:
- **NaN z-scores** → start earlier (e.g., `2018-01-01`) or ensure ≥3y of valid points in the window  
- **Sign issues** → confirm formula `Net%OI = 100*(long − short)/OI` for both AM and LF  
- **Percentile differences** → the script uses **inclusive** rank; ensure the tool does too  
- **Missing NQ** → extend market aliases if your dataset uses a slightly different name (e.g., `NASDAQ 100 E-MINI` vs `NASDAQ-100 E-MINI`)

---

## Popular Command Recipes

```bash
# Latest (5y), default extremes, 2-week confirm
crowded-cot cftc --start-date 2018-01-01   --output-csv out/latest.csv   --output-json out/latest.json

# 3y lens (156 weeks), looser extremes, 1-week confirm (exploratory)
crowded-cot cftc --start-date 2020-01-01   --lookback-weeks 156 --am-long-pct 85 --lf-short-pct 15 --confirm-weeks 1   --output-csv out/looser.csv   --output-json out/looser.json

# Stricter extremes & longer confirm for higher conviction
crowded-cot cftc --start-date 2018-01-01   --am-long-pct 95 --lf-short-pct 5 --extreme-threshold 2.5 --confirm-weeks 3   --output-csv out/strict.csv   --output-json out/strict.json
```

---

## Troubleshooting

**“No service found for this URL” / 404**  
You likely mixed domain/dataset. With current code, use:
- Domain: `https://publicreporting.cftc.gov`
- Dataset: `gpe5-46if`

**400 “column not found”**  
Use the TFF field names:  
`report_date_as_yyyy_mm_dd`, `contract_market_name`,  
`asset_mgr_positions_long/short`, `lev_money_positions_long/short`, `open_interest_all`.

**Empty results `[]`**  
Filter mismatch. This project filters by **contract_market_name** for ES/NQ.

**NQ missing / NaN z**  
Start earlier (ensure ≥3y valid observations for z). The tool tolerates gaps but needs minimum history.

**429 rate limits**  
Retry or reduce date range. With a Socrata token: `--api-token "<TOKEN>"`.

**Pandas FutureWarnings**  
Handled in code by using `shift(fill_value=False)` + `astype(bool)` for confirmation flags.

---

## Optional: Extra Trader Groups

You can compute/show the same metrics for:
- **Dealer/Intermediary (DI)**
- **Other Reportables (OR)**
- **Non-Reportables (NR)**

Add their long/short fields in `data_source.py`, compute `*_net_pct_oi`, z, and percentile in `metrics.py`, and (optionally) print them in `cli.py`. The code comments include the exact field names and small patches needed.

---

## Project Layout

```
crowded_cot/
  cli.py          # command-line interface & printing
  data_source.py  # CFTC API loader + CSV loader
  metrics.py      # calculations (nets, z, percentiles, flags)
  __init__.py
```

---

## License / Contributions

- Add your license text here.  
- PRs welcome for: more markets, richer summaries, charts, and integrated “news-failure” detection helpers.
