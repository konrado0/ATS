# Phase D2-NM — prospective C+P+X LightGBM falsification plan

**Status:** draft for owner review; design only; no new fit, prediction,
outcome access, evaluation, or Phase D3 work is authorized by this document

**Research-philosophy amendment (2026-09-03):** the prospective-only structure
below is not the controlling execution design. Before execution, revise this
draft into an explicitly labeled retrospective robustness study with prospective
monitoring conditional on that result. Reused D2 history may guide the research
direction but is not independent confirmation. This note changes no accepted D2
artifact or verdict.

**Proposed contract ID:** `phase-d2-nm-prospective-v1`

**Relationship to accepted evidence:** this is a second, related Phase D query.
It does not amend, reinterpret, or overturn the accepted Phase D2 `STOP`. The
accepted D2 predictions, evaluations, audit qualification, and scientific hash
remain immutable.

## Recommendation

One more experiment is defensible, but only in this narrow form. Promote the
already-defined `RICH_NO_M_LIGHTGBM` diagnostic cell to one prospective
challenger, compare it with the unchanged `C_LINEAR` and `C_LIGHTGBM` cells,
retain the original materiality and opportunity-tail hurdles, and use only
outcomes that were not available when this follow-up was frozen.

This is a low-probability falsification, not a likely rescue. The diagnostic
arithmetic implies the following equal-session-weighted mean rank ICs:

| Evidence already inspected | C+P+X LightGBM | C linear | Delta vs C linear | C LightGBM | Delta vs C LightGBM |
|---|---:|---:|---:|---:|---:|
| 2024 development | 0.028235 | 0.021092 | +0.007143 | -0.004789 | +0.033024 |
| 2025 H1–2026 H1 locked | 0.068374 | 0.064749 | +0.003626 | 0.018319 | +0.050055 |

The no-M diagnostic beat both conventional cells in both pooled periods, but
its margin over `C_LINEAR` was below the frozen `+0.010` materiality hurdle in
both. These retrospective values motivate the hypothesis and set expectations;
they are not confirmation evidence and cannot enter the new gate.

No new no-M tail, per-block, subgroup, feature-importance, or alternative-model
result may be opened to refine this plan.

## 1. Exact decision

Does the exact frozen 18-feature C+P+X LightGBM cell provide **material,
stable, and economically relevant incremental information** over each of the
two frozen conventional comparators on two consecutive outcome-unopened
half-years?

A pass supports only an owner decision about one bounded portfolio translation.
It does not establish deployable alpha. A failure closes this C+P+X LightGBM
follow-up and supplies no authority to search more models, features, horizons,
thresholds, subgroups, or data sources.

## 2. Cheapest credible experiment

Reuse the accepted Phase D machinery and make only three bounded changes:

1. evaluate exactly three cells: `RICH_NO_M_LIGHTGBM`, `C_LINEAR`, and
   `C_LIGHTGBM`;
2. remove model-family selection, the M ablation, secondary labels, proximity-Q5
   work, feature importance, and every other nongating branch; and
3. make label admission literally block-scoped and artifact-proven before any
   new prediction publication.

The model, feature definitions, target, panel, timing, refit cadence,
calibration rule, comparators, economic hurdles, and missing-state semantics do
not change. No new D0-scale registry or general ML infrastructure is justified.

## 3. Frozen scientific object

### Challenger

- cell: `RICH_NO_M_LIGHTGBM`;
- representation: the exact 18 C+P+X columns already present in the accepted
  D2 derived contract;
- feature authority: the existing 30-feature registry with SHA-256
  `733bacb9c1132d98eacb4a190cfb3cd96b0163207af46f3745002206b3705ef6`,
  filtered to the existing C, P, and X allowlist;
- estimator: the existing deterministic `lightgbm.LGBMRegressor` configuration
  (`gbdt`, squared error, 300 trees, learning rate 0.03, 15 leaves, depth 4,
  minimum child 100, full row/column sampling, L1 0.1, L2 1.0, seed
  `20260831`, one job, forced column-wise execution);
- missing values: unchanged native IEEE NaN routing; and
- model or hyperparameter selection: none.

### Comparators

`C_LINEAR` and `C_LIGHTGBM` remain exactly as frozen in Phase D2. Every decisive
incremental rank and tail comparison must pass against both separately. The
fact that the diagnostic no-M cell clearly beat `C_LIGHTGBM` does not reduce the
burden against `C_LINEAR`.

### Target and opportunity definition

- target: unchanged `label__open_to_open__20` split-adjusted price return;
- decision timestamp: unchanged 08:45 Europe/Warsaw with one-session-lagged
  information;
