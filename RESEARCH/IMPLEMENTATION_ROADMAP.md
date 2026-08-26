# Implementation Roadmap

The roadmap follows one rule: **build correctness infrastructure early; build scalability infrastructure only after representative profiling shows a need.** The first useful milestone is trustworthy GPW feature-to-future-return evidence, not a generalized storage service.

## Completed study baseline

The environment freezes, hardware/data audit, technology research, physical-layout study and prototype benchmarks are complete. They establish portable choices and useful writer defaults without requiring all benchmark machinery to become production infrastructure.

Acceptance already met:

- Existing `vectorbt` environment exported without modification.
- Fresh research, event and ML environments exported three ways.
- `D:\Stock\data` treated as read-only.
- 397 retained benchmark rows across five non-blended layers.
- ZSTD/Snappy, physical row groups, security buckets and real GPW hourly month layout measured.
- Custom daily simulator prototype tests pass.

## Phase A — Minimum trustworthy research slice

Build one end-to-end GPW path with the smallest infrastructure that can prevent false conclusions.

### Implement

1. A minimal stable `security_id` table and validity-dated ticker/ISIN/vendor aliases for the TOP60 scope.
2. Point-in-time WIG20 + mWIG40 membership from the complete-PIT 2019-12-23 start, retaining unresolved members, non-trading states, feature-specific eligibility, and benign exits.
3. A validated GPW daily observation adapter with whole-bar priority `Bossa mstall -> Bossa session-page supplement -> Investing.com -> accepted clean Yahoo WSE history -> explicit missing`. Degraded Yahoo historical symbols are validation evidence only. Stooq remains an independent adjusted reference and never enters this source/native panel as a fallback.
4. Explicit `event_ts`, `available_ts`, `decision_ts` and next-eligible-session semantics.
5. A small feature decorator/dataclass containing name, version, frequency, lookback, dependencies and code fingerprint.
6. Five features: 12–1 momentum, five-session return, 20-session volatility, 20-session relative volume and WIG 200-session trend.
7. Separately namespaced 3/5/10/20-session forward-return labels.
8. Cross-sectional ranks, coverage, rank IC, quantile returns and turnover proxies.
9. A portable run directory:

```text
runs/<run_id>/
  config.yaml
  metrics.json
  manifest.json
  artifacts/
```

The manifest pins source hashes, logical dataset/universe version, schema version, feature versions, Git commit, environment, seed and decision/label timing.

### Initial diagnostic questions

- Is subsequent return monotonic across momentum ranks/quantiles?
- Does a short pullback inside a positive long trend have distinct forward-return distributions?
- Does proximity to a trailing high add information after controlling for momentum?
- How stable are coverage, IC and quantile spreads through time and across membership changes?

These are pipeline diagnostics and hypothesis generation. They are not strategy optimization or evidence of deployable alpha.

### Acceptance

- Every feature input has `available_ts <= decision_ts`.
- Close-derived features cannot use the same session's close as an execution price.
- Membership boundary, unresolved identity and benign-exit fixtures pass.
- Labels are inaccessible to feature functions and agree with hand-calculated fixtures.
- pandas/reference and Polars outputs agree within declared tolerances.
- Repeating one run from its directory reproduces logical hashes and metrics.
- Coverage and missing-state reports accompany every IC/quantile result.
- Every cross-sectional calculation retains the official universe denominator and each excluded member's state: if 57 of 60 official TOP60 members have usable prices, the output records and ranks `57/60` rather than silently redefining the universe as 57.

### Price-basis rebuild checkpoint

The 2026-08-25 coverage and split forensics in `GPW_PHASE_A_PRICE_BASIS_READINESS.md` refine this phase without changing the accepted Phase A artifact:

