# Phase D2 bounded audit repair

Status: **STOP — VERIFIED / EXECUTION INTEGRITY NOT FULLY PROVEN**

Date: 2026-09-02

## Disposition

The accepted prediction and evaluation publications remain unchanged. Audit v2
independently validates their seals and reproduces the negative scientific
anchors sufficient to retain the Phase D verdict. The result is not marginal:

| Population | Rich minus `C_LINEAR` mean IC | Frozen minimum |
|---|---:|---:|
| 2024 development | -0.015205 | +0.010000 |
| 2025–2026H1 locked | -0.025285 | +0.010000 |

Locked frequency-matched rich opportunity returns were 0.651 percentage points
worse than `C_LINEAR` and 1.291 points worse than `C_LIGHTGBM`. Relevant
accepted bootstrap lower bounds remain below zero. These failures are
sufficient for the frozen mechanical `STOP`; no diagnostic can reverse them.

- Phase D research verdict: **STOP — VERIFIED**
- D2 execution integrity: **NOT FULLY PROVEN**
- Phase D3 authorized: **NO**
- Portfolio/backtest work authorized: **NO**

## Preserved evidence and versioned audit

No prediction, outcome, metric, gate, threshold, or accepted stage artifact was
regenerated or edited. The new audit publications are:

- primary:
  `D:\Stock\data\ATS\phase_d_ml\evaluation_runs\phase-d2-evaluation-20260902-v6\audit-v2`;
- reproduction:
  `D:\Stock\data\ATS\phase_d_ml\reproductions\evaluation_runs\phase-d2-evaluation-20260902-v6-reproduction\audit-v2`.

Both publications contain exactly `audit.json` and `manifest.json`. Inventory,
byte size, SHA-256, package-logical-hash, and scientific-payload-hash checks
pass. Their scientific logical hash matches exactly:

`397d66ed3c88c8e914c1a6bbdc9af7875f0d553acbd86c48dcb8d3f64eab944c`

The accepted prediction-table logical hash remains:

`ad9ea68d66fde122e127d502706f8eeaea162749b6f67a38b1a68ac0c06e8466`

## Finding 1: sequential locked-label admission

The accepted v4 implementation loaded the union of training-label sessions
needed by all outer blocks before generating its first block. Every individual
fit retained only rows whose exact label endpoint preceded that fit boundary,
so no statistical leakage into a model was found. However, the accepted trace
does not prove literal block-by-block label admission. Audit v2 therefore records
`sequential_locked_label_admission = NOT PROVEN` and refuses to upgrade overall
execution integrity.

The forward runtime now uses `SequentialLabelAdmissionFirewall`. It admits only
the label sessions required by the next declared outer block, requires exact
block order, rejects a session reaching the refit boundary, records admitted
session and endpoint evidence, and fails if the sequence is incomplete. The
accepted Stage 1 run was deliberately not rerun; a future safeguard cannot be
used as retroactive evidence.

## Finding 2: execution-integrity gates

The original final matrix remains a preserved historical artifact. Its 26
execution-integrity rows—13 each for development and locked evaluation—were
emitted as unconditional `PASS` values. They are no longer cited as independent
proof of their own claims.

Future evaluation stages derive all 13 rows from retained masks, outcomes, fit
audits, feature allowlists, frozen minima, lineage, inventories, byte hashes,
and logical payloads. Audit v2 separately derives those same 13 dimensions from
the accepted artifacts; all 13 pass. The separate historical sequential-access
check remains `NOT PROVEN`, so the combined classification is **NOT FULLY
PROVEN**, not `PASS`.

## Finding 3: independent evaluator coverage

The independent evaluator imports no primary D2 metric functions. It
independently recomputes 2023 model-family selection, denominators, session IC
and paired mean deltas, candidate and idle frequencies, episode anchors, mean
tail separation, severe-outcome differences, security concentration, and
chronological-quartile concentration. Audit v2 additionally recomputes session
and half-year concentration and the decisive negative mean-IC anchors.

