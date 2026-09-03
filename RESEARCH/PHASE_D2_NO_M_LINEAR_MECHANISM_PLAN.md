# Phase D2 C+P+X model-mechanism test

**Status:** FROZEN BEFORE REAL MODEL FIT

**Contract ID:** `phase-d2-no-m-linear-mechanism-20260903-v1`

**Evidence level:** `RETROSPECTIVE_HYPOTHESIS_DEVELOPMENT_AND_ROBUSTNESS`

This test was selected after inspection of the accepted Phase D2 and D2-NM
results. It cannot provide prospective confirmation, overturn the original D2
`STOP`, establish alpha, authorize portfolio work, change the registered D2-NM
prospective stream, or authorize deployment.

## Bounded decision

Determine whether the exact accepted 18-feature C+P+X representation contains
stable incremental rank information under the frozen Ridge estimator and whether
the accepted LightGBM procedure materially improves on Ridge with the feature
representation held fixed.

The cheapest credible experiment is one newly fitted cell,
`RICH_NO_M_LINEAR`, plus exact reproduction of three accepted control cells on
the same rows. Evaluation is rank-only over the seven complete half-years from
2023 H1 through 2026 H1. Thresholds, candidate flags, episodes, tail returns,
other models, other windows, and other feature sets are unnecessary and are not
calculated.

## Frozen inputs and scientific object

- Feature registry SHA-256:
  `733bacb9c1132d98eacb4a190cfb3cd96b0163207af46f3745002206b3705ef6`.
- Accepted prediction run: `phase-d2-predictions-20260902-v4`.
- Accepted prediction-table logical hash:
  `ad9ea68d66fde122e127d502706f8eeaea162749b6f67a38b1a68ac0c06e8466`.
- Accepted D2-NM follow-up: `phase-d2-nm-followup-20260903-v1`.
- Feature allowlist: the exact accepted derived-contract
  `RICH_NO_M_LIGHTGBM.feature_names` list, reused without reordering.
- Target: `label__open_to_open__20`, defined as the exact t+20 official-session
  open divided by the decision-session open minus one.
- Price basis: `split_adjusted_price_return`; cash distributions are excluded
  and known dividend price gaps remain.
- Population: official point-in-time TOP60 membership, denominator 60, with
  missing, unresolved, non-trading, and unavailable states retained visibly.
- Timing: preceding-session information only, 08:45 Europe/Warsaw decision
  timestamp, January/July refits, trailing 36 calendar months, and label endpoint
  strictly earlier than the refit decision timestamp.
- Existing prospective stream: immutable and outside this task.

The four frozen cells are:

| Cell | Features | Estimator | Role |
|---|---|---|---|
| `RICH_NO_M_LINEAR` | C+P+X | Ridge | scientifically new mechanism cell |
| `C_LINEAR` | C | Ridge | same-estimator feature baseline control |
| `C_LIGHTGBM` | C | LightGBM | fixed conventional control |
| `RICH_NO_M_LIGHTGBM` | C+P+X | LightGBM | accepted nonlinear procedure control |

Ridge is exactly median imputation without indicators, standardization, and
`sklearn.linear_model.Ridge(alpha=1.0, fit_intercept=true, solver="lsqr",
tol=1e-6, max_iter=10000)`, with preprocessing fitted independently inside
every fit. Every fit fails if a registered feature has no finite training value.
The accepted deterministic LightGBM definition is reproduced without change.
No tuning or alternative preprocessing is permitted.

## Stage 1: prediction-only publication

Create immutable primary and clean-reproduction packages under
`D:/Stock/data/ATS/phase_d_ml/mechanism_runs/`. Each package contains no outcome,
IC, return, classification, candidate, threshold, or episode field. It binds the
contract, accepted manifests, exact Git blobs, environment, code fingerprints,
walk-forward plan, block-scoped label admission, fit audits, score-row ledgers,
and score hashes. No mutable `latest` or `current` pointer is permitted.

For each refit block, admit only that block's permitted training labels; recreate
preprocessing and estimator state for each inner fit and final fit; and score the
four cells on identical semantic rows. Predictor nulls remain null until the
model's frozen missing-value policy. The three controls must match score hashes
derived from the accepted prediction table separately for every block before any
new-cell outcome is loaded or evaluated. Any mismatch makes the result `NOT
PROVEN`.

The clean reproduction must independently regenerate the complete four-cell
prediction table and match its logical identity byte-for-byte at the persisted
Parquet level.

## Stage 2: rank-only evaluation

Evaluate only the ordered union of these complete populations:

| ID | First session | Last session |
|---|---|---|
| `RETRO_2023_H1` | 2023-01-02 | 2023-06-30 |
| `RETRO_2023_H2` | 2023-07-03 | 2023-12-29 |
| `RETRO_2024_H1` | 2024-01-02 | 2024-06-28 |
| `RETRO_2024_H2` | 2024-07-01 | 2024-12-30 |
| `RETRO_2025_H1` | 2025-01-02 | 2025-06-30 |
| `RETRO_2025_H2` | 2025-07-01 | 2025-12-30 |
| `RETRO_2026_H1` | 2026-01-02 | 2026-06-30 |

