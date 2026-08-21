# Technology Comparison

The machine-readable assessment is [`technology_matrix.csv`](technology_matrix.csv). Its columns are: category, technology, intended role, local evidence state, a 1–5 fit score, MVP decision, licensing/cost note, decision rationale, and an official source. A score is a fit-to-this-workstation assessment, not a universal quality ranking.

## Storage and physical organization

Parquet/Arrow is the canonical format. It is portable across PyArrow, DuckDB, Polars, pandas, Spark, and most future engines; it preserves typed columns and row-group statistics; and it separates durable data from any query engine. DuckDB's documentation confirms projection/filter pushdown and explains that sorting tightens row-group min/max statistics for pruning. It recommends roughly 100,000–1,000,000 rows per row group and 100 MB–10 GB files for its reader ([DuckDB Parquet guidance](https://duckdb.org/docs/current/guides/performance/file_formats), [sorting and row groups](https://duckdb.org/docs/stable/data/parquet/tips)). Arrow independently warns that partitioning can cost more than it saves and advises avoiding files below 20 MB, above 2 GB, or extremely high partition counts ([Arrow dataset guidance](https://arrow.apache.org/docs/python/dataset.html)).

These principles match the local result: the naïve 327-file Hive conversion helped date-range pruning but materially hurt single-security and metadata-heavy reads; a 16-way security bucket exploded to 3,477 files; and splitting the 28.6-MB GPW hourly corpus into 26 monthly files added overhead without a date-window gain. Therefore “Parquet” is not a sufficient decision, but the MVP conclusion is deliberately simple: publish a few compact manifest-listed files and keep partition/row-group settings configurable. Automatic period selection and compaction are optimizations, not correctness contracts.

CSV/text remains the immutable vendor landing format. HDF5 is rejected for the canonical layer because its advantages are Python-centric and it has weaker multi-engine portability. SQLite is selected for transactional metadata, not bars (available when needed). DuckDB is the analytical catalog/query facade, with optional materialized hot tables where profiling proves repeated join-heavy workloads justify duplication. PostgreSQL/TimescaleDB become reasonable only when concurrent writers, services, or always-on APIs appear.

## Data/query engines

The selected combination is deliberately plural:

- **PyArrow** owns Parquet schemas, dataset discovery, metadata inspection and interoperable batches.
- **DuckDB** owns SQL, selective scans, universe/macro joins, dataset construction and query-plan inspection.
- **Polars lazy** owns expression-heavy feature pipelines and long-to-wide transformations.
- **pandas** remains the compatibility boundary for libraries and small notebook results.

No one engine won every local query. On the partitioned control, DuckDB and Polars were essentially tied on the broad aggregate, while PyArrow/Polars were faster for the bounded date range and PyArrow was fastest for a one-security filter. Polars was about twice as fast as pandas on the retained feature workload. This supports an Arrow contract with purpose-specific engines rather than a single DataFrame monoculture.

Dask, Modin, Vaex and Spark remain matrix candidates, not execution dependencies. The 69.6M-row control is only 1.09 GB compressed and the current work is single-machine. Their scheduler/cluster models solve a scale problem not demonstrated by the evidence.

## Vectorized research

The core research layer should be transparent factor analytics implemented with Polars/NumPy and profiled Numba kernels:

- point-in-time eligibility;
- feature and forward-return calculation;
- cross-sectional ranks, IC, quantiles and turnover proxies;
- bounded parameter grids with deterministic checksums.

vectorbt remains a secondary adapter, not the core contract. The installed fresh `vectorbt` 1.1.0 workload exceeded a 120-second cold guard, whereas the transparent reference completed. The upstream project is active and its release history shows continued work, so the proper conclusion is to isolate, pin, profile import/compilation, and re-test—not to declare the library intrinsically unusable ([official releases](https://github.com/polakowo/vectorbt/releases)).

`bt` is the most relevant allocation-tree challenger but was not given a full portfolio accounting benchmark. backtesting.py is maintained but its primary single-instrument abstraction is a poor fit for daily point-in-time multi-asset ranking. Neither should own the feature or experiment schemas.

## Event-driven portfolio simulation

The MVP should use the narrow custom daily simulator. It was the only engine run end-to-end on identical local data and reconciled through an explicit ledger. Its domain is intentionally bounded: target weights, next-open fills, fractional quantities, cash, costs, missing/non-tradeable states, and auditable corporate-action hooks.

Zipline-reloaded 3.1.1 and Backtrader passed import smoke tests. Zipline is the best packaged challenger for a later adapter, and its current release adds modern Python/NumPy compatibility ([official release](https://github.com/stefan-jansen/zipline-reloaded/releases)). PyBroker's cold import exceeded the guard in the mixed event environment even though its documented walk-forward interface is relevant ([PyBroker strategy API](https://www.pybroker.com/en/latest/reference/pybroker.strategy.html)). A fair packaged-engine decision requires clean per-engine environments and full golden-ledger adapters; imports are not performance benchmarks.

LEAN and NautilusTrader are future engines, not MVP contenders. LEAN becomes compelling when supported broker/live parity, its time-frontier event model, and a dedicated engine deployment are required ([LEAN engine](https://www.quantconnect.com/docs/v2/lean-engine/getting-started), [algorithm engine](https://www.quantconnect.com/docs/v2/writing-algorithms/key-concepts/algorithm-engine)). NautilusTrader becomes compelling for intraday/live typed event flows where a Rust-native core and matching backtest/live semantics offset the operational burden ([architecture](https://nautilustrader.io/docs/latest/concepts/architecture/)). Both must consume the platform's security, feature, signal and order-intent contracts rather than redefine the canonical store.

## ML, validation and reporting

Start with scikit-learn preprocessing and linear baselines, LightGBM as the primary tabular nonlinear/ranking model, and XGBoost as the challenger. CatBoost is conditional on meaningful categorical inputs; PyTorch is deferred until tabular baselines and data leakage controls are mature. GPU is optional and workload-dependent. XGBoost's official GPU interface uses `device="cuda"` and can preserve data on-device through suitable matrix APIs ([XGBoost GPU support](https://xgboost.readthedocs.io/en/stable/gpu/)). LightGBM exposes CPU/GPU/CUDA devices and ranking objectives ([LightGBM parameters](https://lightgbm.readthedocs.io/en/stable/Parameters.html)).

Validation must be date-grouped and chronological. scikit-learn's `TimeSeriesSplit` is a useful reference and supports a gap, but securities sharing a session must not be split across train/test by ordinary row index ([TimeSeriesSplit](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)). Each fold fits preprocessing on training dates only and prevents training feature/label information intervals from overlapping information unavailable at the validation decision boundary. For simple forward-return labels, the default purge is at least the maximum label horizon; overlapping events, holding-period targets or other sampling structures may require a larger or structurally different exclusion.

Use YAML experiment files validated by Pydantic and a portable `runs/<run_id>/` directory containing config, metrics, manifest and artifacts. Git plus source/data hashes is sufficient initially. MLflow documents a useful local database workflow, but should be introduced only when run volume makes its search/UI valuable; it may index, never replace, the portable manifest ([official tutorial](https://mlflow.org/docs/latest/ml/tracking/tutorials/local-database/)). Use Plotly and matplotlib for reports, and treat QuantStats as a presentation adapter rather than an accounting engine.

## Licensing and operational posture

Licences and paid tiers must be checked again at adoption time. The matrix links to official projects, but licence terms can change between releases. No SaaS tracker, hosted database, broker API, or commercial backtester is required for this MVP. The design avoids canonical-data lock-in by keeping Parquet, schemas, manifests, signals and order intents engine-neutral.
