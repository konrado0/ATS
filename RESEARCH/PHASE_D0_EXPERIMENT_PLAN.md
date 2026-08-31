# Phase D0 pooled-ML experimental contract

**Status:** frozen D0 v2 amendment; ready for renewed owner review; Phase D1 and all real predictive execution remain unauthorized

**Contract version:** `phase-d0-20260831-v2`

**Amendment boundary:** v2 preserves every v1 input, feature, model, fold, threshold, and phase boundary. It changes only two contract defects identified in owner review: every decisive incremental rank/stability gate now compares the selected rich challenger separately with both fixed conventional cells, and same-session frequency matching uses identity-neutral fractional boundary-tie weights. No predictive result was inspected and no D1 work began.

**Research classification:** decision-grade experimental design. This document is not deployment validation, a model result, a strategy result, or evidence that an opportunity exists.

Machine-readable authorities:

- `source/python/configs/phase_d0_reference.json` — timing, eligibility, model, split, opportunity, evaluation, and decision rules;
- `source/python/configs/phase_d0_feature_registry.json` — exact predictor definitions;
- `RESEARCH/PHASE_D0_MANIFEST.json` — frozen inputs and hashes;
- `RESEARCH/PHASE_D0_REQUIREMENT_AUDIT.json` — requirement-by-requirement status; and
- `RESEARCH/prototypes/phase_d0/validate_phase_d0.py` — contract-only validator.

If prose and machine-readable content differ, validation fails and the D0 contract is not executable. No path may follow a mutable `latest` pointer.

## Decision design

### Exact decision

Phase D must decide whether to continue or stop the bounded pooled-ML line:

> Continue only if a compact, ticker-independent rich representation of stock evolution, cross-sectional context, and frozen market state materially, stably, and economically improves selective long-only opportunity identification over the strongest conventional OHLCV model. Otherwise stop or descope the pooled-ML line.

An approximately equal result is failure because the richer representation has not earned its complexity. A pass authorizes at most one later frozen Phase C translation and prospective observation; it does not authorize deployment.

### Cheapest credible experiment

Use the already pinned exact-PIT TOP60 candidate panel, one unchanged continuous target, 30 registered predictors, two fixed squared-error estimators, four primary cells, one annual model-family selection fold, two later annual development-confirmation folds, and one locked historical test. Use one LightGBM market-state ablation and only the prespecified diagnostics. This is the smallest experiment that separates representation value from nonlinear capacity without reusing selection outcomes as confirmation and tests the intended abstaining opportunity tail.

### Must-have validity work

- exact PIT decision-session membership and official denominator 60;
- preceding-session feature availability and exact next-open label timing;
- feature-specific exact-window eligibility with no synthetic bars;
- stored label isolation from feature, preprocessing, selection, and calibration code;
- whole-session chronological splits and endpoint-derived purge;
- fold-local learned transformations and deterministic model settings;
- common primary comparison rows and visible eligible/scored denominators;
- positive predictor allowlist and identity-proxy negative tests;
- overlap-aware session inference, opportunity clustering, and concentration checks;
- immutable input, document, configuration, environment, and implementation hashes; and
- a fully frozen pass/fail gate before real scores or outcomes are inspected.

### Useful but non-gating diagnostics

- 5- and 10-session open-to-open robustness labels;
- C+P+X versus C+P+X+M LightGBM attribution;
- rank and tail behavior within the frozen max-high proximity Q5 population;
- monotonicity, prediction distribution, and model explanation summaries;
- market-state slices, future excursion/path descriptions, and source-switch sensitivity; and
- negative-score and shuffled-label controls.

None may select a model, feature, threshold, label, or rescue a failed primary gate.

### Explicitly deferred

Phase D1 implementation, real model fitting or predictions, Phase D2, all-GPW expansion, new sector/event/macro data, total-return reconstruction, general corporate-action work, sequence/deep/ranking models, large feature libraries, hyperparameter search, XGBoost, GPU/distributed systems, MLflow, feature stores, Phase C changes, proximity optimization, further market-state research, trade bookkeeping, orders, capital allocation, exits, costs, settlement, and portfolio simulation are outside D0.

### Prespecified stop/continue rule

Every validity gate and every economic/incremental dimension in `decision_gate` must pass in both the declared development evidence and locked historical test where specified. Statistical significance cannot replace materiality; materiality cannot replace stability. Any required failure produces `STOP OR DESCOPE POOLED ML`. No secondary result can reverse it.