- The final 2026-08-26 targeted audit passes expected-trading price coverage from the earlier complete-PIT boundary: 99,721/99,721 observations, zero unexplained price gaps, and zero additional price histories. The recommended future evaluation start is 2019-12-23 with feature-specific eligibility retained.
- The other 59 official rows are explicit non-trading states. Strict every-session 252-bar readiness is 98,517/99,780; 1,263 windows remain ineligible because of listing age, no-reference/non-trading dates, or post-exit dates rather than acquisition failures.
- Full selected-source volume coverage remains incomplete on PLAY 2020-06-03 and CCC 2020-06-10. No fields may be spliced; any Yahoo PLAY substitution must be an explicitly approved whole-bar override.
- Source/native panel construction may proceed, preserving one complete vendor bar, provenance, and displayed-volume uncertainty.
- Source-native technical features may not proceed across splits. Bossa is proven mixed: SUNEX is already split-adjusted, while BLOOBER and CASPAR are raw through their tested splits. Investing.com BLOOBER is already split-adjusted.
- Before a new Phase A run, build a complete authoritative split-event inventory for the warm-up/evaluation universe, classify every selected series/event as adjusted, unadjusted, not applicable, or unknown, and publish a versioned split-adjusted OHLC/volume view. Unknown and double-application states fail closed.
- Define `raw price return` as the split-neutral price-only return without cash distributions and compute it from split-adjusted close. Do not compute it blindly from source-native close.
- A price-only Phase A variant is a changed research basis around cash distributions; it cannot be called a reproduction or replacement of the accepted Stooq-based Phase A. Economic momentum and forward investor-return labels require the later ATS total-return layer unless the owner explicitly accepts the changed price-only question.

Checkpoint status: **CONDITIONAL GO for source/native ingestion and split-normalization work; NO-GO for an accepted replacement Phase A run today.**

## Phase B — Harden canonical data, without building a storage service

Formalize the successful slice into reusable data contracts.

### Implement

- Arrow schemas for security identity, source/native bars, derived split-adjusted bars, separately named price-only returns, membership, macro data, corporate actions and manifests. Total-return facts remain a distinct later derivation.
- Compact ZSTD Parquet publication, initially one or a few files per `(table, market, frequency)`.
- Benchmark-derived writer defaults: ZSTD level 3 and 122,880-row groups, kept in configuration.
- Immutable logical dataset version directories and small manifest/pointer files.
- DuckDB views built from the manifest's explicit file list.
- Polars lazy pipelines for validated feature inputs.
- US daily ingestion after GPW reproduces exactly.
- A simple full-version rebuild for new data or corrections. At the present size, this is preferable to deltas and compaction.

### Do not implement yet

- automatic annual/era/month partition selection;
- delta-file accumulation or scheduled compaction;
- a storage daemon, database server or distributed scheduler;
- generalized schema-evolution machinery beyond fail-closed version checks.

### Acceptance

- Semantic-key, row-count and numeric hashes match the trusted Phase A slice.
- Duplicate keys, alias overlaps, schema drift and invalid OHLCV fail closed.
- A published dataset version never changes and a run never follows `latest`.
- A failed publish leaves the previous manifest queryable.
- One correction produces a new complete version with explicit lineage.
- Deleting derived caches cannot remove raw or canonical facts.

## Phase C — Readable daily portfolio ledger

Promote the narrow prototype only after signal diagnostics are trustworthy. Optimize for inspectability, not milliseconds. The decision-oriented Phase A report changes the validation emphasis, not the accounting architecture: momentum remains data-confounded, the strong-stock pullback thesis is not supported, and proximity to a strict trailing high plus the extreme-volatility tail are only promising conditioning hypotheses. Phase C therefore validates execution and ledger semantics with frozen external intents; it does not select, optimize or promote a strategy.

The Phase A diagnostic labels begin at a decision-session close that is not executable at the 08:45 decision timestamp. Phase C must bridge that distinction explicitly: close-derived information may create an intent, but the earliest ordinary fill is the next eligible session open. Diagnostic close-to-close results are context only and are not reconciliation targets for executable P&L.

### Implement

- immutable target-weight/order-intent inputs;
- intent provenance that pins the data manifest, feature/signal version, decision timestamp, official universe denominator, usable/eligible counts and every excluded member state;
- next-session-open translation and fills;
- shared cash, fractional reference mode and later integer/rounding mode;
- positions, valuations, turnover, commission and slippage ledgers;
- missing open, suspension, unresolved and non-tradeable states;
- merger conversion, cash takeover, delisting and identifier-change hooks;
- an explicit adjusted-bar/corporate-action policy that prevents double application of splits, dividends or takeover terms;
- explicit treatment of target weight made unavailable by missing or rejected members: retain it as cash or reject the intent according to configuration, never silently renormalize the remaining 57/60 members;
- configurable calendars and explicit rejection/retry reasons.

Signal calculation stays outside `ats_portfolio`. For realistic integration fixtures, use a small frozen intent stream that can exercise momentum plus proximity-to-high and an extreme-volatility condition, and retain the unsupported deep-pullback rule only as a negative-control fixture. Do not tune thresholds, holdings, rebalance dates or horizons in Phase C, and do not present the resulting ledger as evidence of alpha.

### Golden scenarios and acceptance

