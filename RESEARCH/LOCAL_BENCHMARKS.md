# Local Benchmarks

All raw rows are in [`benchmark_results.csv`](benchmark_results.csv); retained code is in [`prototypes`](prototypes/). The CSV schema is: benchmark layer, name, engine, dataset, layout, run kind/index, elapsed seconds, absolute peak RSS, logical rows, bytes on disk, file count, output checksum, notes, and UTC timestamp.

## Interpretation rules

- Layers are not blended. A Parquet scan, feature kernel and portfolio simulation answer different questions.
- Each first run is retained separately from warm repetitions.
- Medians below refer to warm runs where a stable warm series exists.
- Absolute RSS from a sequential process is not incremental engine memory. Fresh-process trials are needed for a fair memory league table.
- Logical checksums/tolerances are the correctness gate; different compressed bytes are expected.
- Strategy returns are workload outputs only and are not evidence of alpha.

## Parquet physical layout

The existing control and the Hive layout contained the same 69,635,916 logical rows and 27,662 ticker strings.

| Query | Existing monolith, 1 file | Hive market/frequency/year, 327 files | Effect |
|---|---:|---:|---|
| Broad aggregate | 0.221 s | 0.281 s | Hive 27% slower |
| Latest cross-section | 0.0304 s | 0.0929 s | Hive 3.1× slower |
| Last 365 days | 0.1768 s | 0.1001 s | Hive 43% faster |
| Security + date range | 0.0184 s | 0.0886 s | Hive 4.8× slower |
| One security history | 0.0190 s | 0.0970 s | Hive 5.1× slower |

Storage changed from 1,092,744,797 bytes to 1,077,997,160 bytes, only a 1.35% reduction. The conversion produced 327 files. Its observed file timestamp span was approximately 19.5 seconds and wall-clock observation was around 20–25 seconds; the in-process build-time record was lost when a post-write diagnostic query used a reserved alias. This is reported as an instrumentation failure, not reconstructed as a precise number.

A latest-day staged append wrote one 2,209-byte file in 0.130 seconds with about 139.9 MB absolute process RSS. That illustrates why per-day Parquet files cannot accumulate indefinitely: they are orders of magnitude below healthy analytical file sizes and require compaction.

### Normalized encoding and row-group stage

