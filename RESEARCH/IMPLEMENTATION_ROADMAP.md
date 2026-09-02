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

## Phase D — Pooled chronological ML research

Phase D is a research-led test, not a general ML-platform buildout. Its bounded
question is whether compact, identity-blind numerical descriptions of stock path,
market-relative behavior, cross-sectional context and market state add material,
stable predictive information beyond the conventional GPW factors already
studied and can identify selective, bounded swing opportunities. The detailed
contract is in `PHASE_D_POOLED_ML_RESEARCH_CHARTER.md`.

The repaired bounded proximity-to-high result remains a frozen conventional
benchmark, not deployment-ready alpha. Do not tune its lookback, threshold,
horizon, regime filter or combinations. Phase D may use its exact signal
definition as a feature and may diagnose ranking within its Q5 population, but it
is not an active optimization track.

The first experiment remains within the exact-PIT TOP60 panel. Expansion to all
GPW securities would reopen historical-universe, identity, delisting and source
coverage work and is conditional on successful evidence from the bounded panel.
The input remains the pinned research-grade split-normalized candidate panel with
its source, volume-quality, missing-state and corporate-action caveats; Phase D
does not silently promote it to a canonical Phase B publication.

Pooled learning does not imply continuous allocation. Every eligible
security-session may contribute a learning example, but the intended action is an
abstaining opportunity detector: cash/no position is the default and no trade is
generated when a frozen absolute or calibrated opportunity gate is not met. A
cross-sectional tail rule alone is insufficient because it would force a trade on
nearly every session. Rank IC remains an information diagnostic; signal frequency,
tail-conditioned outcomes, future path/excursion behavior, concentration and
eventual trade-level economics govern actionability. The initial action hypothesis
is long-only; negative-tail outcomes are diagnostics, not authorization for a
short-selling branch.

### Phase D0 — Freeze the scientific contract

**Final pre-D2 amendment, 2026-09-01:** D0 v3 replaces the accepted expanding
annual chronology with a locked January/July procedure. The model at each refit
uses the immediately preceding, month-aligned 36 calendar months. Inside that
window it fits/scores three consecutive prequential six-month calibration blocks
after 18, 24 and 30 months of history, freezes the unchanged `max(1%, linear
q90)` cell threshold, refits on every label-mature row in the window and scores
only the next calendar half-year. The locked object is this deterministic
procedure, not one permanently frozen fitted estimator.

Selection uses complete 2023 H1/H2 blocks, development confirmation uses complete
2024 H1/H2 blocks, and locked evidence uses complete 2025 H1/H2 plus 2026 H1.
Annual stability includes only complete decisive years 2024 and 2025. Partial
2026 H2 through 2026-08-18 is monitoring only and cannot enter selection,
confirmation, locked, annual, concentration or verdict gates.

The v3 authority is `PHASE_D0_EXPERIMENT_PLAN_v3.md` and
`source/python/configs/phase_d0_reference_v3.json`. The accepted D0 v2 plan,
manifest, audit and unchanged 30-feature registry remain preserved parents.
Chronology/calibration and their population/minimum mappings are the only
scientific changes; models, features, target, thresholds, metrics, numerical
gates, price basis and caveats are unchanged. This is the final major design
amendment before D2.

The Phase D0 experiment plan and machine-readable contracts are frozen at
`PHASE_D0_EXPERIMENT_PLAN.md`, `source/python/configs/phase_d0_reference.json`,
and `source/python/configs/phase_d0_feature_registry.json`. They define four
disjoint C/P/X/M blocks, the fixed 2x2 model comparison, exact chronological
folds and endpoint-derived purge, an abstaining score gate, numerical
continuation thresholds, deterministic D1 structural resolutions, and a
requirement audit. The v2 amendment requires every decisive rank/stability gate
to pass against both fixed conventional cells and uses fractional score-boundary
weights instead of identity to resolve frequency-matching ties. The D0 scientific
contract remains frozen and preserved, and its four authoritative byte anchors
remain unchanged. Historical whole-repository D0 validation is replayed
at accepted Git checkpoint `cbddb4ff13f4452aa37f427f0f3c09a3f3da1ae4`;
mutable current guidance is not rolled back to satisfy that historical manifest.
D0 authorizes no real predictive execution.

Before inspecting any Phase D prediction result:

- pin the candidate-panel manifest and exact member-session universe;
- retain the accepted stored `label__open_to_open__20` definition on the
  `split_adjusted_price_return` basis and exact Phase A v2
  decision/next-open/20-session endpoint semantics as the sole primary horizon;
  evaluate it cross-sectionally without rewriting the stored label as a
  relative-return fact;
- retain 5- and 10-session outcomes, if used, as named secondary diagnostics
  that cannot select the winning model;
