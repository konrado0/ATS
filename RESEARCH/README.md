# ATS Technical Research Study

This directory contains the workstation-specific architecture study, retained benchmark harnesses and reproducibility records. `D:\Stock\data` was treated as read-only; generated data is isolated under `prototypes/cache/` and ignored by Git.

## Read in this order

1. [`RECOMMENDED_ARCHITECTURE.md`](RECOMMENDED_ARCHITECTURE.md) — direct component and physical-layout decisions.
2. [`FEEDBACK_ASSESSMENT.md`](FEEDBACK_ASSESSMENT.md) — accepted, modified and rejected simplification points.
3. [`IMPLEMENTATION_ROADMAP.md`](IMPLEMENTATION_ROADMAP.md) — correctness-first vertical-slice sequence.
4. [`LOCAL_BENCHMARKS.md`](LOCAL_BENCHMARKS.md) — measured evidence and limitations.
5. [`ARCHITECTURE_OPTIONS.md`](ARCHITECTURE_OPTIONS.md) — separate scorecards and weighted stack decision.
6. [`EXISTING_PROJECT_AUDIT.md`](EXISTING_PROJECT_AUDIT.md) and [`HARDWARE_ENVIRONMENT.md`](HARDWARE_ENVIRONMENT.md) — input and machine context.
7. [`TECHNOLOGY_COMPARISON.md`](TECHNOLOGY_COMPARISON.md) and [`technology_matrix.csv`](technology_matrix.csv) — current technology research.

Raw benchmark rows are in [`benchmark_results.csv`](benchmark_results.csv). Scripts are grouped by benchmark layer under [`prototypes`](prototypes/); environment records are in [`environments`](environments/).

## Decision in one paragraph

Start with a few compact, immutable logical versions of ZSTD Parquet; Arrow schemas; DuckDB SQL/catalog access; Polars feature pipelines; transparent NumPy/Numba research kernels; and portable filesystem run manifests. ZSTD level 3 and 122,880-row groups are measured writer defaults, not permanent architecture. Deliver the trustworthy GPW feature → forward-return slice before storage automation or the daily event ledger. Keep pandas, vectorbt and packaged event engines at optional boundaries; LEAN and NautilusTrader remain later adapters.

## Reproduction notes

The successful physical-layout and data-engine reruns used the Python executable from `ats-stack-research`. Every timing row distinguishes `first` from `warm`. Parallel floating reductions are normalized to 12 significant digits for logical checksums; all repeated checksum groups in the retained CSV are stable. Exact performance will change with cache state, package builds, free RAM and storage placement.
