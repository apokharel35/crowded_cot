"""Data loading interfaces for CFTC TFF data."""

from __future__ import annotations

import abc
import datetime as dt
import glob
import json
from dataclasses import dataclass
from typing import Iterable, List, Mapping, Optional

import pandas as pd
import requests


class DataSource(abc.ABC):
    """Abstract base class for data loaders."""

    @abc.abstractmethod
    def load(self) -> pd.DataFrame:
        """Return a dataframe with weekly observations."""


# Mapping of logical dataset names to Socrata identifiers.  Users can modify
# this dictionary to point at alternative datasets if desired.
DATASET_IDS: Mapping[str, str] = {
    "TFF_COMBINED": "6p9r-dwsc",  # default Futures + Options Combined dataset
}

# Market name filters for contracts.  CFTC market names are inconsistent, so we
# match against any of the provided aliases.
MARKET_ALIASES: Mapping[str, List[str]] = {
    "ES": ["E-mini S&P 500", "S&P 500 E-mini"],
    "NQ": ["E-mini NASDAQ-100", "NASDAQ-100 E-mini"],
}

# Columns fetched from the CFTC dataset.  Keys are the column names expected in
# the returned dataframe, values are the column names in the Socrata dataset.
CFTC_COLUMN_MAP: Mapping[str, str] = {
    "report_date": "as_of_date_in_form_yyyymmdd",
    "market_name": "market_and_exchange_names",
    "open_interest": "open_interest_all",
    "asset_mgr_long": "asset_mgr_long_all",
    "asset_mgr_short": "asset_mgr_short_all",
    "lev_fund_long": "lev_fund_long_all",
    "lev_fund_short": "lev_fund_short_all",
}


@dataclass
class CftcPRELoader(DataSource):
    """Load data from the CFTC Public Reporting environment via Socrata."""

    start_date: dt.date
    end_date: Optional[dt.date] = None
    api_token: Optional[str] = None
    dataset_id: str = "TFF_COMBINED"

    def _resolve_dataset(self) -> str:
        dataset = DATASET_IDS.get(self.dataset_id, self.dataset_id)
        return dataset

    def load(self) -> pd.DataFrame:
        dataset = self._resolve_dataset()
        select_clause = ",".join(CFTC_COLUMN_MAP.values())

        base_url = f"https://publicreporting.cftc.gov/resource/{dataset}.json"

        where_clauses = [
            f"{CFTC_COLUMN_MAP['report_date']} >= '{self.start_date.isoformat()}'",
        ]
        if self.end_date:
            where_clauses.append(
                f"{CFTC_COLUMN_MAP['report_date']} <= '{self.end_date.isoformat()}'"
            )

        # Market name filters
        market_filters: List[str] = []
        for aliases in MARKET_ALIASES.values():
            joined = ",".join(f"'{a}'" for a in aliases)
            market_filters.append(
                f"upper({CFTC_COLUMN_MAP['market_name']}) in (" +
                ",".join(f"'{a.upper()}'" for a in aliases) + ")"
            )
        where_clauses.append("(" + " OR ".join(market_filters) + ")")

        params = {
            "$select": select_clause,
            "$where": " AND ".join(where_clauses),
            "$order": CFTC_COLUMN_MAP['report_date'],
            "$limit": 50000,
        }

        headers = {"Accept": "application/json"}
        if self.api_token:
            headers["X-App-Token"] = self.api_token

        response = requests.get(base_url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        data = json.loads(response.text)
        df = pd.DataFrame(data)
        if df.empty:
            return df

        # Rename columns to internal names and parse types
        df = df.rename(columns={v: k for k, v in CFTC_COLUMN_MAP.items()})
        df["report_date"] = pd.to_datetime(df["report_date"]).dt.date
        num_cols = [
            "open_interest",
            "asset_mgr_long",
            "asset_mgr_short",
            "lev_fund_long",
            "lev_fund_short",
        ]
        for col in num_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # Map market names to contract codes
        def _contract(name: str) -> Optional[str]:
            name_upper = name.upper()
            for code, aliases in MARKET_ALIASES.items():
                if any(name_upper == a.upper() for a in aliases):
                    return code
            return None

        df["contract"] = df["market_name"].apply(_contract)
        df = df.dropna(subset=["contract"]).reset_index(drop=True)
        return df


@dataclass
class CsvFolderLoader(DataSource):
    """Load TFF data from local CSV files."""

    path: Iterable[str]

    def load(self) -> pd.DataFrame:
        frames: List[pd.DataFrame] = []
        patterns = list(self.path)
        for pattern in patterns:
            for file in glob.glob(pattern):
                frame = pd.read_csv(file, parse_dates=["report_date"])
                if "contract" not in frame.columns and "market_name" in frame.columns:
                    def _contract(name: str) -> Optional[str]:
                        name_upper = str(name).upper()
                        for code, aliases in MARKET_ALIASES.items():
                            if any(name_upper == a.upper() for a in aliases):
                                return code
                        return None

                    frame["contract"] = frame["market_name"].apply(_contract)
                frames.append(frame)
        if not frames:
            return pd.DataFrame(columns=CFTC_COLUMN_MAP.keys())
        df = pd.concat(frames, ignore_index=True)
        # Ensure date type
        df["report_date"] = pd.to_datetime(df["report_date"]).dt.date
        numeric_cols = [
            "open_interest",
            "asset_mgr_long",
            "asset_mgr_short",
            "lev_fund_long",
            "lev_fund_short",
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df