## Frozen evidence basis

Phase D uses the immutable research-grade split-normalized candidate panel:

- run `gpw-split-normalization-20260826-v4`;
- manifest SHA-256 `e77ce37cb51c3a1e5608b4b2c9b112abe51635bdae1ce64db0b5aa7d4780331a`;
- panel SHA-256 `c23ffbfc6aaab8bafd466bd980f906ec4476fd051aebcc8c0fa3b7e57a9f8c15`;
- logical hash `447fbadaac4418c04b257bd46bf8daa81b24b2546ac40b0f3ff89763ed9fdd4e`; and
- data basis `gpw_split_adjusted_price_candidate.v1`.

The panel has 99,780 official member-session rows: 1,663 decision sessions from 2019-12-23 through 2026-08-18, exactly 60 official members per session. Its earlier rows are warm-up only. This is a structural observation, not a predictive result.

The basis is `split_adjusted_price_return`: cash distributions are excluded, cash-dividend price gaps are preserved, and no total-return interpretation is allowed. Authoritative exhaustive split discovery remains **NOT PROVEN**. The panel is not promoted to canonical Phase B.

The complete accepted market-state v2 block is pinned by logical hash `b21793076e76f945b72fa1f37bb5a6bab85e40f7e31603ad4ca6d0d7d79a57eb`. Its descriptive association was mixed and it does not define a regime or timing rule.

## Observation, PIT, and eligibility contract

### Row and membership identity

One observation is `(security_id, decision_session, candidate_run_id, contract_version)`. A security is expected only when the pinned panel marks it an official WIG20 or mWIG40 member on that decision session. There must be exactly 60 unique official `security_id` values; any other count fails the session.

The decision timestamp is 08:45 Europe/Warsaw. Stock and WIG predictors end at the immediately preceding official WIG session. Modeled daily close availability is 17:05 on that preceding session. The vendor-latency assumption remains a caveat rather than a claim of measured delivery.

Frozen TOP60 aggregate M features preserve accepted v2 timing: their information-session universe is the 60 official members on the preceding session. X features rank decision-session official members using only each member's already lagged stock feature.

### Exact windows and missing states

Every feature owns its eligibility. A row does not need every registered predictor. Missing price or volume invalidates only dependent features. The common score mask is determined at the decision time by official membership and the four established core C features named in the config; it never consults future-label availability. Fit and outcome masks add an exact boundary-permitted primary label. Label-unavailable and right-censored rows remain scored and stay in frequency/abstention denominators.

An exact window requires every stated official-session observation. There is no forward fill, zero fill, shortened window, endpoint substitution, or synthetic bar. D0 keeps the accepted C formulas but strengthens their prospective Phase D eligibility to an explicit exact-window rule; it does not recalculate or reinterpret accepted Phase A evidence.

Whole-bar source switches do not automatically reset price features. A crossing window is valid only if every required observation is usable, split-normalized under the pinned factor version, and free of unresolved treatment. Volume windows additionally require every observation to be explicitly comparable. Source-switch, lineage, and quality masks remain audit-only and cannot become predictors.

Exclusion codes are closed and machine-readable. Expected, feature-eligible, model-eligible, scored, outcome-evaluable, missing, prelisting, non-trading, unresolved, and label-unavailable states remain distinct. Every cross-sectional output retains official expected count, eligible count, scored count, outcome-evaluable/unavailable counts, excluded count, and reason counts. A result over 57 usable names is shown as `57/60`.

### Structural minimums

Each purged fit interval needs at least 230 decision sessions and 10,000 model rows; the first declared fit has 235 sessions after the label-blind exact-endpoint purge. Each calibration and annual selection/confirmation interval needs at least 200 sessions and 10,000 scored rows. The locked test needs at least 350 outcome-evaluable sessions. Every predictor needs at least 90% valid fit coverage, and session rank metrics require at least 45 members. Failing a minimum fails the affected cell; no boundary or threshold moves after outcomes are known.

## Target and inaccessible future outcomes

The sole primary target is the existing continuous `label__open_to_open__20`:

```text
split_adjusted_open[t+20] / split_adjusted_open[t] - 1
```

`t` is the decision session; the modeled 09:00 open follows the 08:45 decision. The endpoint is the exact open 20 official WIG sessions later with the decision session counted as session zero. Start or endpoint absence yields a null label; intervening non-trading does not change calendar counting. It is an execution-timing proxy, not auction fillability evidence.

