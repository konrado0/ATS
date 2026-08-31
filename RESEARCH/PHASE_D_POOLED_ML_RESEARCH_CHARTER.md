# Phase D Pooled ML Research Charter

## Status and purpose

This charter defines the owner-approved direction for Phase D. It does not
authorize execution of the ML experiment. Phase D0 is now frozen in
`PHASE_D0_EXPERIMENT_PLAN.md` and its machine-readable contracts; that baseline
is ready for owner review but does not itself authorize Phase D1. Phase D1 must
prove the minimum machinery and freeze the bounded label-inaccessible structural
resolutions without fitting a real model or inspecting predictive performance.
Phase D2 requires a separate later owner decision.

Phase D asks one bounded question:

> Do compact, recurring and identity-blind numerical descriptions of GPW stock
> behavior and surrounding market state add material, stable cross-sectional
> predictive information beyond the conventional OHLCV factors already studied,
> and can that information selectively identify bounded swing opportunities?

The objective is not to prove a "whale" mechanism, discover a deployable strategy
or justify a general ML platform. Any economic interpretation follows evidence;
it is not encoded into the target.

## Relationship to existing ATS evidence

Accepted Phase A, Phase B, Phase C and Phase A v2 artifacts remain immutable and
retain their original meaning. The repaired bounded proximity-to-high result is a
frozen conventional benchmark, not deployment-ready alpha or an optimization
track. Its lookback, threshold, horizon, regime treatment and portfolio
construction may not be tuned in Phase D.

Phase D uses the pinned research-grade split-normalized candidate panel through a
thin, manifest-pinned research boundary. It does not require that panel to become
a canonical Phase B version. Its results remain price-only:

```text
return_semantics = split_adjusted_price_return
cash_distributions_included = false
cash_dividend_price_gaps_preserved = true
```

Authoritative exhaustive split discovery, total-return economics and empirical
auction fillability remain not proven and must remain visible as limitations.

## Initial universe and observation unit

The initial universe is exact-PIT WIG20 plus mWIG40, preserving the official
denominator of 60, feature-specific eligibility and every missing, non-trading,
unresolved and label-unavailable state. The historical panel begins at the
accepted complete-PIT boundary, 2019-12-23, with earlier observations used only
as warm-up where available and required.

The observation unit is a security x decision session. Security rows on one date
are not independent samples: they share market shocks, adjacent observations
overlap, and forward labels overlap. Splits and inference therefore operate on
date groups and information intervals, while evaluation is primarily
session-level.

Expansion to a broader GPW universe is out of scope until the bounded TOP60 study
passes. A broader universe would require a separately justified PIT eligibility,
identity, delisting and source-coverage contract.

## Prediction contract

The primary target is the existing 20-session `label__open_to_open__20` on the
`split_adjusted_price_return` basis, using the exact accepted Phase A v2 decision,
next-open and endpoint semantics. The stored label remains an absolute
price-return fact. Predictions are evaluated cross-sectionally by decision
session; the label is not needlessly rewritten as a relative-return dataset.

Five- and ten-session labels may be retained only as predefined secondary
diagnostics. They cannot choose the model, feature representation or verdict.
Every label must retain endpoint availability and exit/unresolved state rather
than silently dropping difficult outcomes. A material unresolved-outcome bias is
a data gate, not a model underperformance result.

## Pooled learning and selective economic action

The model may learn from every eligible security-session, but its intended
economic application is not an always-invested cross-sectional portfolio. It is
an abstaining detector of bounded swing opportunities:

- cash/no position is the default state;
- high relative rank alone does not require a trade;
- an opportunity is emitted only when a frozen absolute or training-calibrated
  score/probability hurdle is met;
- zero opportunities on a session is a valid and expected result;
- the hurdle is never lowered to fill a quota or maintain exposure; and
- multiple adjacent signals for one security are correlated observations, not
  automatically independent trades.

The initial action hypothesis is long-only. Low-score and negative-outcome tails
remain useful controls for discrimination, but Phase D does not open a parallel
short-selling strategy or borrow/financing implementation.

Phase D0 must freeze the score-to-opportunity mapping, its training-only
calibration, expiry, duplicate/overlap treatment and minimum evidence needed to
evaluate it. A purely cross-sectional top-N or top-quantile gate is insufficient
because it would force nominal opportunities even when all expected outcomes are
weak.