- define and fingerprint a compact feature set in four explicit, disjoint
  blocks: conventional stock state (C), stock path/evolution (P), stock-relative
  cross-sectional context (X), and frozen market state (M);
- make the market-state block numerical and compact: multi-horizon WIG trend,
  market drawdown, short/long realized-volatility state, TOP60 breadth,
  cross-sectional dispersion, and correlation/co-movement or leadership
  concentration where it is cheap and PIT-safe;
- freeze a market-state ablation comparing rich stock-state features without
  that block against the same representation with it;
- freeze the minimum 2x2 comparison: conventional versus rich representation,
  each under a regularized linear model and fixed LightGBM model;
- define date-grouped chronological development folds, information-interval
  purge/embargo rules and one later locked historical test segment;
- call that segment a locked historical test, not genuinely untouched evidence,
  because outcomes through 2026-08-18 have influenced the research program;
- freeze fold-local preprocessing, missing-value behavior, seeds, evaluation
  metrics, concentration checks, material-improvement thresholds and the exact
  stop/continue rule; and
- freeze an abstaining score-to-opportunity rule using development-training
  information only, including an absolute or calibrated hurdle, signal-expiry and
  duplicate/overlap semantics; do not require a fixed number of selections per
  session or silently lower the hurdle when no opportunity qualifies;
- define prospective maximum-favourable excursion, maximum-adverse excursion and
  time/path diagnostics as future-only evaluation labels that are inaccessible to
  feature and model-fitting code; and
- hash the plan and configuration before any real predictive metric is emitted.

The primary model comparison requires the selected rich representation to pass
decisive rank, stability and tail gates separately against both fixed conventional
cells, not merely the conventional family selected in 2022. A richer model that
approximately ties either conventional model fails the incremental-value objective.

### Phase D1 — Build only the minimum workbench

**Checkpoint 2026-09-01: v3 complete — PASS.** The controlling evidence is
`PHASE_D1_READINESS_v3.md`, `PHASE_D1_REQUIREMENT_AUDIT_v3.json`,
`PHASE_D1_MANIFEST_v3.json` and immutable run
`phase-d1-v3-structural-ed315ee058c7e0e7ce51`. The focused D1 suite has 80
passing tests and the supported complete suite has 187. All eight P features
remain preserved; every outer, inner-fit, inner-score and final-fit structural
minimum passes. No real label value, fit, prediction, score, performance result
or D2 execution occurred.

Accepted D1 v2 readiness and immutable run
`phase-d1-structural-b4fb9bbc480c2026e423` remain preserved as the parent
checkpoint. V3 adds only the semiannual splitter, label-blind minimum resolution,
synthetic prequential separation and locked-generation firewall required by the
final chronology amendment.

Add a small `ats_ml` boundary for:

- manifest-pinned D0/input loading and the exact security-session observation
  builder;
- the 30 registered PIT feature calculations, synthetic-only primary-label
  builder, chronological folds and endpoint-derived purge;
- identity-excluded four-cell matrices with immutable ordered semantic row
  ledgers shared by matrices, targets and scores;
- fold-local Ridge preprocessing and LightGBM-native missingness plus fixed,
  deterministic Ridge and LightGBM adapters that fit/predict only on
  content-pinned repository fixtures;
- strict abstention and pure fractional boundary-tie mechanics; and
- immutable evidence for only the four frozen label-blind structural
  resolutions, including asserted candidate/WIG and membership/market-state
  calendar equality.

Session-level predictive evaluation, paired comparisons, uncertainty,
opportunity tails, episode accounting, concentration, ablations and verdict
generation remain Phase D2 work. Their definitions in the frozen D0 contract do
not move their implementation or execution into D1.

D1 validates this machinery with hand-calculated, synthetic and mechanically
bounded fixtures. After separate owner authorization it may inspect real data
schemas, counts, date ranges, missingness and eligibility, and may compute the
registered predictor values through 2024-12-30 solely to apply the frozen
label-blind P duplicate rule. It must freeze and return the owner-reviewed
`phase_d1_structural_resolution.json` before any real model fit or prediction.
D1 may not load or derive realized forward labels, emit validation scores, or
publish or inspect real predictive performance. No locked historical test data
are opened by a model in D1.

### Phase D0/D1 historical acceptance checkpoint — 2026-09-01

**State at this checkpoint: D0/D1 v3 PASS for requesting separate owner review
of D2; Phase D2 was not yet authorized.**

- The owner-approved plan is frozen and hashed before any real model result.
- The primary label is unchanged and inaccessible to feature computation.
- No session is divided across fit, inner score or outer evaluation blocks.
- Every January/July refit uses only its trailing 36-calendar-month estimator
  window; feature warm-up before the window cannot become a model row.
