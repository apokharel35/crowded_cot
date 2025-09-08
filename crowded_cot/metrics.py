"""Compute normalized positioning metrics and extreme-crowding flags."""

from __future__ import annotations

import numpy as np
import pandas as pd


LOOKBACK_WEEKS_DEFAULT = 260  # ~5 years
MIN_REQUIRED_WEEKS = 156      # default minimum history for z-scores (~3y


def _percentile_rank_inc(window_vals: np.ndarray, x: float) -> float:
    """
    Inclusive percentile rank (0..100), like Excel PERCENTRANK.INC.
    NaNs in window are ignored.
    """
    vals = window_vals[~np.isnan(window_vals)]
    if vals.size == 0 or np.isnan(x):
        return np.nan
    # count of values <= x divided by N
    return 100.0 * (np.searchsorted(np.sort(vals), x, side="right") / vals.size)


def _rolling_stats(series: pd.Series, lookback: int, min_required: int = MIN_REQUIRED_WEEKS) -> tuple[pd.Series, pd.Series]:
    # Use a slightly shorter min_period to handle gaps (e.g., NQ history)
    min_required = min(lookback, min_required)
    mean = series.rolling(lookback, min_periods=min_required).mean()
    std = series.rolling(lookback, min_periods=min_required).std(ddof=1)
    return mean, std


def _rolling_pct(series: pd.Series, lookback: int) -> pd.Series:
    # Compute inclusive percentile rank for each point against the trailing window
    out = np.full(series.shape[0], np.nan, dtype=float)
    arr = series.to_numpy(dtype=float)
    for i in range(series.shape[0]):
        lo = max(0, i - lookback + 1)
        out[i] = _percentile_rank_inc(arr[lo : i + 1], arr[i])
    return pd.Series(out, index=series.index, dtype=float)


