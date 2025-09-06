# crowded_cot

Utility for monitoring crowding in US equity index futures using the CFTC
Traders in Financial Futures (TFF) report.

## Quick start

Fetch data from the CFTC Public Reporting environment:

```bash
crowded-cot cftc --start-date 2024-01-01 --end-date 2024-06-01 \
    --output-csv es_nq.csv --output-json es_nq.json
```

Or load previously downloaded CSV files:

```bash
crowded-cot csv --path data/*.csv --output-csv es_nq.csv
```

The command prints a concise summary of the most recent week and writes tidy
CSV/JSON files for further analysis.