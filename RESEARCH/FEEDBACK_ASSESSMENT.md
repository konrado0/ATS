# Feedback Assessment: Correctness First, Scale on Evidence

This note records how the implementation-simplification feedback changed the recommendation. It is not an uncritical adoption: each point was weighed against the local benchmarks, the original acceptance requirements and the risk of producing convincing but invalid research.

## Accepted

### Build the trustworthy GPW vertical slice first

Accepted. The former roadmap delayed rank/IC/quantile evidence behind generalized canonical publication. The revised Phase A reaches point-in-time TOP60 features and 3/5/10/20-session labels first, while enforcing identity, availability and membership correctness. This yields useful evidence early and gives later infrastructure a real workload.

### Defer automatic physical-layout machinery

Accepted. The workstation scanned the 69.6M-row control in well under a second, while over-partitioning caused observable harm:

- 327 coarse Hive files made one-security retrieval about 5× slower;
- 3,477 bucketed files remained about 34× slower even with the correct bucket predicate;
- 26 monthly files did not improve the real GPW hourly 30-day query and hurt broad/security reads.

The MVP now publishes one or a few compact files per `(table, market, frequency)`. Automatic year/era/month resolution, delta accumulation and scheduled compaction require a measured trigger.

### Keep correctness mechanisms from day one

Accepted without dilution: stable security identity, validity-dated aliases and membership, unresolved-member retention, event/availability/decision timestamps, next-session rules, source hashes, immutable logical versions, chronological folds and accounting invariants remain mandatory.

### Use a minimal manifest and feature registry

Accepted. The authoritative dataset/run metadata is a small portable file, not a service. The initial feature registry is a decorator or frozen dataclass with identity, version, frequency, lookback, dependencies and code fingerprint. Feature values remain derived caches.

### Defer MLflow

Accepted. The initial contract is `runs/<run_id>/{config.yaml,metrics.json,manifest.json,artifacts/}` plus Git and hashes. MLflow may later index these directories when experiment discovery becomes painful, but is never authoritative.

### Prefer a readable daily ledger over optimization

Accepted. The event loop is moved after the trustworthy factor slice, but its golden accounting scenarios remain. TOP60 daily simulation does not justify aggressive runtime optimization.

## Accepted with modification

### Treat row-group and compression values as configuration

Accepted with a reproducibility condition. ZSTD level 3 and 122,880 rows are not semantic architecture, but every dataset manifest must record codec, level, row-group setting, writer/version, sort order and file list. A changed setting creates a new physical dataset version and must pass logical equivalence checks.

### “A small number of reasonably sized files”

Accepted as the MVP policy, with explicit operational criteria. The primary trigger to benchmark splitting is a missed representative query/rebuild SLO or file size that materially harms publication, correction or maintenance. Approaching 2 GiB is only a configurable initial review default. This prevents both premature partition machinery and an accidental future 50-GB monolith.

### Produce research before the complete portfolio engine

Accepted, but feature diagnostics cannot be called a backtest and cannot answer deployability. The first questions concern cross-sectional distributions, IC, quantile monotonicity, coverage and temporal stability. Claims about cash, turnover, fills or implementable return wait for the Phase C ledger.

## Not accepted

### Make physical organization unspecified

Rejected. The benchmarks proved file count and row-group organization materially affect behavior. The MVP uses an intentionally simple physical policy, but it is still explicit and versioned. “Just Parquet” would make reproduction and later comparison ambiguous.

### Postpone corporate-action and missing-state semantics entirely

Rejected. Full share/cash accounting belongs in Phase C, but Phase A must already classify membership exits, unresolved securities, suspensions/non-tradeability and price availability so factor samples are not silently biased. The data state model precedes the portfolio treatment.

### Treat initial signal diagnostics as evidence of alpha

Rejected. The proposed questions are useful for validating the research surface and generating hypotheses. Multiple testing, regime dependence, costs, capacity and portfolio construction are unresolved. Reports must say so directly.

## Resulting decision

The component choice is unchanged:

> Parquet + Arrow + DuckDB + Polars + NumPy/Numba + a narrow custom daily ledger.

The delivery order and operational scope changed materially:

1. trustworthy GPW feature/label/IC vertical slice;
2. simple compact canonical Parquet and manifest-backed DuckDB views;
3. readable daily accounting ledger;
4. chronological ML;
5. partitioning, compaction, caching, tracking UI and packaged engines only on measured triggers.

This preserves an evolvable foundation while removing infrastructure that the current 1.09-GB control and 28.6-MB GPW hourly corpus do not justify.