def compute_positioning_metrics(
    df: pd.DataFrame,
    threshold: float = 2.0,
    lookback_weeks: int = LOOKBACK_WEEKS_DEFAULT,
    min_required_weeks: int = MIN_REQUIRED_WEEKS,
) -> pd.DataFrame:
    """
    Input dataframe must contain at least:
      report_date (date), contract (str),
      open_interest, asset_mgr_long, asset_mgr_short,
      lev_fund_long, lev_fund_short

    Returns the same rows with added columns:
      am_net_pct_oi, lf_net_pct_oi
      asset_mgr_z, lev_fund_z
      asset_mgr_pct, lev_fund_pct
      is_extreme_am_long, is_extreme_lev_short
      is_confirmed_extreme_am_long, is_confirmed_extreme_lev_short
      extreme_crowding (aggregate flag kept for CLI compatibility)
    """
    if df.empty:
        return df.copy()

    # Ensure types
    work = df.copy()
    work = work.sort_values(["contract", "report_date"]).reset_index(drop=True)
    num_cols = [
        "open_interest",
        "asset_mgr_long",
        "asset_mgr_short",
        "lev_fund_long",
        "lev_fund_short",
    ]
    for c in num_cols:
        work[c] = pd.to_numeric(work[c], errors="coerce")

    # --- Net % of Open Interest (SIGN: long - short for ALL groups) ---
    # This fixes any prior sign ambiguity on Leveraged Funds.
    eps = 1e-12
    oi = work["open_interest"].replace(0, np.nan)  # avoid div/0
    work["am_net_pct_oi"] = 100.0 * (
        (work["asset_mgr_long"] - work["asset_mgr_short"]) / oi
    )
    work["lf_net_pct_oi"] = 100.0 * (
        (work["lev_fund_long"] - work["lev_fund_short"]) / oi
    )
    # new groups
    work["di_net_pct_oi"] = 100.0 * ((work["dealer_long"]      - work["dealer_short"])      / oi)
    work["or_net_pct_oi"] = 100.0 * ((work["other_rept_long"]  - work["other_rept_short"])  / oi)
    work["nr_net_pct_oi"] = 100.0 * ((work["nonrept_long"]     - work["nonrept_short"])     / oi)

    # --- Rolling z-scores & percentile ranks per contract ---
    results = []
    for contract, g in work.groupby("contract", sort=False):
        g = g.copy()

        # Asset Managers
        am_mean, am_std = _rolling_stats(g["am_net_pct_oi"], lookback_weeks, min_required_weeks)
        g["asset_mgr_z"] = (g["am_net_pct_oi"] - am_mean) / am_std
        g["asset_mgr_pct"] = _rolling_pct(g["am_net_pct_oi"], lookback_weeks)

        # Leveraged Funds
        lf_mean, lf_std = _rolling_stats(g["lf_net_pct_oi"], lookback_weeks, min_required_weeks)
        g["lev_fund_z"] = (g["lf_net_pct_oi"] - lf_mean) / lf_std
        g["lev_fund_pct"] = _rolling_pct(g["lf_net_pct_oi"], lookback_weeks)

        # If you compute extra groups (Dealer/Other/Nonrep), also pass min_required_weeks:
        if "di_net_pct_oi" in g:
            di_mean, di_std = _rolling_stats(g["di_net_pct_oi"], lookback_weeks, min_required_weeks)
            g["dealer_z"] = (g["di_net_pct_oi"] - di_mean) / di_std
            g["dealer_pct"] = _rolling_pct(g["di_net_pct_oi"], lookback_weeks)
        if "or_net_pct_oi" in g:
            or_mean, or_std = _rolling_stats(g["or_net_pct_oi"], lookback_weeks, min_required_weeks)
            g["other_rep_z"] = (g["or_net_pct_oi"] - or_mean) / or_std
            g["other_rep_pct"] = _rolling_pct(g["or_net_pct_oi"], lookback_weeks)
        if "nr_net_pct_oi" in g:
            nr_mean, nr_std = _rolling_stats(g["nr_net_pct_oi"], lookback_weeks, min_required_weeks)
            g["nonrept_z"] = (g["nr_net_pct_oi"] - nr_mean) / nr_std
            g["nonrept_pct"] = _rolling_pct(g["nr_net_pct_oi"], lookback_weeks)

        # Dealer/Intermediary (DI)
        di_mean, di_std = _rolling_stats(g["di_net_pct_oi"], lookback_weeks)
        g["dealer_z"] = (g["di_net_pct_oi"] - di_mean) / di_std
        g["dealer_pct"] = _rolling_pct(g["di_net_pct_oi"], lookback_weeks)

        # Other Reportables (OR)
        or_mean, or_std = _rolling_stats(g["or_net_pct_oi"], lookback_weeks)
        g["other_rep_z"] = (g["or_net_pct_oi"] - or_mean) / or_std
        g["other_rep_pct"] = _rolling_pct(g["or_net_pct_oi"], lookback_weeks)

        # Non-Reportables (NR)
        nr_mean, nr_std = _rolling_stats(g["nr_net_pct_oi"], lookback_weeks)
        g["nonrept_z"] = (g["nr_net_pct_oi"] - nr_mean) / nr_std
        g["nonrept_pct"] = _rolling_pct(g["nr_net_pct_oi"], lookback_weeks)        

        # --- Extreme flags ---
        g["is_extreme_am_long"] = (g["asset_mgr_pct"] >= 90) | (g["asset_mgr_z"] >= threshold)
        g["is_extreme_lev_short"] = (g["lev_fund_pct"] <= 10) | (g["lev_fund_z"] <= -threshold)

        # 2-week confirmations (requires two consecutive weeks true)
        ext_am = g["is_extreme_am_long"].astype(bool)
        ext_lf = g["is_extreme_lev_short"].astype(bool)

        g["is_confirmed_extreme_am_long"]  = ext_am & ext_am.shift(1, fill_value=False)
        g["is_confirmed_extreme_lev_short"] = ext_lf & ext_lf.shift(1, fill_value=False)

        # Legacy aggregate flag for CLI compatibility
        g["extreme_crowding"] = g["is_extreme_am_long"] | g["is_extreme_lev_short"]

        results.append(g)

    out = pd.concat(results, ignore_index=True)

    # Keep column order friendly
    preferred = [
        "report_date",
        "contract",
        "market_name",
        "open_interest",
        "asset_mgr_long",
        "asset_mgr_short",
        "lev_fund_long",
        "lev_fund_short",
        #open-interest
        "am_net_pct_oi",
        "lf_net_pct_oi",
        "di_net_pct_oi",""
        "or_net_pct_oi",
        "nr_net_pct_oi",
        #z-scores
        "asset_mgr_z",
        "lev_fund_z",
        "dealer_z",
        "other_rep_z",
        "nonrept_z",
        #pct
        "asset_mgr_pct",
        "lev_fund_pct",
        "dealer_pct",
        "other_rep_pct",
        "nonrept_pct",
        "is_extreme_am_long",
        "is_extreme_lev_short",
        "is_confirmed_extreme_am_long",
        "is_confirmed_extreme_lev_short",
        "extreme_crowding",
    ]
    # Only keep columns that exist
    cols = [c for c in preferred if c in out.columns] + [c for c in out.columns if c not in preferred]
    return out.loc[:, cols]
