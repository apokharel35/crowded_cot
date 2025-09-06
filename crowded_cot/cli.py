"""Command line interface for the crowded COT tool."""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
from typing import Iterable

from .data_source import CftcPRELoader, CsvFolderLoader, DataSource
from .metrics import compute_positioning_metrics


def _parse_date(value: str) -> dt.date:
    return dt.datetime.strptime(value, "%Y-%m-%d").date()


def _build_loader(args: argparse.Namespace) -> DataSource:
    if args.source == "cftc":
        start = _parse_date(args.start_date)
        end = _parse_date(args.end_date) if args.end_date else None
        return CftcPRELoader(
            start_date=start,
            end_date=end,
            api_token=args.api_token,
            dataset_id=args.dataset_id,
        )
    if args.source == "csv":
        return CsvFolderLoader(path=args.path)
    raise ValueError(f"Unknown source: {args.source}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)

    # shared options for all subcommands
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--output-csv", help="Write tidy CSV to this path")
    common.add_argument("--output-json", help="Write tidy JSON to this path")
    common.add_argument(
        "--extreme-threshold",
        type=float,
        default=2.0,
        help="Z-score threshold for extremes (default: 2.0)",
    )
    common.add_argument(
        "--lookback-weeks",
        type=int,
        default=260,
        help="Rolling window for z-scores/percentiles (weeks, default: 260 ≈ 5y)",
    )
    # NEW: user-tunable crowding rules + confirmation window
    common.add_argument(
        "--am-long-pct",
        type=float,
        default=90.0,
        help="Asset Managers crowded-long percentile threshold (default: 90)",
    )
    common.add_argument(
        "--lf-short-pct",
        type=float,
        default=10.0,
        help="Leveraged Funds crowded-short percentile threshold (default: 10)",
    )
    common.add_argument(
        "--confirm-weeks",
        type=int,
        default=2,
        help="Consecutive weeks required to confirm a signal (default: 2)",
    )

    sub = parser.add_subparsers(dest="source", required=True)

    cftc = sub.add_parser("cftc", parents=[common], help="Load data from the CFTC PRE API")
    cftc.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    cftc.add_argument("--end-date", help="YYYY-MM-DD")
    cftc.add_argument("--api-token", help="Socrata API token")
    cftc.add_argument(
        "--dataset-id",
        default="TFF_COMBINED",
        help="Key in DATASET_IDS or explicit dataset id",
    )

    csv = sub.add_parser("csv", parents=[common], help="Load data from local CSV files")
    csv.add_argument("--path", nargs="+", required=True, help="File paths or globs")

    return parser


def _get(colname: str, row, default=None):
    """Safe access for optional columns."""
    return row[colname] if (colname in row and row[colname] is not None) else default


def _bool(x) -> bool:
    try:
        return bool(x) if x is not None else False
    except Exception:
        return False


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    loader = _build_loader(args)
    df = loader.load()
    metrics = compute_positioning_metrics(
        df,
        threshold=args.extreme_threshold,
        lookback_weeks=args.lookback_weeks,
    )

    if args.output_csv:
        Path(args.output_csv).parent.mkdir(parents=True, exist_ok=True)
        metrics.to_csv(args.output_csv, index=False)
    if args.output_json:
        Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
        metrics.to_json(args.output_json, orient="records", date_format="iso")

    if metrics.empty:
        print("No data returned.")
        return 0

    latest_date = metrics["report_date"].max()
    print(f"Latest report date: {latest_date}")

    # Use the full history to compute confirmation over N weeks per contract
    by_contract = metrics.sort_values(["contract", "report_date"]).groupby("contract", sort=False)

    for contract, g in by_contract:
        # last row (today)
        today = g.iloc[-1]

        am_z = float(_get("asset_mgr_z", today, float("nan")))
        lf_z = float(_get("lev_fund_z", today, float("nan")))
        am_pct = _get("asset_mgr_pct", today, None)
        lf_pct = _get("lev_fund_pct", today, None)

        # Human-friendly percentile strings
        am_pct_str = f"{am_pct:.0f}th" if am_pct is not None else "n/a"
        lf_pct_str = f"{lf_pct:.0f}th" if lf_pct is not None else "n/a"

        # User-configurable extreme rules for today's bar
        am_ext_today = (
            (am_pct is not None and am_pct >= args.am_long_pct)
            or (am_z >= args.extreme_threshold)
        )
        lf_ext_today = (
            (lf_pct is not None and lf_pct <= args.lf_short_pct)
            or (lf_z <= -args.extreme_threshold)
        )

        # N-week confirmation using today's thresholds
        w = max(1, int(args.confirm_weeks))
        tail = g.tail(w)

        # Build series with the same rule over the tail window
        am_series = (
            ((tail["asset_mgr_pct"] >= args.am_long_pct) | (tail["asset_mgr_z"] >= args.extreme_threshold))
            .fillna(False)
            .astype(bool)
        )
        lf_series = (
            ((tail["lev_fund_pct"] <= args.lf_short_pct) | (tail["lev_fund_z"] <= -args.extreme_threshold))
            .fillna(False)
            .astype(bool)
        )
        am_conf = bool(am_series.all()) if len(tail) == w else False
        lf_conf = bool(lf_series.all()) if len(tail) == w else False

        # Decide trade direction per your rules:
        # LONG if LF crowded-short (confirmed); SHORT if AM crowded-long (confirmed)
        trade = "NO"
        reason = ""
        if lf_conf and not am_conf:
            trade = "YES (LONG)"
            reason = f"LF extreme short confirmed {w}w"
        elif am_conf and not lf_conf:
            trade = "YES (SHORT)"
            reason = f"AM extreme long confirmed {w}w"
        elif am_conf and lf_conf:
            trade = "YES (CONFLICT)"
            reason = f"Both extremes confirmed {w}w (review manually)"

        # Main summary line with user thresholds and confirmation outcome

        di_z = today.get("dealer_z", None);     di_pct = today.get("dealer_pct", None)
        or_z = today.get("other_rep_z", None);  or_pct = today.get("other_rep_pct", None)
        nr_z = today.get("nonrept_z", None);    nr_pct = today.get("nonrept_pct", None)
        def fmt(z,p):
            zs = f"{z:+.2f}" if z is not None else "n/a"
            ps = f"{p:.0f}th" if p is not None else "n/a"
            return f"{zs} (pct {ps})"

        summary = (
            f"{contract}: "
            f"AM {fmt(am_z, am_pct)}, LF {fmt(lf_z, lf_pct)}; "
            f"DI {fmt(di_z, di_pct)}, OR {fmt(or_z, or_pct)}, NR {fmt(nr_z, nr_pct)}; "
            f"conf{w}w AM={am_conf} LF={lf_conf}"
        )

        print(summary)
        print(f"  TRADE: {trade}" + (f" — {reason}" if reason else ""))

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