The initial economic horizon remains the accepted bounded 20-session contract.
Phase D2 diagnoses opportunities but does not optimize stops, profit targets,
holding periods, entry delays or position sizing. If Phase D passes, a later
single Phase C translation must freeze one trade lifecycle before execution and
must allow unused capital to remain cash.

## Frozen feature representations

The Phase D0 registry uses four disjoint blocks and 30 predictors: C conventional
stock state, P stock path/evolution, X stock-relative cross-sectional context,
and M frozen market state. Exact names, formulas, lookbacks, availability,
missingness and implementation-source obligations are in
`source/python/configs/phase_d0_feature_registry.json`. The representation is
compact and economically interpretable; it is not a technical-indicator library.

### C. Conventional stock state

Use the exact established stock-level definitions where available: both frozen
proximity forms, medium-term momentum, five-session return, short realized
volatility and relative volume. C contains no WIG or other global market field,
including renamed, rescaled or lag-shifted M variables. The earlier phrase
"basic WIG context" is superseded for the D0 comparison so the M ablation remains
interpretable.

### P. Stock path and evolution

Describe how the current state developed with no more than eight predefined,
economically distinct path features. Phase D0 freezes two directional horizons,
path efficiency, positive-return persistence, drawdown depth, recovery from a
recent low, volatility evolution and close location in the recent high-low
envelope. If separately authorized, D1 may compute the registered predictor
values through 2024-12-30 only to apply the frozen label-blind duplicate rule;
realized forward labels and target evidence remain inaccessible. The resolved
P set is owner-frozen before the first real model fit, and D1 cannot replace a
removed feature using target evidence.

### X. Stock-relative cross-sectional context

Describe a stock's same-session position using four deterministic ranks of
registered stock features. Every calculation uses only already available inputs,
records the official denominator, eligible count and excluded states, and is
invariant to ticker, vendor and row order. X contains no WIG or direct market
aggregate and cannot reconstruct an M variable with C and P.

### M. Frozen market state

Market state is an explicit numerical feature block, not a hidden binary filter.
Carry the complete corrected pre-Phase-D v2 block of 12 WIG trend, drawdown,
volatility, TOP60 breadth, dispersion, correlation and leadership variables.
Select or remove none using historical Q5 association and add no optional state
variable.

The predefined market-state ablation compares C+P+X against C+P+X+M with the
fixed LightGBM family. Its question is whether explicit market state adds
information beyond stock state, stock path and cross-sectional context—not which
hand-selected regime filter makes returns look best.

## Identity-blind primary model

The primary feature schema excludes ticker, ISIN, `security_id`, nominal price,
raw share volume and other direct identity fields. Per-security normalization may
use only historical information available at the decision time and must not be
globally fitted. Source and volume-quality fields remain available for auditing
and masks but cannot silently become identity proxies in the primary model.

Identity-blind inputs do not prove transfer to unseen securities. Report
per-security contribution and prediction concentration. An unseen-security or
identity-predictability diagnostic is optional confirmation if it is inexpensive;
it is not a prerequisite for the core decision.

## Minimum model and representation comparison

Run at least the following frozen 2x2 design on identical folds and comparable
rows:

| Representation | Regularized linear | LightGBM |
|---|---:|---:|
| Conventional | required | required |
| Rich state | required | required |

This separates representation value from nonlinear model capacity. The primary
challenger is the best rich-state model and the primary reference is the strongest
conventional model. Rich LightGBM beating only conventional linear is
insufficient if conventional LightGBM performs equally well.

Hyperparameters must be fixed or selected through a small, predefined process
inside development folds. No Optuna service or broad search is allowed. A richer
model that approximately ties the strongest conventional model fails because its
complexity has not earned its cost.

## Chronological validation

Phase D0 defines explicit development folds and one later locked historical test
before results are inspected. Requirements are:

- whole-session train, validation and test assignment;
- chronological training only;
- exclusion based on feature/label information intervals so no training example
  overlaps information unavailable at a validation or test decision boundary;
- fold-local fitting of every learned transform, imputer, winsorizer, scaler,
  residual model and estimator;