Five- and ten-session open-to-open labels are secondary robustness diagnostics only. Maximum favourable/adverse excursion, time-to-excursion, and forward-path labels are evaluation-only. D1 must make them inaccessible to feature computation, preprocessing, fitting, model selection, and opportunity calibration.

## Exact disjoint predictor blocks

The registry contains 30 model predictors: 6 C, 8 P, 4 X, and the complete 12-feature M block. Audit masks and denominator fields are not predictors.

### C — conventional stock state (6)

| Feature | Exact role |
|---|---|
| `proximity_to_max_high_252` | prior close divided by exact trailing 252-session maximum high |
| `proximity_to_max_close_252` | prior close divided by exact trailing 252-session maximum close |
| `momentum_12_1` | prior `c[i-21] / c[i-252] - 1` |
| `return_5` | prior exact five-session price return |
| `realized_volatility_20` | sample SD of 20 prior exact simple close-to-close returns |
| `relative_volume_20` | prior volume divided by exact 20-session mean minus one |

C contains no global market variable, M copy, or renamed/rescaled/lag-shifted M field. The earlier charter phrase “basic WIG context” is superseded for D0 by placing every market-wide variable in M.

### P — stock path/evolution (8)

| Feature | Distinct economic interpretation |
|---|---|
| `stock_log_return_20` | one-month directional endpoint change |
| `stock_log_return_60` | three-month directional endpoint change |
| `stock_path_efficiency_20` | directness of net movement relative to total path variation |
| `stock_positive_return_share_20` | persistence of positive daily changes |
| `stock_drawdown_depth_60` | depth below the recent closing peak |
| `stock_recovery_from_low_60` | recovery above the recent closing low |
| `stock_volatility_ratio_20_60` | recent volatility expansion/compression |
| `stock_close_location_value_20` | final close position in the recent high-low envelope |

No primitive has more than two horizons. Raw, percent, log, rank, and z-score variants are not duplicated inside P.

Only after separate owner authorization, D1 applies the label-blind duplicate rule using registered predictor values through 2024-12-30. Exact formula/value matches use `1e-12`; P near-duplicates require absolute pooled Spearman correlation at least `0.995` and median session percentile-rank distance at most `0.01`, over at least 200 sessions and 10,000 paired rows. Preference is higher coverage, shorter lookback, fewer raw dependencies, then registry order. D1 may compute these registered predictors and validity masks for this bounded structural purpose, but it must not load or derive realized forward labels, fit a model, emit predictions, score validation rows, or calculate association or economics. The result is frozen and owner-reviewed in `phase_d1_structural_resolution.json` before any real model fit or prediction. Fewer than five survivors or a collision outside permitted P reduction fails closed; no replacement is added.

The complete M block is a frozen exception: its accepted acceleration term is retained even though it is an affine combination of two other M terms. A collision between M and another block is a contract failure, not permission to remove an M feature.

### X — stock-relative cross-sectional context (4)

X contains average-tie within-session percentile ranks of C momentum, max-high proximity, realized volatility, and relative volume. Each uses only eligible decision-session official members, requires at least 45, and records `n/60` plus excluded states. Ticker, vendor, source order, and lineage cannot affect ranks.

No X feature uses WIG or a market aggregate. C+P+X therefore cannot algebraically reconstruct a registered M variable.

### M — frozen market state (12)

The complete corrected v2 block is carried forward unchanged:

- `wig_log_return_20`
- `wig_log_return_60`
- `wig_trend_200`
- `wig_trend_acceleration_20_60`
- `wig_drawdown_252`
- `wig_downside_semivolatility_20`
- `wig_volatility_ratio_20_60`
- `top60_breadth_positive_60`
- `top60_breadth_change_10`
- `top60_return_dispersion_20`
- `top60_average_pairwise_correlation_60`
- `top60_positive_leadership_share_20`

Dispersion is linear-interpolated cross-sectional Q75 minus Q25. Leadership is the top five positive 20-session returns divided by all positive returns. The volatility ratio is centered as `vol20/vol60 - 1`. TOP60 aggregates require at least 45 of the official 60 and never count unavailable members as negatives. No variable is removed or selected by historical association, and no binary regime is created.

## Identity blindness

The only permissible model columns are the registered C/P/X/M feature names after the frozen P duplicate rule. Ticker, ISIN, `security_id`, names, nominal price, raw volume, source/vendor identity, lineage, file path, row order, sector/classification, exclusion text, and missingness indicators are prohibited.

