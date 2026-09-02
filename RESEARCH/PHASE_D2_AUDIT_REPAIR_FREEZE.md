# Phase D2 bounded audit repair freeze

Status: **FROZEN BEFORE AUDIT-V2 CALCULATION**

Date: 2026-09-02

## Exact decision

Determine whether the four identified audit gaps invalidate the already sealed
Phase D2 scientific `STOP`, and correct the evidence claim without regenerating
predictions, changing any scientific choice, or executing Phase D3.

## Cheapest credible repair

1. Preserve the accepted prediction and evaluation publications unchanged.
2. Make future Stage 1 execution admit training labels one outer block at a time
   in chronological order; do not rerun Stage 1 for this repair.
3. Replace future unconditional execution-integrity rows with checks derived
   from the prediction, mask, outcome, fit-audit, lineage, and manifest evidence.
4. Publish one versioned `audit-v2` beside each accepted primary/reproduction
   evaluation root. It independently validates seals, derives the available
   integrity checks, adds the missing session/period concentration report, and
   states exactly which statistics the independent evaluator did and did not
   recompute.
5. Narrow human claims instead of implementing a second full statistical engine.
6. Add one executable Phase D owner-review notebook that reads sealed evidence
   only and renders its figures in a fresh repaired Jupyter kernel.

## Frozen audit classifications

- The accepted v4 fit populations remain endpoint-mature; this is checked from
  the retained fit and chronology evidence.
- Literal sequential label admission is `NOT PROVEN` for the accepted v4 run
  because its implementation loaded the union of training labels before the
  first outer block. No model was shown to consume an unavailable label.
- The scientific `STOP` is verified independently when the sealed inputs match
  and the independently recomputed development and locked rich-minus-`C_LINEAR`
  mean IC deltas remain below the frozen `+0.010` requirement. This is sufficient
  to reject `CONTINUE`; it does not upgrade execution integrity.
- Execution integrity is `NOT FULLY PROVEN` while sequential admission is not
  provable, even if every other derived integrity check passes.
- The accepted mechanical verdict artifact remains `STOP`; audit v2 qualifies
  its evidence coverage and does not replace or edit it.

## Session and period concentration formulas

For each decisive population, use the persisted outcome-evaluable rich episode
anchors already sealed by Stage 2B/2C:

- count anchors by `decision_session`;
- divide by total anchors for session shares;
- report largest-session share, top-five-session share, and session HHI as the
  sum of squared session shares;
- count anchors by frozen half-year `block_id` and report block shares, largest
  block share, and block HHI; and
- retain the already published chronological-quartile counts and share.

These are reporting diagnostics. No threshold was frozen for them, so they do
not add, remove, or reinterpret a decision gate.

## Must-have validity work

- validate every sealed input inventory, byte hash, and logical payload;
- bind audit v2 to the accepted prediction-table and stage logical identities;
- prove primary/reproduction audit scientific payload equality;
- derive integrity values from retained artifacts rather than copy the original
  unconditional rows;
- test sequential label admission order and fail closed on a wrong block;
- test session/period concentration formulas, including zero-anchor behavior;
- execute the notebook from a fresh repaired kernel with no cell errors;
- verify that figures contain nonempty PNG output and inspect rendered images;
  and
- rerun focused D2 and complete supported regression suites.

## Useful but nongating diagnostics

Notebook tables and figures for chronology, rank IC, opportunity tails,
frequency/abstention, gate failures, concentration, and the market-state
ablation. They explain the retained decision and cannot rescue it.

## Deferred

No prediction regeneration, model refit, model selection, threshold change,
bootstrap redesign, new independent statistical platform, new data, feature,
label, model, subgroup, portfolio, optimization, Phase D3, or deployment work.

## Stop rule

- If a sealed input or independently recomputed negative-result anchor differs,
  classify the repair `NOT PROVEN` and stop.
- Otherwise retain **Phase D research verdict: STOP — VERIFIED**, publish the
  bounded audit qualification, keep **D2 execution integrity: NOT FULLY
  PROVEN**, and stop for owner review.
- D3 and portfolio/backtest work remain unauthorized in every outcome.

Frozen audit output directories:

- `D:\Stock\data\ATS\phase_d_ml\evaluation_runs\phase-d2-evaluation-20260902-v6\audit-v2`
- `D:\Stock\data\ATS\phase_d_ml\reproductions\evaluation_runs\phase-d2-evaluation-20260902-v6-reproduction\audit-v2`
