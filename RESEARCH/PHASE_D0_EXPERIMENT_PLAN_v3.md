# Phase D0 v3 — final pre-D2 chronology and calibration amendment

**Status:** frozen design amendment; D1 v3 structural proof is authorized, Phase
D2 and every real predictive operation remain unauthorized

**Contract version:** `phase-d0-20260901-v3`

**Preserved parents:** accepted D0 v2 at
`cbddb4ff13f4452aa37f427f0f3c09a3f3da1ae4` and accepted D1 v2 checkpoint
`724971466dacfba05ff0fa7e92cd68c4628008c7`. Their plans, audits, manifests,
fixture registry, structural resolution and immutable structural run remain
historical evidence and are not overwritten.

This is the final major experimental-design amendment before D2. It replaces
the expanding annual chronology with a deterministic semiannual procedure. No
real GPW label value, fit, prediction, score, rank IC, model comparison, feature
importance, opportunity outcome, tail result, economic result or Phase D verdict
was inspected to choose it.

Machine-readable authority is
`source/python/configs/phase_d0_reference_v3.json`. It is a narrow amendment over
the four immutable D0 v2 anchors. The existing
`phase_d0_feature_registry.json` remains the sole feature authority; no v3
registry is created because all 30 scientific feature definitions are unchanged.

## Bounded decision design

### Exact decision

Can ATS deterministically construct and structurally prove a leakage-safe Phase
D procedure that refits every January and July, uses the trailing 36 calendar
months, admits targets only after exact availability, calibrates a threshold
from three prior out-of-fit score blocks, refits on all mature rows, evaluates
the next six months and repeats without researcher intervention?

### Cheapest credible experiment

Amend only D0 chronology/calibration and the minimum D1 splitter, structural
resolver, synthetic four-cell plumbing and firewall tests. Reuse the pinned
candidate and market-state inputs, accepted feature code, exact label endpoint
metadata, four model cells, matrices/ledgers, model adapters and opportunity
utility. Do not implement D2 evaluation machinery.

### Must-have validity work

- official-calendar January/July boundaries and month-aligned trailing windows;
- exact endpoint-timestamp purging at every inner and outer refit boundary;
- strict separation of three prequential score fits, pooled score threshold and
  final estimator refit;
- label-blind structural eligibility/minimum resolution with denominator 60;
- identical semantic score populations across all four cells;
- sequential locked-generation and outcome-evaluation firewall;
- partial-block/right-censoring and complete-block gate mappings;
- immutable logical, physical, code, environment and input provenance; and
- adversarial fail-closed fixtures before any real predictive access.

### Useful, nongating D1 diagnostic

Synthetic score-distribution differences between the three inner models and the
final refit may be represented only by a provenance hash. They establish no
quality result and cannot trigger score rescaling, threshold relaxation or a
rescue rule.

### Deferred

Real selection, real fitting/scoring, IC and model comparison, bootstrap
inference, tail economics, leave-security-out evaluation, episodes,
concentration verdicts, feature importance, ablations, portfolio translation and
the Phase D STOP/CONTINUE decision remain D2/D3 work. Alternative windows,
cadences, weights, calibration layouts, parameters, features, labels, models,
sector/peer data, total-return work and ML-platform infrastructure are not
authorized.

### Stop/continue rule

D1 v3 passes only if every specified procedure boundary is frozen,
fixture-proven, structurally resolved and reproducible without predictive data.
Any infeasible minimum, missing score block, calendar mismatch, population
misalignment, forbidden read or unapproved choice is `FAIL` and returns to the
owner. A pass authorizes only a new owner decision about D2.

## Unchanged scientific contract

The following remain byte- or semantics-pinned to D0/D1 v2:

- the GPW candidate panel and accepted market-state inputs;
- exact PIT TOP60 membership, official denominator 60 and all missing,
  unresolved, non-trading and feature-specific eligibility states;
- `split_adjusted_price_return`, exclusion of cash distributions, preserved cash
  dividend price gaps and no total-return interpretation;
- all 30 C/P/X/M features and all eight accepted P survivors;
- `label__open_to_open__20`, its exact 20-session open endpoint and 08:45
  Europe/Warsaw decision timestamp;
- identity-blind allowlists and semantic matrix/target/score row ledgers;
- Ridge and LightGBM classes, parameters and the four conventional/rich cells;
- `max(1%, q90)` using the linear empirical quantile, strict `score > threshold`,
  no top-N quota and valid zero-candidate sessions;
- every existing metric and numerical materiality threshold, including separate
  decisive comparison with `C_LINEAR` and `C_LIGHTGBM`;
- tail, severe-outcome, influence and concentration definitions; and
- price-basis/live-availability caveats and all Phase A/B/C evidence.

The scientific changes are chronology, calibration population, evidence-period
mapping and the minimum rules necessarily tied to them. File names, schema
versions, hashes, parent pointers and current-guidance links are metadata-only.

## Outer semiannual walk-forward

For each calendar half-year, refit on its first official WIG decision session.
January refits score January–June; July refits score July–December. The lower
calendar boundary is the first day of the refit month minus 36 months, mapped to
the first official session on or after it. The upper boundary is the last
official session before the refit. Thus a July refit uses the immediately
preceding July–June trailing window.