D1 must positively prove exact allowlist equality and invariance to shuffled identity/lineage/source metadata and source-row order. It must negatively inject direct, renamed, hashed, categorical, ordinal, one-hot, frequency-encoded, and target-encoded identity fields, nominal price, raw volume, and missingness indicators and require rejection. Audit fields remain available outside the model matrix.

Identity blindness does not establish generalization to unseen securities. Security contribution and concentration remain required diagnostics.

## Frozen 2×2 comparison and ablation

The four and only four primary cells are:

| Cell | Representation | Estimator |
|---|---|---|
| `C_LINEAR` | C | scikit-learn Ridge |
| `C_LIGHTGBM` | C | LightGBM regressor |
| `RICH_LINEAR` | C+P+X+M | scikit-learn Ridge |
| `RICH_LIGHTGBM` | C+P+X+M | LightGBM regressor |

All use the same primary label, folds, sessions, decision-time common score mask, exact-label outcome mask, and deterministic seed `20260831`.

Ridge uses training-fold median imputation without missing indicators, `StandardScaler`, and `Ridge(alpha=1.0, solver="lsqr", tol=1e-6, max_iter=10000)`. LightGBM uses native NaNs and fixed `LGBMRegressor(objective="regression_l2", n_estimators=300, learning_rate=0.03, num_leaves=15, max_depth=4, min_child_samples=100, reg_alpha=0.1, reg_lambda=1.0, subsample=1.0, colsample_bytree=1.0, n_jobs=1, deterministic=true, force_col_wise=true)`. Both estimate the conditional mean under squared loss, so the 2×2 capacity comparison and absolute score hurdle have the same estimand. No early stopping or search is allowed.

The conventional reporting reference and rich challenger are selected using `MODEL_SELECTION_2022` only by higher equal-session-weighted mean rank IC; an absolute difference at or below `0.002` chooses Ridge. This period selects model families and supplies no confirmation threshold or confidence interval. The pair is recorded before `DEV_2023`, `DEV_2024`, or locked outcomes are opened. Nonselected cells stay reported and cannot replace the selected rich challenger. Conventional selection is naming/reporting only: every decisive incremental rank-IC, chronological-stability, leave-security-out rank, tail, and severe-outcome gate for the selected rich challenger must pass separately against both `C_LINEAR` and `C_LIGHTGBM`. Selection therefore cannot hide a stronger conventional model on either rank or tail evidence.

The single secondary market-state ablation uses the fixed LightGBM configuration and common rows:

```text
C+P+X  versus  C+P+X+M
```

It attributes explicit market-state information and cannot rescue the primary gate.

## Chronological validation and purge

Whole decision sessions are indivisible. Training is expanding and strictly earlier than calibration and evaluation. The exact boundaries are:

| Fold | Fit | Score calibration | Evaluation |
|---|---|---|---|
| `MODEL_SELECTION_2022` | 2019-12-23..2020-12-30 | 2021-01-04..2021-12-30 | 2022-01-03..2022-12-30; selection only |
| `DEV_2023` | 2019-12-23..2021-12-30 | 2022-01-03..2022-12-30 | 2023-01-02..2023-12-29; confirmation |
| `DEV_2024` | 2019-12-23..2022-12-30 | 2023-01-02..2023-12-29 | 2024-01-02..2024-12-30; confirmation |
| `LOCKED_2025_2026` | 2019-12-23..2023-12-29 | 2024-01-02..2024-12-30 | 2025-01-02..2026-08-18 |

For each fit row, the full information interval begins at the earliest raw feature observation and ends at the exact primary-label endpoint open. Before calibration or evaluation, retain a fit/calibration row only when its exact label endpoint timestamp is strictly earlier than the next partition's 08:45 decision timestamp. D1 derives and records exact retained/purged boundary sessions from stored timestamps; it may not merely subtract 20 rows.

For `MODEL_SELECTION_2022`, `DEV_2023`, and `DEV_2024` outcome metrics, a validation row is outcome-evaluable only when its endpoint is strictly earlier than the next fold's validation-start decision timestamp. Locked-test outcomes require an endpoint by 2026-08-18. Boundary-withheld and right-censored rows remain scored and count in frequency/abstention; they are excluded only from outcome metrics and must pass the outcome-evaluability bias gate. No extra embargo is necessary because there is no post-validation training; a future design that trains after validation needs a new contract.

Every imputer, scaler, estimator, and calibration threshold is fold-local. The locked period is a **locked historical test**, not untouched validation. Broader ATS work has already used outcomes through 2026-08-18. Genuine forward evidence begins only afterward.