- refits: unchanged January/July cadence and trailing 36 calendar months;
- calibration: exactly three preceding six-month out-of-fit score blocks;
- threshold: unchanged `max(0.010000, linear empirical q90)` separately by cell
  and refit;
- qualification: strict `score > threshold`, no quota and valid zero-candidate
  sessions;
- episodes: unchanged first-anchor and 20-official-session de-overlap rule; and
- price basis: split-adjusted price only, excluding cash distributions and
  preserving known dividend price gaps.

## 4. Prospective evidence boundary

The owner confirms that no newer labels currently exist. That delays the
verdict but does not prevent freezing the experiment or starting an
outcome-inaccessible prediction stream.

The accepted D2 prediction table
`phase-d2-predictions-20260902-v4` already contains all three proposed cells for
35 monitoring sessions from 2026-07-01 through 2026-08-18. It contains 2,100
`RICH_NO_M_LIGHTGBM` rows with finite scores and thresholds and no attached
outcomes. The whole prediction table is bound by scientific logical hash
`ad9ea68d66fde122e127d502706f8eeaea162749b6f67a38b1a68ac0c06e8466`.

Those rows are a useful outcome-unopened canary, but the new primary publication
must be generated under the repaired literal label-admission process. It must
reproduce the overlapping three-cell score rows exactly before extending the
stream. The accepted D2 run is read-only and is never replaced.

### Prespecified gating blocks

The preferred gating pair is:

- `PROSPECTIVE_2026_H2`; and
- `PROSPECTIVE_2027_H1`.

`PROSPECTIVE_2026_H2` is eligible only if every included official decision
session has all three cell scores sealed before its primary label is admitted to
evaluation, the full half-year meets the unchanged structural coverage minimum,
and every access-integrity check passes. Whether this block qualifies is decided
from timestamps, manifests, and access traces alone, before any of its outcomes
are opened.

If 2026 H2 fails that outcome-blind operational test, it becomes monitoring only
and the **single prespecified fallback pair** is 2027 H1 plus 2027 H2. There is
no third rollover, no best-period choice, and no shortened denominator. Failure
to obtain two valid blocks by the maturity of 2027 H2 is `NOT PROVEN` and ends
this proposal unless the owner explicitly commissions a new phase.

No interim outcome evaluation is permitted. Outcomes are attached once, only
after both selected blocks are complete, label-mature, prediction-fingerprinted,
and independently validated as inaccessible during scoring.

## 5. Must-have validity work

1. Preserve exact PIT identity, official TOP60 membership, denominator 60,
   decision timestamps, feature lags, exact label endpoints, and all missing,
   unresolved, non-trading, and outcome-unavailable states.
2. Replace eager whole-training-period label loading with block-scoped admission.
   Each refit may read only labels whose exact availability precedes that refit;
   the retained access trace must prove the files, rows, maximum endpoint, and
   admission time rather than asserting a Boolean gate.
3. Build one common semantic score mask for all three cells. No cell may gain an
   easier population through missingness, row dropping, or denominator changes.
4. Recreate preprocessing and estimators at every inner and outer fit, preserve
   endpoint purging, and keep calibration scores and final-refit predictions
   separate.
5. Seal and hash predictions before outcome attachment. Any session scored after
   its label was accessible is ineligible for the prospective block; it is not
   silently discarded from the official denominator.
6. Require at least `ceil(0.80 × expected official sessions)` qualifying
   sessions per complete half-year, at least 45 eligible securities per
   qualifying session, and the inherited fit/calibration minima.
7. Preserve at least 90% scored-row and episode-anchor outcome evaluability, at
   least 90% defined paired-IC session coverage, and at most a five-point gap
   between scored-row and episode evaluability.
8. Reproduce the complete three-cell prediction and evaluation identities in a
   second run. A narrow independent evaluator must recompute every input to the
   final D2-NM verdict, including bootstrap, block, frequency, concentration,
   and leave-contributor gates; it may not merely reclassify stored gate rows.

Any failure above is fail-closed before scientific metrics are interpreted.

## 6. Frozen scientific gate

The historical D2 periods never enter the prospective estimates. Because the
hypothesis is fixed from old data and tested once on new outcomes, the original
materiality and uncertainty thresholds remain unchanged; no retrospective and
prospective estimate is pooled to increase apparent precision.

All conditions below must pass.

### Incremental rank information

Against `C_LINEAR` and `C_LIGHTGBM` separately:

- pooled two-block mean paired session-IC delta at least `+0.010`;
- the frozen 5,000-sample, 20-session circular moving-block bootstrap 95%
  lower bound strictly above zero;