All cells use identical security-session rows on the common outcome-evaluable
population. A session IC is defined only with at least 45 paired observations
and nonconstant predictions and outcomes. Spearman uses average ranks; identity
and row order never resolve ties. Pooled statistics weight each defined session
equally.

Primary contrasts are:

1. `RICH_NO_M_LINEAR - C_LINEAR`, the incremental P+X value under Ridge.
2. `RICH_NO_M_LIGHTGBM - RICH_NO_M_LINEAR`, the incremental nonlinear value
   with features fixed.
3. Each C+P+X cell separately against `C_LINEAR` and `C_LIGHTGBM`.

For every contrast report pooled mean and median paired session-IC delta; the
mean delta in every half-year; median of the seven half-year means; positive
half-year count; positive-session count and fraction; a deterministic circular
20-session moving-block 95% interval with 5,000 PCG64 samples, seed `20260831`,
linear 2.5%/97.5% quantiles, identical paired indices, and at least 99% defined
replicates; all seven leave-one-half-year-out pooled deltas; the pooled result
after removing every identity-neutral exact tie for the largest contributing
security; and the largest positive-contribution share by security and half-year.
Bootstrap intervals are uncertainty diagnostics, not classification gates.

Contribution for a dimension member is the sum of positive defined session-IC
deltas attributable to that member divided by the sum of all positive defined
session-IC deltas. Security attribution is recomputed from common rows by
removing each security without refitting; the largest contributor is the
security whose removal causes the largest decrease in pooled mean delta, with
every exact tie retained. Half-year contribution uses the sum of positive
session deltas in that half-year. A zero positive-total yields a null share and
fails any gate requiring concentration to be below 50%.

Useful nongating diagnostics are per-half-year Spearman correlations between the
two C+P+X score vectors, final-fit Ridge coefficient signs and standardized
magnitudes by refit, prediction dispersion and rank turnover by refit,
feature/half-year missing-value rates, and decomposition of the 2023 H1 contrast
into Ridge and C+P+X levels. They cannot change the cells, features, model,
thresholds, classification, or next action.

## Broad-increment gate and verdict

`BROAD_INCREMENT(candidate, comparator)` passes only if all of the following
are true:

- pooled mean paired session-IC delta is strictly greater than `+0.005`;
- at least five of seven half-year mean deltas are strictly positive;
- the median of the seven half-year mean deltas is strictly positive;
- every leave-one-half-year-out pooled delta is strictly positive;
- removing each tied largest-contributing security leaves the pooled delta
  strictly positive;
- no security and no half-year supplies 50% or more of total positive excess;
- every validity, control-reproduction, seal, and independent-evaluation check
  passes.

Every practical continuation claim must pass separately against both
`C_LINEAR` and `C_LIGHTGBM`. Apply the mechanical verdict in this order:

1. `NOT PROVEN`: any timing, population, control-hash, prediction-seal,
   model-definition, or independent-reproduction requirement fails.
2. `REPRESENTATION ROBUST — RIDGE SUFFICIENT`: Ridge C+P+X passes broad increment
   against both conventional comparators and LightGBM does not pass against
   Ridge C+P+X.
3. `REPRESENTATION ROBUST — NONLINEARITY ADDS`: Ridge C+P+X passes against both
   conventional comparators and LightGBM also passes against Ridge C+P+X.
4. `NONLINEARITY-DEPENDENT — WEAK`: Ridge fails against at least one conventional
   comparator, but LightGBM passes against Ridge and retains a positive pooled
   delta plus at least four of seven positive half-years against each conventional
   comparator.
5. `NOT ROBUST`: every other scientifically valid result.

The result-dependent discussion boundary is fixed: Ridge sufficient permits
discussion of a separately frozen prospective Ridge stream and forbids the
48-month experiment; nonlinearity adds retains the current prospective LightGBM
stream and makes further historical work owner-gated; nonlinearity-dependent
weak permits discussion of the bounded 36m-versus-48m rank-only diagnostic; not
robust stops new model/window/feature research while the existing prospective
stream may accumulate; not proven permits only the smallest integrity repair.
No verdict automatically authorizes the follow-on action.

## Explicitly deferred and required evidence

Deferred: 48/60-month windows; T, Bollinger, or other TA features; feature
deletion or coefficient-driven selection; Ridge-alpha or LightGBM tuning;
alternative estimators/objectives; thresholds, episodes, opportunity tails;
other horizons, labels, universes, vendors, total-return construction; portfolio
simulation, execution, and deployment.

Required retained evidence is the frozen prose and JSON contract, sealed
prediction-only primary package, byte-identical clean reproduction, primary
rank evaluation, an evaluator that imports no primary metric functions, machine
verdict, results Markdown/JSON, and a fresh-kernel executed
`source/python/notebooks/06_phase_d_no_m_linear_mechanism_review.ipynb` that reads
sealed artifacts only and performs no fitting or network access.

