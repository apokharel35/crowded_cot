# crowded_cot

Utility for monitoring crowding in US equity index futures using the CFTC
Traders in Financial Futures (TFF) report.

## Quick start

Fetch data from the CFTC Public Reporting environment:

```bash
crowded-cot cftc --start-date 2024-01-01 --end-date 2024-06-01 \
    --output-csv es_nq.csv --output-json es_nq.json
```

## Example
                                                                                ```bash                                       
crowded-cot cftc \
  --start-date 2020-01-01 \
  --lookback-weeks 156 \
  --output-csv  out/es_nq_3y.csv \
  --output-json out/es_nq_3y.json

Latest report date: 2025-09-02
ES: AM z=+0.89 (pct 66th, confirmed False); LF z=-0.77 (pct 13th, confirmed False)
NQ: AM z=-1.60 (pct 4th, confirmed False); LF z=+0.45 (pct 63th, confirmed False)
```


Or load previously downloaded CSV files:

```bash
crowded-cot csv --path data/*.csv --output-csv es_nq.csv
```

The command prints a concise summary of the most recent week and writes tidy
CSV/JSON files for further analysis.