- No fill occurs before signal availability or on an ineligible bar.
- A close-derived intent never receives a same-close fill; next-open eligibility is proven on boundary fixtures.
- Cash plus marked positions equals equity within tolerance after every event.
- Fill quantities, cash movements and position changes reconcile independently.
- Missing bars never become implicit zero-price or forward-filled executions.
- A 57/60 session retains denominator 60, all three unavailable-member states and any resulting unallocated cash; it is not silently converted into a 57-member universe or renormalized portfolio.
- Merger, cash-takeover, suspension and benign-exit fixtures balance shares/cash.
- Adjusted-bar and explicit-corporate-action combinations fail closed unless their interaction policy proves that value is applied exactly once.
- Replaying the same manifests and config reproduces ledger hashes.
- Every realistic intent/fill date is covered by its pinned canonical Phase B manifest. The 2026 report extension may inform fixture choice, but it cannot drive a 2026 ledger until a compatible canonical Phase B version is published.

Zipline-reloaded is the first optional challenger only after this ledger is stable. PyBroker requires a clean isolated environment before retry. LEAN and NautilusTrader remain future interface adapters.

## Phase D — Chronological ML workbench

### Implement

- date-grouped expanding/rolling splits;
- validation splitting based on information intervals: training feature/label intervals must not overlap information unavailable at the validation decision boundary; for simple forward-return labels the default purge is at least the maximum label horizon, but overlapping events, holding-period targets or other sampling structures may require a larger or structurally different exclusion;
- fold-local preprocessing;
- SGD/linear baseline, LightGBM primary and XGBoost CPU/GPU challenger;
- bounded Optuna studies only after one deterministic baseline;
- stored prediction lineage: model/run version, features, data manifest, horizon and `as_of_ts`.

### Acceptance

- No session is divided across train and validation.
- All transformers fit only on training dates.
- The untouched recent holdout is not used for tuning.
- CPU/GPU runs record package build, driver, device, dtype and transfer behavior.
- Predictions can be regenerated from a run directory without MLflow.

## Phase E — Optimize only measured pain (ongoing, trigger-driven)

Profile representative GPW, US and intraday workflows. Add one mechanism at a time only when its trigger is met.

| Candidate optimization | Evidence required before implementation |
|---|---|
| Time partitioning | A representative query/rebuild SLO is missed or file size materially harms publication, correction or maintenance; 2 GiB is only a configurable review default |
| Delta publication and compaction | Update cadence/rebuild time materially delays research; first measure storage amplification and recovery behavior |
| Feature-value cache | Repeated deterministic feature computation is a measured dominant cost |
| Security bucket | A large intraday partition misses security-query SLO; current 16-way/3,477-file result is the rejected baseline |
| MLflow | Filesystem runs become difficult to find/compare; it indexes but never replaces portable manifests |
| GPU optimization | A representative model is training-bound after data preparation and transfer costs |
| Dask/Spark | A representative optimized workflow cannot meet memory/runtime needs on the workstation |
| PostgreSQL/TimescaleDB | Concurrent writers, remote services or transactional APIs actually exist |
| Packaged event engine | Golden-ledger parity plus a concrete realism/maintenance advantage |
| LEAN | A funded supported-broker/live deployment requirement |
| NautilusTrader | Higher-frequency live state/order-book throughput is required |

## Phase F — Reporting and operating runbook (after the slice)

Create deterministic HTML/PNG reports for data coverage, factor diagnostics, ML evaluation and ledger reconciliation. Add CLI commands and restart/rollback instructions only for workflows that now exist. Reports link to config, manifest, code commit, data hashes and artifacts.

Acceptance:

- A fresh machine can reproduce the small GPW fixture from the retained environment/configuration.
- Failed and cancelled runs remain diagnosable.
- A report never lacks its dataset/universe/feature versions.
- Strategy-return displays carry the assumptions and “not alpha evidence” warning.

## Suggested repository boundaries

Create only modules required by the active phase:

```text
src/ats_contracts/      # minimal identity, timing, feature and manifest types
src/ats_research/       # Phase A PIT joins, labels, ranks, IC and quantiles
runs/                   # ignored artifacts; portable schema documented and tested

# Add in later phases:
src/ats_data/           # Phase B canonical publication and DuckDB views
src/ats_portfolio/      # Phase C event ledger and accounting
src/ats_ml/             # Phase D chronological datasets and models
```

Engine adapters remain at the edges. A feature definition cannot import an event engine, and an event engine cannot resolve raw vendor tickers.