Only model rows inside that window are eligible. Earlier observations may supply
frozen feature warm-up but can never enter a fit. At every boundary `B`, a row is
fit-eligible only when its exact `label_endpoint_ts < B.decision_ts`. Endpoint
metadata, not a fixed 20-row subtraction, determines the purge.

Every fit recreates preprocessing and estimator state. After calibration, the
final outer estimator fits all outcome-eligible, label-mature rows in the window
and scores only the next six-month block.

## Three-block internal prequential calibration

The first 18 calendar months are initial fitting history. The remaining 18
months are three consecutive six-month score blocks. For each block, recreate
the preprocessing and model, fit only earlier rows in the same 36-month window
after exact endpoint purge, and score the entire common score mask. Score-block
labels are inaccessible to threshold construction.

Pool exactly those three finite out-of-fit score populations separately by
model cell. Freeze:

```text
threshold = max(0.010000, linear empirical q90(pooled inner scores))
```

No failed block may be replaced and fewer than three blocks may not be pooled.
The final refit neither changes nor recalculates the threshold.

## Frozen evidence periods and gate mappings

| Role | Complete outer blocks | Decisive aggregation |
|---|---|---|
| Model-family selection | 2023 H1, 2023 H2 | pool both with equal session weighting; Ridge wins an absolute tie `<= 0.002` |
| Development confirmation | 2024 H1, 2024 H2 | pooled for decisive gates and each half separately for stability |
| Locked historical test | 2025 H1, 2025 H2, 2026 H1 | pooled for decisive gates and each half separately for stability |
| Partial monitoring | 2026 H2 through 2026-08-18 | nongating; preserve right-censored/unavailable states |

The 2023 population supplies no confirmation threshold or confidence interval.
Freeze the conventional reporting reference and rich challenger after 2023 and
before opening 2024 outcomes.

Annual stability uses only complete decisive calendar years 2024 and 2025. The
positive-year fraction therefore has denominator two. Partial 2026 cannot be
classified as a positive or failed year. 2026 H1 remains in pooled locked and
half-year stability. A pooled result cannot hide a required block failure, and a
favorable block cannot rescue a failed pooled gate.

The composed v3 runtime contract must replace, rather than inherit, every v2
evidence-period reference in `comparison`, `evaluation` and `decision_gate`.
Those objects carry explicit machine-readable mappings for selection blocks
`MODEL_SELECTION_2023_H1/H2`, development blocks `DEVELOPMENT_2024_H1/H2` and
locked blocks `LOCKED_2025_H1`, `LOCKED_2025_H2`, `LOCKED_2026_H1`. Composition
fails closed if `MODEL_SELECTION_2022`, `DEV_2023`, `DEV_2024`,
`LOCKED_2025_2026` or the obsolete generic locked-test population survives.

## Minimum evidence

For each complete evaluation block, require at least
`ceil(0.80 × expected official sessions)` qualifying sessions, each with at least
45 eligible securities. The minimum row count is that session minimum times 45.
Never shorten a block or redefine its denominator.

Each final 36-month fit requires at least 230 qualifying sessions, 10,000 model
rows and at least 80% of structurally expected label-mature sessions, with 45
fit-eligible rows required for a qualifying session.

For the 18-, 24- and 30-month inner fit histories, derive the expected sessions
after exact endpoint removal and require:

```text
minimum sessions = max(120, ceil(0.80 × expected sessions))
minimum rows     = max(5,400, 45 × minimum sessions)
```

Every one of the three inner score blocks requires common-score-mask coverage on
at least 80% of expected sessions and a finite cell threshold. D1 resolves
calendar endpoints and label-blind structural eligibility only. D2 must also
enforce actual outcome-eligible populations.

## Locked sequential-generation firewall

D1 fixture-proves this future D2 sequence without real predictions:

1. generate and fingerprint 2025 H1 predictions;
2. at July 2025, admit only earlier locked labels whose exact availability
   precedes the refit, then generate 2025 H2;
3. at January 2026, apply the same rule and generate 2026 H1; and
4. fingerprint the complete ordered sequence before any outcome attachment,
   metric, display, logging or inspection is allowed.

Prediction generation/fingerprinting and outcome attachment/evaluation are
mechanically separate stages. No procedure mutation is permitted between
refits. The firewall binds each block to its expected first official refit
session and to a canonical proof identity covering the exact retained-session
set, endpoint-availability summary and validated structural minima. A syntactic
SHA-256 value alone is insufficient.

## D1 v3 boundary and owner gate

D1 v3 may derive only official calendars, exact endpoint metadata, label-blind
structural eligibility, frozen minima, affected concentration bins, hashes and
the previously accepted P-survivor result. Synthetic fitting/scoring proves
plumbing, not model quality. It may not load a real label value, fit or score a
real row, compute a real metric or model-family result, or start D2.

The next gate after a D1 v3 `PASS` is owner review of
`PHASE_D1_READINESS_v3.md` and its explicit immutable structural run. Only that
review may decide whether to authorize D2.

The later owner instruction is recorded separately in
`PHASE_D2_AUTHORIZATION_OVERLAY.md`. It automatically authorizes a new D2 task
only after this repaired baseline is committed and passes clean post-commit
verification. The D1 structural construction described here did not have that
authorization and inspected no predictive result.

Phase D2 is therefore conditional on the later overlay trigger, not on this
historical construction PASS alone.

**Predictive usefulness remains NOT PROVEN. This repair does not execute D2.**