- relative mean improvement at least 15% when the comparator mean IC is
  positive; and
- each of the two half-years has mean paired delta at least `+0.005`.

### Selective opportunity tail

- no-M episode mean minus same-session eligible-universe mean at least `+1.00`
  percentage point;
- no-M episode mean minus each same-session frequency-matched conventional mean
  at least `+0.50` percentage point;
- no-M episode median strictly positive;
- severe-outcome-rate difference versus each comparator no greater than two
  points; and
- the inherited bootstrap lower/upper bounds pass for eligible separation, both
  comparator separations, median, and severe-outcome differences.

These are research diagnostics, not fills, trades, costs, or portfolio returns.

### Evidence amount, abstention, and concentration

- at least 100 effective same-security episodes, 20 distinct securities, and 50
  opportunity sessions across the pooled two-block population;
- raw candidate rows per effective episode at most 5;
- in each half-year: candidate-row fraction at most 10%, opportunity-session
  fraction from 10% through 80%, idle-session fraction at least 20%, and linear
  p95 session candidate count at most 12;
- largest-security episode share at most 10%, top-five share at most 35%,
  security HHI at most 0.05, and largest chronological-quartile share at most
  40%; and
- after leaving out each identity-neutral top-contributor boundary security,
  delta IC remains at least `+0.005` and tail separation remains positive
  against both comparators.

Approximately tying, beating only `C_LIGHTGBM`, positive standalone IC, one good
half-year, a rare or concentrated tail, or an unresolved confidence bound is not
a pass.

## 7. Useful nongating diagnostics

Keep these descriptive and unable to alter the gate:

- the pre-existing outcome-unopened 2026 H2 overlap reproduction;
- per-session IC distributions and plotted cumulative paired deltas;
- candidate and episode counts by session and half-year;
- largest-session share and session HHI; and
- the historical diagnostic values in the rationale table, displayed separately
  and never pooled with prospective evidence.

Do not calculate alternate labels, alternate horizons, new thresholds, feature
importance, SHAP, subgroups, market regimes, portfolio returns, or additional
ablations.

## 8. Explicitly deferred

- Ridge or another model on C+P+X;
- full-rich C+P+X+M as a new challenger;
- XGBoost, CatBoost, ranking objectives, neural/sequence models, ensembles, or
  hyperparameter search;
- reopening P/X definitions, adding technical indicators, changing the label or
  using a new universe/vendor;
- total-return reconstruction, sector/event data, all-GPW expansion, a feature
  store, MLflow, GPU work, or a general prediction service; and
- portfolio construction, costs, sizing, turnover, fillability, optimization,
  deployment, or live trading.

## 9. Prespecified verdict

- **CONTINUE CANDIDATE:** every validity, incremental-rank, tail, evidence,
  abstention, stability, concentration, reproduction, and independent-audit
  requirement passes. This returns to the owner for a decision on exactly one
  bounded Phase D3 portfolio test; it does not authorize that test
  automatically.
- **STOP:** any scientifically evaluable gate fails. The tested OHLCV-only
  C+P+X LightGBM extension is closed. No diagnostic may rescue it and no further
  ML/model search is authorized.
- **NOT PROVEN:** two valid prospective blocks cannot be obtained or a validity,
  access, reproduction, or audit requirement remains unresolved. This does not
  become `CONTINUE` by relaxing thresholds or extending the window after the
  fact.

The result must always be reported narrowly. Even a `STOP` would reject this
fixed C+P+X LightGBM continuation, not every conceivable ML approach. Conversely,
a `CONTINUE CANDIDATE` would support only a bounded portfolio falsification, not
deployment.

## 10. Minimal execution sequence after separate authorization

1. Freeze this plan and a small machine-readable amendment before opening any
   new outcome.
2. Implement and fixture-test literal block-scoped label admission and the
   three-cell allowlist; perform no scientific evaluation.
3. Reproduce the overlapping sealed 2026 H2 scores and publish the prospective
   prediction stream under a new immutable run ID.
4. Select the preferred or fallback block pair using access/coverage evidence
   only, then seal both complete prediction blocks.
5. Attach outcomes once, compute the reduced frozen gate, reproduce it, and run
   the independent full-gate evaluator.
6. Publish `CONTINUE CANDIDATE`, `STOP`, or `NOT PROVEN`, preserve all artifacts,
   and stop for owner review.

Until steps 1–2 receive separate owner authorization, the current Phase D2
`STOP — VERIFIED` controls and Phase D3 remains unauthorized.