- Training feature/label information intervals do not cross a validation or test
  decision boundary; purge is derived from those intervals rather than hard-coded
  merely as a horizon number.
- Exactly three chronologically prior out-of-fit score blocks determine each
  cell threshold, and the final refit cannot recalculate it.
- Every fitted transformation uses training dates only; same-session
  cross-sectional transforms are explicit and deterministic.
- Official denominator 60, eligible count and every excluded-member state remain
  present in the observation and structural evidence.
- Identity-blind columns are enforced by schema allowlist and negative tests.
- Matrices, targets and scores are bound to the same ordered semantic keys, while
  the four synthetic representation/model cells use identical folds and rows.
- Synthetic opportunity-gate fixtures can abstain and use identity-neutral
  fractional boundary ties; no real gate has been calibrated.
- Future excursion/path labels are inaccessible to features, preprocessing,
  fitting and opportunity calibration.
- Synthetic known-signal, no-signal, leakage and shuffled-label controls behave
  as expected.
- Observation, split, matrix, target and score fixtures reproduce without MLflow
  or notebook state, and the real structural resolution is immutable.
- A requirement-by-requirement audit is `PASS`, `FAIL` or `NOT PROVEN`; at this
  historical checkpoint, owner approval was required before Phase D2 could
  inspect real predictive results.
- Locked D2 generation must proceed 2025 H1, 2025 H2 and 2026 H1 in simulated
  historical time and be completely fingerprinted before outcomes or metrics are
  accessible.

### Phase D2 automatic authorization overlay — 2026-09-01

The owner's focused-repair instruction supersedes the remaining manual-review
gate without rewriting the historical D1 state. Under
`PHASE_D2_AUTHORIZATION_OVERLAY.md`, Phase D2 becomes authorized automatically
only after the repaired v3 baseline is committed and clean post-commit checks
pass for the composed half-year gate mappings, refit/availability firewall
bindings, regenerated manifests, D0/D1 validators, independent reproduction,
focused/full/regression suites and accepted-parent preservation.

The repair task stops after that durable baseline and does not execute D2. Once
activated, authorization covers one separately pinned execution of the frozen
D2 study, with prediction generation/fingerprinting mechanically preceding
outcome attachment/evaluation. Phase D3, portfolio translation, optimization,
deployment and design changes remain unauthorized.

**Overlay outcome on 2026-09-02: ACTIVATED AND CONSUMED.** Committed baseline
`1dc9bbd` passed the named post-commit checks and authorized exactly one frozen
Phase D2 execution. That execution is complete. The historical D1 checkpoint
above remains an accurate record of its pre-overlay state and is not rewritten.

### Phase D2 — Complete: valid negative result

Phase D2 execution integrity is `PASS` and the predictive evidence package is
`COMPLETE`. `C_LIGHTGBM` and `RICH_LIGHTGBM` were selected within their frozen
representations on the 2023 selection population. Across development and locked
evaluation the rich representation did not establish material, stable
incremental information against both fixed conventional comparators. Its
positive standalone locked IC and mean episode return were insufficient: paired
incremental bounds remained negative, frequency-matched locked tail returns were
worse than both comparators, and chronology, opportunity-count, frequency, and
influence gates failed.

The prediction sequence was generated and fingerprinted before any outcome
attachment. A second execution reproduced the prediction table, sequence, all
evaluation stages, and final scientific identities exactly. An independent
evaluator matched the decisive metrics, 177 gate classifications, and verdict
without importing primary metric functions. The gate matrix contains 99 `PASS`
and 78 `FAIL` results; all execution-integrity, validity, and reproducibility
gates pass. See [`PHASE_D2_RESULTS.md`](PHASE_D2_RESULTS.md),
[`PHASE_D2_REQUIREMENT_AUDIT.json`](PHASE_D2_REQUIREMENT_AUDIT.json), and
[`PHASE_D2_MANIFEST.json`](PHASE_D2_MANIFEST.json).

### Phase D3 — Not authorized; Phase D verdict STOP

The frozen mechanical verdict is `STOP`. Phase D3 execution, portfolio/backtest
translation, optimization, and deployment are `NO` pending owner review. The
negative result is retained as the bounded decision; do not search additional
indicators, horizons, objectives, models, subgroups, or thresholds until one
works.

The original continue rule required material and stable incremental information
over both conventional models, an economically credible selective opportunity
tail, enough non-overlapping evidence, meaningful abstention, and robustness to
time and contributor influence. Those conditions were not met. Valid execution
and positive standalone metrics cannot rescue failed scientific gates.

Deferred unless a successful bounded experiment demonstrates a concrete need:
all-GPW expansion, new sector history, ESPI/event ingestion, sequence/deep models,
ranking objectives, hyperparameter-search infrastructure, XGBoost challengers,
GPU/distributed execution, MLflow and feature-store work.

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
