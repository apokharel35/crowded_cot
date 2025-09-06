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
        loader = CftcPRELoader(
            start_date=start,
            end_date=end,
            api_token=args.api_token,
            dataset_id=args.dataset_id,
        )
        return loader
    if args.source == "csv":
        loader = CsvFolderLoader(path=args.path)
        return loader
    raise ValueError(f"Unknown source: {args.source}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--output-csv", help="Write tidy CSV to this path")
    common.add_argument("--output-json", help="Write tidy JSON to this path")
    common.add_argument(
        "--extreme-threshold",
        type=float,
        default=2.0,
        help="Z-score threshold for extreme crowding",
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


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    loader = _build_loader(args)
    df = loader.load()
    metrics = compute_positioning_metrics(df, threshold=args.extreme_threshold)

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
    latest = metrics[metrics["report_date"] == latest_date]
    print(f"Latest report date: {latest_date}")
    for contract, group in latest.groupby("contract"):
        row = group.iloc[0]
        summary = (
            f"{contract}: asset_mgr_z={row['asset_mgr_z']:.2f}, "
            f"lev_fund_z={row['lev_fund_z']:.2f}"
        )
        if row["extreme_crowding"]:
            summary += " **EXTREME**"
        print(summary)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