## Deterministic D1 structural resolutions

D0 defers only values that require label-blind implementation facts:

1. exact last-retained and first-purged sessions at every partition boundary;
2. any P removals under the frozen duplicate rule;
3. four contiguous concentration-bin boundaries using `array_split` on retained evaluation sessions; and
4. D1 code/environment/estimator fingerprints.

Only calendars, registered feature timestamps/values through 2024-12-30, feature-valid masks, implementation bytes, registry bytes, and package metadata are permitted. This is narrow real-feature structural execution, not predictive execution. Realized returns, target associations, model scores, IC, tail outcomes, and economics are prohibited and must remain inaccessible. Each value, rounding rule, bounds, fallback, and destination artifact is specified in `structural_derivations`. D1 must freeze and owner-review `phase_d1_structural_resolution.json` before any D2 model fit or prediction; D2 may not open `MODEL_SELECTION_2022` first and resolve P afterward.

## Selective-opportunity contract

Every model score means predicted absolute 20-session split-adjusted open-to-open price return. A fold model is trained on its purged exact-label fit interval. Its calibration population is every decision-time common-score-mask row in the calibration interval, including rows whose future label is absent. The opportunity threshold is:

```text
max(1.00%, linear empirical 90th percentile of finite calibration scores)
```

Calibration uses scores only, not calibration labels. A row qualifies only when `score > threshold`; equality does not qualify. The hurdle is never lowered and there is no quota. Zero candidates on a session is valid. A prediction is valid for its associated decision-session open only and expires immediately afterward; it is not carried.

Every qualifying security-session is retained for raw frequency. For decisive outcomes, a same-security episode begins at the first qualifying session and absorbs later signals until more than 20 official sessions have elapsed since the preceding signal; only that first observation is the episode anchor. Tail metrics use outcome-evaluable anchors, equal-weight session aggregates, and paired 20-session block inference. Raw overlapping rows cannot pass an economic gate. No observation is called an independent trade.

For each session with `k` outcome-evaluable rich anchors and `n` common outcome rows, frequency matching is performed separately for each conventional cell using score only. If `0 < k < n`, let the boundary be the kth-largest conventional score, `a` the number strictly above it, and `m` the number equal to it. Rows above receive weight 1, rows below weight 0, and every boundary-tied row receives the same fractional weight `(k-a)/m`. If `k=0`, all weights are zero; if `k>=n`, all are one. The weights sum to `k` exactly and are used for all matched conventional means, hit rates, severe rates, distribution summaries, and paired tail contrasts. Weighted quantiles combine equal outcome values and return the smallest outcome whose cumulative weight reaches the requested fraction of total weight. They are invariant to `security_id`, ticker, vendor identity, input row order, and identity reassignment. Rich must beat both C cells separately. This changes no model's own hurdle and is not a portfolio, allocation, or compulsory top-N rule.

## Evaluation hierarchy and inference

Validity precedes economics. The primary hierarchy is:

1. causality, denominator, identity, split, and reproduction gates;
2. paired selected-rich-minus-each-fixed-conventional session rank IC;
3. rich opportunity-tail outcomes and frequency-matched conventional separation;
4. chronological stability and session/security/period concentration; and
5. opportunity count, frequency, abstention, and overlap.

Report mean, median, and distribution of session Spearman IC; paired incremental IC; fold and year results; tail mean/median and eligible-universe separation; severe outcomes at `<= -10%`; hit rate above the 1% economic hurdle; opportunity and idle-session frequency; raw signals and effective episodes; top-session/security/five-security/period shares and HHI; leave-fold and leave-top-security sensitivities; secondary labels; the market-state ablation; and within-Q5 ranking.

The machine-readable metric registry freezes equal-session weighting, episode anchors, same-session conventional matching, severe-rate and leave-security formulas, eligible-year rules, chronological halves/quartiles, and the linear p95 convention. Outcome-unavailable candidates stay in frequency denominators. In pooled confirmation and locked populations, at least 90% of scored rows and rich anchors must be outcome-evaluable, and their evaluability rates may differ by at most 5 points.

Uncertainty is a deterministic paired circular moving-block bootstrap over the full ordered session grid with block length 20, 5,000 samples, and `numpy.random.Generator(PCG64(20260831))`. It draws `ceil(N/20)` circular block starts, truncates to N, and uses identical indices for paired models. Two-sided percentile bounds use linear 2.5%/97.5% quantiles. Undefined replicates are excluded but at least 99% must remain. Session IC is null below 45 paired rows or with constant score/label, remains visible in coverage, and must be defined on at least 90% of outcome-evaluable sessions.