The corrected row-group experiment used the observed 36 uncompressed bytes/row to request approximately 64, 128 and 256 MiB groups. Parquet metadata confirmed 38, 19 and 10 physical groups with average sizes of 57.5, 115.7 and 184.2 MiB respectively. (The first byte-target attempt was rejected from the final results because DuckDB's default 122,880-row threshold flushed first and made all three files physically identical.)

| Normalized one-file encoding | Write | Peak RSS | Bytes | Broad | One security | Date range |
|---|---:|---:|---:|---:|---:|---:|
| ZSTD 3, ~64 MiB groups | 26.85 s | 17.45 GB | 1.017 GB | 0.260 s | 0.0365 s | 0.2079 s |
| ZSTD 3, ~128 MiB groups | 55.70 s | 18.60 GB | 1.016 GB | 0.272 s | 0.0682 s | 0.2258 s |
| ZSTD 3, ~256 MiB groups | 93.01 s | 17.79 GB | 1.035 GB | 0.296 s | 0.1260 s | 0.2030 s |
| Snappy, ~128 MiB groups | 107.24 s | 15.13 GB | 1.523 GB | 0.207 s | 0.0483 s | 0.1917 s |

Larger groups saved essentially no ZSTD space and degraded selective reads. Snappy accelerated scans at the same large group target but consumed about 50% more space and had the slowest observed full write. More importantly, the existing/default 122,880-row control remained faster for selective reads. ZSTD 3 with 122,880 rows is therefore the MVP writer default—not an immutable architectural requirement or a fashionable 128-MiB group.

### Security bucket and intraday month candidates

The 16-way security bucket produced **3,477 files**, 1.133 GB, a 40.09-second write and 9.75-GB peak RSS. An unqualified one-security query was 0.83 s. Adding the correct bucket predicate reduced it only to 0.65 s because the reader still crossed time/market partitions; the one-file control was 0.019 s. Security bucketing is rejected at this scale.

The real GPW hourly input contained 2,294,501 rows. Its normalized monolith was 28.62 MB and took 10.51 s to parse, sort and write. Year/month Hive partitioning produced 26 files and 28.84 MB in another 0.71 s. Warm comparisons were:

| GPW hourly query | One file | 26 monthly files |
|---|---:|---:|
| Broad scan | 0.0135 s | 0.0214 s |
| Latest cross-section | 0.0168 s | 0.0116 s |
| Last 30 days | 0.0091 s | 0.0093 s |
| Security + 30 days | 0.0044 s | 0.0098 s |
| One security | 0.0039 s | 0.0165 s |

Monthly partitioning gives no net benefit for this sparse 28-MB corpus and creates roughly 1-MB files. The chosen intraday layout uses annual/compacted files now and makes month a density-triggered extension, not a default.

## Data-engine layer

Using the same Hive dataset:

| Engine | Broad aggregate | Date range | One security |
|---|---:|---:|---:|
| DuckDB | 0.2994 s | 0.1046 s | 0.1989 s |
| Polars | 0.2860 s | 0.0562 s | 0.1495 s |
| PyArrow | 0.3925 s | 0.0517 s | 0.0900 s |

The result does not identify one universal winner. PyArrow's direct filtered dataset scan excelled on selective retrieval; Polars matched DuckDB on the broad operation and performed strongly on date filtering; DuckDB provides the best SQL/join/query-plan surface. The architecture composes all three over one Arrow schema.

## Research-backtester layer

The TOP60 feature workload contained 83,836 eligible point-in-time rows:

- pandas feature matrix: 0.0545 s warm median.
- Polars feature matrix: 0.0279 s warm median, about 1.95× faster.
- Numba bounded 1,000-variant last-row kernel: 0.000123 s warm after JIT.
- vectorbt cold import plus bounded MA grid: exceeded 120 seconds and was recorded as `compatibility_failed`.

The Numba number is intentionally narrow. It is a throughput microkernel over a 1,430 × 89 panel, not a full 1,000-portfolio cash-and-order simulation. It proves that compiled rank/grid kernels need not be the bottleneck; it does not validate order semantics or memory scaling. The factor layer should retain transparent reference outputs before any accelerated kernel is accepted.

## Event-engine layer

The custom daily workload covered 1,908 sessions and produced 2,752 ledger rows/trades with weekly TOP10 targets, next-session-open execution, fractional quantities, 10 bps commission and 15 bps slippage. Warm median runtime was 0.779 s; absolute sampled RSS was 191.6 MB. Ending equity was 1,722,745.04 from the configured initial state and is retained only as a reconciliation checksum—not a performance claim.

PyBroker exceeded a 90-second cold import guard. Zipline-reloaded and Backtrader passed import smoke tests. They did not receive full target-weight adapters, so this study cannot claim a runtime winner between event engines. The defensible conclusion is narrower: the custom simulator is executable and auditable now, while the packaged candidates require isolated environments and trade-by-trade golden-ledger adapters.

The custom ledger and tests cover next-open timing and conservation basics. Before production it must add explicit golden fixtures for suspension, missing bars, merger share conversion, cash takeover, identifier change, and revision replay.

## ML layer

The bounded real US table used 300,000 rows × 56 float32 features with a chronological split: training ended 2023-03-28 and testing started 2023-03-29.

| Model | First run | Warm run | Absolute peak RSS |
|---|---:|---:|---:|
| scikit-learn SGD baseline | 0.483 s | 0.466 s | 309 MB |
| LightGBM CPU | 0.727 s | 0.744 s | 454 MB |
| XGBoost CPU | 1.011 s | 0.900 s | 479 MB |
| XGBoost GPU | 0.586 s | 0.542 s | 508 MB |

GPU XGBoost was about 40% faster than its CPU warm run in this bounded trial. Prediction emitted a CUDA-model/CPU-input mismatch warning and fell back through a DMatrix path. The result justifies retaining GPU support, not making it mandatory. Model quality was deliberately not optimized.

## Acceptance status

| Check | Status |
|---|---|
| Benchmark CSV parses | Pass |
| Every result has a benchmark layer | Pass: 307 layout, 54 data, 19 research, 9 event, 8 ML rows |
| Existing 69.6M-row control preserved | Pass |
| TOP60 point-in-time builder retained | Pass |
| Custom simulator unit tests | Pass (2 tests) |
| Cross-engine logical checksums | Implemented for retained query cases; expand before migration |
| ZSTD/Snappy and 64/128/256-MiB row-group stage | Pass, with physical metadata verification |
| Security-bucket and GPW hourly month candidates | Pass; both rejected at current density |
| Full packaged-event golden ledgers | Not complete; optional challenger gate |
| Strategy/model alpha optimization | Intentionally not performed |
