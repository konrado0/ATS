# Hardware and Environment Record

Audit date: 2026-08-19 (Europe/Warsaw). This is a reproducibility record, not a capacity guarantee; free memory, free disk, clocks, temperatures, and background load vary between runs.

## Workstation

| Component | Observed state | Research implication |
|---|---|---|
| OS | Windows 11 Pro, build 10.0.26100 | Native Windows wheels and Conda compatibility matter; WSL/Docker were not benchmarked. |
| CPU | AMD Ryzen 9 3900X, 12 physical / 24 logical cores | Strong local parallel scans and CPU model training; single-thread latency remains relevant. |
| RAM | 31.91 GiB installed; about 16.96 GiB available at audit | Use lazy scans and bounded matrices. Do not assume the full 69.6M-row table plus wide features fits as pandas objects. |
| GPU | NVIDIA GeForce RTX 4070, 12,282 MiB VRAM | Useful for sufficiently large XGBoost/LightGBM/PyTorch workloads; copying small matrices can erase the benefit. |
| NVIDIA stack | Driver 591.86; reported CUDA capability 13.1 | Package CUDA runtime compatibility must be checked independently of the driver capability. |
| Storage | Samsung 980 1 TB NVMe; ADATA SX8200PNP 476.9 GB NVMe; Plextor 512 GB SATA SSD; Seagate ST4000DM004 4 TB SATA HDD | Put active canonical data/caches on SSD; HDD is appropriate for immutable archives and cold snapshots. |
| Volumes | C: 930.7 GB / 453.6 GB free; D: 2,194 GB / 1,331.8 GB free; E: 1,500 GB / 34.6 GB free | D: has adequate headroom for canonical versions, temporary rewrites, and compaction. E: is too full for safe rewrite workflows. |

The limiting resource for this study is memory during wide matrices and model training, followed by small-file metadata overhead. The canonical 1.09-GB compressed bar control is modest relative to local storage. GPU capacity is secondary because the first MVP workloads are tabular and bounded.

## Conda environments

All pre-existing environments were preserved. The `vectorbt` environment was exported before new environment work:

- `vectorbt-environment.yml`: portable package specification.
- `vectorbt-conda-explicit.txt`: exact Conda artifact URLs.
- `vectorbt-pip-freeze.txt`: Python package view.

Fresh, independently solved environments were created rather than cloning `vectorbt`:

| Environment | Purpose | Important observed versions/state |
|---|---|---|
| `ats-stack-research` | Arrow/Parquet, DuckDB, Polars, pandas, vectorized research, notebooks and tests | Python 3.12.13; DuckDB 1.5.5; Polars 1.43.2; pandas 3.0.5; NumPy 1.26.4; Numba 0.67.0; vectorbt 1.1.0; PyArrow 25.0.0 (pip). |
| `ats-stack-event` | Packaged event-engine compatibility | Python 3.11.15; PyBroker 2.0.0; Zipline-reloaded 3.1.1; Backtrader 1.9.78.123. Pip resolved pandas 2.3.3 and PyArrow 25.0.0. |
| `ats-stack-ml` | Conservative bounded ML benchmark | Python 3.12; NumPy 1.26; pandas 2.3; PyArrow 22; scikit-learn 1.6.1; LightGBM 4.7; XGBoost 3.4. |

Each fresh environment has YAML, explicit-Conda, and pip-freeze exports in [`environments`](environments/). Explicit exports are platform-specific; YAML files are more portable but are not guaranteed to solve identically in the future.

### Compatibility findings

1. `ats-stack-event` is an experimental compatibility environment. Pip replaced pandas with 2.3.3 after the Conda solve while stale pandas 3.0.5 metadata remained in `conda-meta`. Recreate this environment from a pinned specification before production use; do not treat the current explicit export as a clean lock.
2. scikit-learn `Ridge` solver calls hung in both the broad latest-stack environment and the pinned ML environment. The benchmark uses `SGDRegressor` as the transparent linear baseline. This is a local numerical-stack finding, not evidence that Ridge is generally defective.
3. vectorbt 1.1.0 cold import plus the bounded moving-average grid exceeded the 120-second guard. It remains optional pending a pinned, isolated reproduction.
4. PyBroker cold import exceeded a 90-second guard in the event environment. Zipline-reloaded and Backtrader passed import smoke tests.

## Reproducibility controls

- Benchmark seed: `20260819` unless a script records a more specific seed.
- First-run and warm-run rows are separate in `benchmark_results.csv`.
- Checksums are logical-output checks, not file-byte checks, so equivalent Parquet encodings can be compared.
- Peak RSS is the process's absolute resident set at the sample point. Engines run sequentially in some harnesses, so RSS must not be interpreted as isolated incremental memory without a fresh-process rerun.
- Generated datasets live in `RESEARCH/prototypes/cache/` and are ignored by Git.
- The benchmark scripts and tests are retained under `RESEARCH/prototypes/`.
- The repository commit is whatever `git rev-parse HEAD` reports at execution time; scripts should record `git_commit` in future run manifests. This study was produced on a clean initial ATS repository plus the new `RESEARCH` tree.

## CUDA policy

CUDA is optional. The selected canonical data and research code must work on CPU. GPU jobs must record driver, library CUDA build, device, VRAM, matrix dtype, and whether input data remains device-resident. The local XGBoost GPU run was faster than CPU on a 300,000-row float32 table, but emitted a device/input mismatch warning during prediction; that path needs a device-resident `QuantileDMatrix` or equivalent before performance claims extend beyond training.

## IDE and notebook support

`ats-stack-research` includes JupyterLab and plotting packages and is suitable for VS Code/PyCharm kernels. Notebooks are exploratory clients, not the source of truth: production feature definitions, benchmarks, point-in-time joins, and simulators belong in importable modules with tests.
