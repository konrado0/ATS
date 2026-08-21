# Reproducible benchmark prototypes

The scripts in this tree generate the measurements reported in
`../benchmark_results.csv`. Inputs under `D:/Stock/data` are read-only.
Generated datasets belong in `cache/` and are intentionally not tracked.

Benchmark layers are kept separate:

- `parquet_layout/`: physical layout, compression, row groups, and updates;
- `data_engine/`: DuckDB, Polars, pandas, and PyArrow query/transform work;
- `research_backtester/`: vectorized factor and parameter-sweep work;
- `event_engine/`: ledger-based portfolio simulation;
- `common/`: shared input discovery, timing, checksums, and schemas.
