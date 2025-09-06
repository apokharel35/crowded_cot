"""Computation of positioning metrics."""

from __future__ import annotations

import pandas as pd


def compute_positioning_metrics(df: pd.DataFrame, threshold: float = 2.0) -> pd.DataFrame:
    """Compute net positions, z-scores and crowding flags.

    Parameters
    ----------
    df:
        DataFrame produced by a :class:`DataSource`.
    threshold:
        Absolute z-score threshold used to flag extreme crowding.
    """

    if df.empty:
        return df.copy()

    result = df.copy()
    result["asset_mgr_net"] = result["asset_mgr_long"] - result["asset_mgr_short"]
    result["lev_fund_net"] = result["lev_fund_long"] - result["lev_fund_short"]

    # Z-scores computed per contract over the entire history
    def _zscore(series: pd.Series) -> pd.Series:
        return (series - series.mean()) / series.std(ddof=0)

    result["asset_mgr_z"] = result.groupby("contract")["asset_mgr_net"].transform(
        _zscore
    )
    result["lev_fund_z"] = result.groupby("contract")["lev_fund_net"].transform(
        _zscore
    )

    result["extreme_crowding"] = (
        result[["asset_mgr_z", "lev_fund_z"]]
        .abs()
        .ge(threshold)
        .any(axis=1)
    )
    return result
