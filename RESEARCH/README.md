# ATS Technical Research Study

This directory contains the architecture study, research contracts, phase reports,
retained benchmark harnesses and reproducibility records. Vendor/source areas
under `D:\Stock\data` are immutable evidence. Versioned ATS publications and
runs live under `D:\Stock\data\ATS`; disposable prototype caches remain under
documented cache/temporary roots and are ignored by Git.

## Read in this order

1. [`RESEARCH_OPERATING_POLICY.md`](RESEARCH_OPERATING_POLICY.md) — decision-proportional rigor and scope rules.
2. [`IMPLEMENTATION_ROADMAP.md`](IMPLEMENTATION_ROADMAP.md) — correctness-first vertical-slice sequence and current Phase D gates.
3. [`PHASE_D_POOLED_ML_RESEARCH_CHARTER.md`](PHASE_D_POOLED_ML_RESEARCH_CHARTER.md) — frozen direction for the next bounded research phase.
4. [`PRE_PHASE_D_MARKET_STATE_DIAGNOSTIC.md`](PRE_PHASE_D_MARKET_STATE_DIAGNOSTIC.md) — controlling market-state readiness checkpoint.
5. [`RECOMMENDED_ARCHITECTURE.md`](RECOMMENDED_ARCHITECTURE.md) — direct component and physical-layout decisions.
6. [`LOCAL_BENCHMARKS.md`](LOCAL_BENCHMARKS.md) and [`ARCHITECTURE_OPTIONS.md`](ARCHITECTURE_OPTIONS.md) — measured evidence and stack alternatives.
7. [`EXISTING_PROJECT_AUDIT.md`](EXISTING_PROJECT_AUDIT.md), [`HARDWARE_ENVIRONMENT.md`](HARDWARE_ENVIRONMENT.md), and [`TECHNOLOGY_COMPARISON.md`](TECHNOLOGY_COMPARISON.md) — input, machine and technology context.

Raw benchmark rows are in [`benchmark_results.csv`](benchmark_results.csv). Scripts are grouped by benchmark layer under [`prototypes`](prototypes/); environment records are in [`environments`](environments/).

## GPW price-basis checkpoints

For the proposed Bossa-primary Phase A rebuild, read these together:

1. [`GPW_PHASE_A_PRICE_BASIS_READINESS.md`](GPW_PHASE_A_PRICE_BASIS_READINESS.md) — consolidated coverage, split-treatment evidence, derived-data contracts, and the current proceed/no-proceed decision.
2. [`GPW_TOP60_DEC2019_WARMUP_AUDIT.md`](GPW_TOP60_DEC2019_WARMUP_AUDIT.md) — earliest complete-PIT date, completed targeted source/native price coverage, strict 252-session eligibility, and the recommended future experiment start.
3. [`GPW_RAW_PRICE_COVERAGE_AUDIT.md`](GPW_RAW_PRICE_COVERAGE_AUDIT.md) — official TOP60 member-session coverage from the later accepted Phase A evaluation start, with Stooq used only as a reference denominator.
4. [`GPW_FIVE_SECURITY_ENRICHMENT_REPORT.md`](GPW_FIVE_SECURITY_ENRICHMENT_REPORT.md) — Investing.com identity, provenance, distribution mapping, and mixed-basis Phase A sensitivity.
5. [`PHASE_A_DECISION_ORIENTED_REPORT.md`](PHASE_A_DECISION_ORIENTED_REPORT.md) — accepted Stooq-based research interpretation and the immutable baseline that a replacement run must not silently overwrite.

Current checkpoint: Bossa + Investing.com + the three accepted clean Yahoo WSE histories provide 100% of the 99,721 expected-trading source/native price observations from the complete-PIT boundary on 2019-12-23; no additional price histories remain. The recommended future experiment start is therefore 2019-12-23 with feature-specific eligibility retained. Strict every-session 252-bar readiness remains 98.7342%, two selected Investing member-session rows have missing displayed volume, and an accepted replacement Phase A is still gated by the authoritative split ledger and derived split-adjusted OHLC/volume view. Price-only returns and later ATS total returns remain separate derived representations.

## Decision in one paragraph

Start with a few compact, immutable logical versions of ZSTD Parquet; Arrow schemas; DuckDB SQL/catalog access; Polars feature pipelines; transparent NumPy/Numba research kernels; and portable filesystem run manifests. ZSTD level 3 and 122,880-row groups are measured writer defaults, not permanent architecture. Deliver the trustworthy GPW feature → forward-return slice before storage automation or the daily event ledger. Keep pandas, vectorbt and packaged event engines at optional boundaries; LEAN and NautilusTrader remain later adapters.

## Reproduction notes

The successful physical-layout and data-engine reruns used the Python executable from `ats-stack-research`. Every timing row distinguishes `first` from `warm`. Parallel floating reductions are normalized to 12 significant digits for logical checksums; all repeated checksum groups in the retained CSV are stable. Exact performance will change with cache state, package builds, free RAM and storage placement.