- explicit treatment of overlapping labels and session dependence;
- no random row split; and
- one-time opening of the locked historical test after representation, model
  parameters and selection rules are frozen.

The later segment is a locked historical test, not genuinely untouched evidence,
because outcomes through 2026-08-18 have already influenced the broader ATS
program. True forward validation begins after that date.

## Evaluation and incremental-value question

Primary evaluation is session-level and paired on common eligible rows. Phase D0
must predefine exact estimators, uncertainty method and numerical materiality
thresholds before model execution. At minimum report:

- mean, median and distribution of session-level rank IC;
- paired incremental IC versus the strongest conventional model;
- tail-conditioned forward outcomes under a frozen abstaining opportunity gate;
- signal frequency, idle sessions, overlap clusters and effective independent
  opportunity count;
- hit rate against the predefined economic hurdle and comparison with the same
  frequency-matched conventional operating point;
- future maximum-favourable excursion, maximum-adverse excursion, time to
  excursion and relevant path shape, all implemented as inaccessible future-only
  evaluation labels;
- top-ranked and quantile economic separation and monotonicity as diagnostics;
- results by chronological fold, year and predefined market-state slices;
- prediction and outcome concentration by date and security;
- expected denominator, eligible count, missingness and label availability;
- stability after removing the strongest period and largest contributors; and
- incremental ranking within the frozen proximity Q5 population as a diagnostic.

The proximity-Q5 diagnostic cannot select an alternative target, model or feature
set. Model explanations and feature importance characterize a model; they do not
prove a mechanism or compensate for weak predictive evidence.

Rank IC is not the economic objective. A model with improved average rank IC but
no stable, sufficiently populated and economically useful opportunity tail does
not pass. Conversely, a selective tail cannot pass merely by becoming extremely
rare: Phase D0 must freeze minimum evidence and concentration requirements before
results are seen.

## Stop and continuation gate

Data integrity, causality, fold correctness and reproducibility must pass before
economic evidence is interpreted. Phase D continues only if the rich
representation shows material and stable incremental information over the
strongest conventional model in both chronological development validation and
the locked historical test, with a useful selective opportunity tail, meaningful
cash/no-position behavior, sufficient non-overlapping evidence, and no dependence
on a small number of dates, years, regimes or securities. Positive standalone
rank IC is insufficient.

Phase D0 freezes exact numerical thresholds in `PHASE_D0_EXPERIMENT_PLAN.md` and
`source/python/configs/phase_d0_reference.json`. They remain proposals for owner
approval and may not be calibrated after seeing real model results.

If the rich representation ties, inconsistently beats, or loses to the strongest
conventional model, the verdict is to stop or descope the ML line. Do not respond
by searching more indicators, horizons, models or filters. A clean pass authorizes
only one frozen Phase C portfolio translation and later forward observation—not
deployment.

## Minimum implementation boundary

Reuse `ats_research` feature, identity, PIT, timing, label, artifact and hashing
machinery. Add only the small `ats_ml` modules required for manifest-pinned
dataset assembly, chronological splits, fold-local preprocessing, two model
adapters, session-level evaluation and portable run artifacts. Large generated
datasets and runs belong under `D:\Stock\data\ATS\phase_d_ml`; code, fixtures,
plans and concise reports belong in the ATS repository.

Deferred until a successful bounded result creates a concrete need:

- all-GPW expansion;
- new PIT sector history;
- ESPI or other event ingestion;
- sequence and deep models;
- learning-to-rank objectives;
- broad hyperparameter optimization;
- XGBoost challengers;
- GPU or distributed execution;
- MLflow, feature stores and general experiment services.

## Phase boundaries

Phase D0 freezes the research contract and stops for owner review. Phase D1 is
not yet authorized; if separately approved, it proves the minimal machinery on
fixtures and computes only the registered, label-inaccessible feature values
needed to freeze `phase_d1_structural_resolution.json`. It stops before any real
model fit, prediction, validation score, or performance calculation. Phase D2
executes the frozen historical study only after another owner approval. Phase D3 issues the
final `STOP`, `CONTINUE TO ONE BOUNDED PORTFOLIO TEST`, or `NOT PROVEN` verdict.