The evaluator reclassifies the remaining stored gate values. It does **not**
independently recompute every bootstrap interval and defined fraction,
leave-top-contributor calculation, complete-year gate input, or every other
gate input. The controlling claim is therefore a **bounded independent core
audit**, not a complete second implementation of all 177 gate inputs.

## Finding 4: session and period concentration

The missing D0 reporting dimension is now present, computed from already sealed
outcome-evaluable rich episode anchors:

| Population | Episodes | Nonzero sessions | Largest session | Top five sessions | Session HHI | Largest half-year | Half-year HHI |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2024 development | 198 | 43 | 21.21% | 56.57% | 0.09285 | 74.24% | 0.61754 |
| 2025–2026H1 locked | 133 | 28 | 27.07% | 54.14% | 0.10815 | 55.64% | 0.40935 |

The largest-session boundaries were 2024-06-25 (42 episodes) and 2025-02-25
(36 episodes). D0 froze no threshold for these values, so they are reporting
diagnostics and cannot add, remove, or reinterpret a gate. They make the
episodic evidence concentration visible without changing the negative result.

## Notebook and figure verification

The owner-review notebook is
[`04_phase_d_pooled_ml_review.ipynb`](../source/python/notebooks/04_phase_d_pooled_ml_review.ipynb).
It explains the information sequence, pooled walk-forward fitting, within-
representation selection, decisive IC and opportunity-tail failures,
frequency/abstention, the historical scientific gate matrix, concentration,
diagnostics, independent-audit coverage, and the final owner decision.

It executed from a fresh repaired kernel with 13 code cells, 23 retained
outputs, zero cell errors, and eight nonempty inline PNG figures. The rendered
machinery, chronology, selection, incremental-IC, locked-tail, frequency,
gate-category, and concentration figures were visually inspected. NumPy,
SciPy, Matplotlib, nbformat, nbclient, and image generation worked in the
existing repaired environment; no environment change or package installation
was required.

## Fail-closed classifier hardening

The audit's overall status is now assigned by one pure classifier. A successful
qualified audit requires the independent core evaluator to pass, independent
reproduction of the scientific `STOP`, an accepted frozen verdict of `STOP`, no
failed integrity check, and exactly one `NOT PROVEN` item:
`sequential_locked_label_admission`. Any integrity `FAIL` or independent-core
`FAIL` produces overall `FAIL`; any other missing, inconsistent, unexpected, or
`NOT PROVEN` requirement produces overall `NOT PROVEN`. The command returns
success only for full `PASS` or this exact qualified pass.

Adversarial tests cover all-pass evidence, the sole permitted historical gap,
unrelated and unexpected `NOT PROVEN` items, both recognized and unrelated
integrity failures, independent-core failure, missing scientific or accepted
`STOP`, combined failures, and process exit status. In-memory primary and
reproduction reconstruction still returns the existing qualified pass and the
unchanged scientific logical hash; no sealed publication was overwritten.

## Verification

- focused audit-hardening suite: **19 passed**;
- complete focused Phase D2 suite: **46 passed**;
- complete supported Python suite: **233 passed**;
- pre-Phase-D market-state regressions: **10 passed**;
- primary and reproduction audit-v2 seals: **PASS**;
- primary/reproduction audit scientific payload: **exact match**;
- fresh-kernel Phase D notebook: **PASS, zero cell errors, eight PNG figures**.

The full-suite run also exposed a nondeterministic D1 synthetic-proof check:
the proof retained only fitted estimator object IDs, allowing Python to reuse an
address after garbage collection. The bounded correction retains the four
estimator objects through the proof and then verifies four distinct identities.
It changes neither fitting semantics nor any Phase D2 model, parameter,
prediction, metric, or verdict. The formerly flaky proof passed three
consecutive focused runs before the complete suite was repeated.

The pre-calculation repair formulas and scope were frozen in commit `872dbd0`
before either audit-v2 publication was calculated.

## Boundary

This repair closes the reporting and forward-audit defects without reopening
Phase D research. It does not authorize prediction regeneration, model
selection, threshold changes, a new statistical platform, feature/model/data
search, Phase D3, portfolio translation, optimization, or deployment.