## Frozen continuation gate

All dimensions are conjunctive.

### Incremental rank information

Every following condition is applied separately to selected-rich-minus-`C_LINEAR` and selected-rich-minus-`C_LIGHTGBM`; passing against only the 2022-selected conventional reporting reference is insufficient:

- mean paired delta session IC at least `+0.010` in pooled `DEV_2023`+`DEV_2024` confirmation and locked test; `MODEL_SELECTION_2022` is excluded;
- paired 95% moving-block interval lower bound strictly above zero in both;
- when the named conventional mean IC is positive, relative mean improvement at least 15%;
- each of the two confirmation folds has delta at least `+0.005` and each leave-one-confirmation-fold result is at least `+0.005`;
- positive delta in at least 75% of calendar years with at least 120 outcome-evaluable sessions, excluding 2022 selection, and no eligible year below `-0.020`; and
- both deterministic contiguous locked-test halves have nonnegative delta IC and positive rich-minus-named-C tail separation.

### Selective tail

In pooled development confirmation and the locked test, using episode anchors and equal-weight session statistics:

- rich opportunity mean label minus same-session eligible-universe mean at least `+1.00` percentage point;
- rich opportunity mean minus each same-session frequency-matched conventional mean at least `+0.50` point;
- rich opportunity median label strictly positive; and
- rich severe adverse-outcome rate may exceed either conventional comparator by at most 2 points;
- paired 95% lower bounds for rich-minus-eligible and both rich-minus-C mean contrasts are strictly positive;
- the block-bootstrap 95% lower bound for the rich episode median is strictly positive; and
- the 95% upper bound for each severe-rate difference is at most 2 points.

These are price-only research diagnostics. They do not represent fillable or after-cost portfolio returns.

### Evidence, frequency, overlap, and abstention

- at least 100 effective same-security episodes in pooled confirmation and 50 in locked test;
- at least 20 distinct securities separately in pooled confirmation and locked test;
- at least 50 confirmation and 30 locked opportunity sessions;
- raw candidate rows divided by effective episodes at most 5;
- candidate rows at most 10% of scored rows;
- opportunity sessions between 10% and 80% of scored sessions;
- idle sessions at least 20%; and
- linear 95th percentile of session candidate counts, including zeros, at most 12.

The four frequency/abstention thresholds pass separately in `DEV_2023`, `DEV_2024`, and the locked test. Fixed episode floors prevent an extremely rare tail from passing; the mandatory block-confidence bounds provide statistical resolution rather than treating those counts as a power claim.

### Concentration and dependence

- largest security episode share at most 10%;
- top-five security share at most 35%;
- security episode HHI at most 0.05;
- largest contiguous chronological-quartile anchor share at most 40%; and
- compute absolute summed anchor excess over the same-session eligible mean, take the fifth-largest value as the top-five boundary, and include every security tied at or above it; after removing each boundary-set security separately, selected-rich-minus-each-C delta IC remains at least `+0.005` and rich-minus-each-C tail separation remains strictly positive. No identity field breaks a boundary tie.

These concentration gates pass separately in pooled confirmation and locked populations. Quartiles use contiguous `array_split` session bins and episodes belong to their anchor bin. Leave-security calculations remove that security from every rank, eligible, episode, and same-session comparator population without refitting or recalibrating.

Positive standalone IC, beating only one conventional cell, an approximate tie, one-fold success, extreme rarity, excessive overlap/concentration, identity-dependent tie resolution, or a post-result threshold change is failure. Secondary diagnostics cannot rescue failure.

## Phase boundary and owner review

Phase D0 ends with this contract, its machine-readable registry/configuration, manifest, audit, and validator. It does not create `ats_ml`, fit a real model, generate a prediction, calculate a real association/IC/tail result, inspect the locked historical-test result, construct trades, or begin D1/D2.

Owner review should decide only whether to authorize D1 to implement and fixture-test this already frozen contract and to compute the registered, label-inaccessible predictor values needed for its bounded P-duplicate resolution. Any requested scientific change creates a versioned D0 amendment before D1. D1 itself must stop before any real model fit, prediction, validation score, or performance calculation and return its owner-reviewed structural-resolution artifact and fixture audit for a separate D2 decision.
