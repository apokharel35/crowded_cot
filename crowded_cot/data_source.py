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
    "TFF_COMBINED": "gpe5-46if",  # default Futures + Options Combined dataset
}

MARKET_ALIASES: Mapping[str, List[str]] = {
    "ES": ["E-MINI S&P 500", "S&P 500 E-MINI"],
    "NQ": [
        "E-MINI NASDAQ-100",   # hyphen
        "NASDAQ-100 E-MINI",   # hyphen reversed
        "E-MINI NASDAQ 100",   # space
        "NASDAQ 100 E-MINI",   # space reversed
    ],
}


# Columns fetched from the CFTC dataset. Keys = our internal names,
# values = exact Socrata field names on the TFF datasets.
CFTC_COLUMN_MAP: Mapping[str, str] = {
    # Date (Floating Timestamp on Socrata)
    "report_date": "report_date_as_yyyy_mm_dd",
    # Clean product name (no exchange suffix) — lets our alias filter match
    "market_name": "contract_market_name",
    "open_interest": "open_interest_all",
    # Position fields use "*_positions_*" on TFF datasets
    "asset_mgr_long": "asset_mgr_positions_long",
    "asset_mgr_short": "asset_mgr_positions_short",
    # Keep our internal key "lev_fund_*" but map to lev_money_* on Socrata
    "lev_fund_long": "lev_money_positions_long",
    "lev_fund_short": "lev_money_positions_short",
    
    "dealer_long": "dealer_positions_long_all",
    "dealer_short": "dealer_positions_short_all",
    "other_rept_long": "other_rept_positions_long",
    "other_rept_short": "other_rept_positions_short",
    "nonrept_long": "nonrept_positions_long_all",
    "nonrept_short": "nonrept_positions_short_all",
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

        # Market name filters (catch hyphen/space + both word orders)
        market_filter = (
            " ("
            "  upper(contract_market_name) like '%E-MINI%S%P%500%'"
            "  OR ("
            "       upper(contract_market_name) like '%E-MINI%NASDAQ%100%'"
            "       OR upper(contract_market_name) like '%NASDAQ%100%E-MINI%'"
            "     )"
            " ) "
        )
        where_clauses.append(market_filter)

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
            "dealer_long",
            "dealer_short",
            "other_rept_long",
            "other_rept_short",
            "nonrept_long",
            "nonrept_short",
        ]
        for col in num_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # Map market names to contract codes
        def _contract(name: str) -> Optional[str]:
            name_upper = str(name).upper()
            for code, aliases in MARKET_ALIASES.items():
                for alias in aliases:
                    if alias.upper() in name_upper:
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
