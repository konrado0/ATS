# Phase D2 pooled-ML results

Status: **STOP — VERIFIED / EXECUTION INTEGRITY NOT FULLY PROVEN**

Date: 2026-09-02

Phase D2 executed the single study frozen in
[`PHASE_D2_EXECUTION_FREEZE.md`](PHASE_D2_EXECUTION_FREEZE.md). The exact
decision was whether the compact rich-state representation provided material,
stable, and economically relevant incremental information beyond **both** fixed
conventional comparators, especially in the selective long-only opportunity
tail. It did not. The mechanical Phase D verdict is `STOP`; Phase D3 execution
and portfolio/backtest work are not authorized.

## 1. Execution and validity

The run used the committed automatic-authorization baseline
`1dc9bbd93aa73da72aceda538f84cba233f79f78`, the immutable D1 v3 structural
run `phase-d1-v3-structural-ed315ee058c7e0e7ce51`, and the operational
configuration in `source/python/configs/phase_d2_execution.json`. No mutable
`latest` pointer was used.

The accepted prediction package is:

- run ID: `phase-d2-predictions-20260902-v4`;
- package logical hash:
  `2d00f4780309457e5a3b28aa164a5c72a561b2d4188008ce8735f4ea247c18d0`;
- prediction-table logical hash:
  `ad9ea68d66fde122e127d502706f8eeaea162749b6f67a38b1a68ac0c06e8466`;
- locked-sequence fingerprint:
  `4af56252a7aae9054baf117a9cb386cf026ad8f35e438a1e3f753b0a1e2999b6`;
- physical manifest SHA-256:
  `ab0fd8f4c38653470d5ec33ede6758f93ab356e98c5fadaf381161e793c48fc8`.

Prediction validation is `PASS`: every frozen block and cell is present, all
five cells (four primary plus the frozen ablation) use their shared semantic
population, scores and thresholds are
finite, the strict threshold rule is preserved, the locked sequence is
complete, and the sealed prediction artifact contains no outcomes or evaluation
metrics. This proves that the sealed prediction table is label-free; it does
not retroactively prove literal block-by-block admission of training labels.

The accepted evaluation run is `phase-d2-evaluation-20260902-v6`. Its sealed
logical hashes are:

| Artifact | Logical hash | Physical manifest SHA-256 |
|---|---|---|
| Stage 2A | `4206fe7d6669b27e43203a7f57bf0c0c368de8bc29d98f4e56d63ee6ba100b05` | `82b7e400...` |
| Stage 2B | `e1675d0e98f67a5596cc0e3c28e75393aa18c11e534d211d0e5774ff663f4d3d` | `f112a14d...` |
| Stage 2C | `0cf187d0fff6330bcb3cd797aeff5f0dd32e526892893166016c620e73361819` | `76051f2d...` |
| Final | `b3a16bad8f0d76e34885639f7758afd11a64aef2a9b075b7ea6f7c201ac55acc` | `11b06103...` |

The abbreviated physical hashes above are display aids; the complete values are
bound in [`PHASE_D2_MANIFEST.json`](PHASE_D2_MANIFEST.json) and in the immutable
external manifests.

Audit v2 derives PIT timing, official-denominator, exact-label-anchor,
endpoint-purge, fold-local preprocessing, identity-exclusion, tie, population,
minimum-sample, coverage, missing-state, lineage, and seal-order checks from
retained artifacts; all thirteen derived dimensions pass. Literal sequential
locked-label admission is `NOT PROVEN` for the accepted v4 run, so execution
integrity is `NOT FULLY PROVEN`. Development scored 14,894 rows over 249
sessions, with 14,892
evaluable primary outcomes (99.9866%). Locked evaluation scored and evaluated
22,013 rows over 372 sessions (100%).

### Reproduction and independent verification

A second clean execution reproduced the prediction-table logical hash and
locked-sequence fingerprint exactly. Stage 2A, Stage 2B, Stage 2C, and final
logical hashes also matched exactly. Package-level logical hashes differ only
where run identity and parent-package provenance are deliberately operational
metadata; persisted table and scientific artifact identities are the decisive
reproduction anchors.

The independent evaluator does not import primary metric functions. It matched
cell selection, a bounded core of IC, tail, frequency, denominator and
concentration calculations, all classifications obtained by applying the gate
operators to stored values, and the `STOP` verdict. It did not independently
recompute every bootstrap, leave-contributor, annual, or other gate input. Its
primary logical hash is
`3e5ca0c5c37d4397d968b61e8dc5337240eb990957b07d98f5c44e129884c40f`;
the reproduction evaluator is independently `PASS` with logical hash
`196e456ad5774e94098f91e58aed219c346d1434fcb952675fabd689483c320a`.

Fresh audit-repair verification passed 29 focused Phase D2 tests, all 216 tests
in the supported Python suite, and all 10
pre-Phase-D market-state regressions. The current D1 v3 structural CLI,
primary/reproduction Stage 1 validators, and all eight primary/reproduction
evaluation-stage validators pass. The independent evaluator was also rerun
read-only against both sealed roots and returned the same two logical hashes and
`STOP` verdict.

### Versioned audit v2

The frozen bounded repair published `audit-v2` beside both accepted evaluation
roots without editing any accepted artifact. Primary and reproduction audit
scientific payloads match exactly at
`397d66ed3c88c8e914c1a6bbdc9af7875f0d553acbd86c48dcb8d3f64eab944c`.
Both validate the prediction and every evaluation-stage seal, independently
select `C_LIGHTGBM` and `RICH_LIGHTGBM`, independently reproduce the decisive
negative rich-minus-`C_LINEAR` IC anchors, retain `STOP — VERIFIED`, and report
execution integrity `NOT FULLY PROVEN`. See
[`PHASE_D2_AUDIT_REPAIR.md`](PHASE_D2_AUDIT_REPAIR.md).

The historical D0/D1 v3 validators pass when replayed from their accepted
activation checkpoint `1dc9bbd` using exact committed bytes. On the current tree
their only mismatch is the older D0 manifest's hashes for `README.md` and
`RESEARCH/IMPLEMENTATION_ROADMAP.md`, which necessarily changed to record Phase
D2. Current controlling guidance was not rolled back to make a historical
manifest green; every D0 scientific and contract check remains `PASS`.

### Preserved operational corrections

Three failed prediction publications, one failed Stage 2A publication, and the
scientifically valid but lineage-superseded evaluation v5 remain preserved.
They were never overwritten or deleted. Each smallest operational correction
was committed before recalculation:

| Commit | Contained correction |
|---|---|
| `64ee4cf` | Preserve failed Phase D2 publications. |
| `a379894` | Correct population-proof validation. |
| `1b8d9ed` | Correct inverted no-metrics validation. |
| `c6e6efe` | Bind identities to persisted Parquet tables. |
| `36f82b6` | Make atomic stage validation use the staged path. |
| `7f1ba4a` | Use the scientific prediction-table fingerprint for reproduction lineage. |

No correction changed a feature, label, model, chronology, threshold, gate,
population, or other scientific choice.

## 2. Stage 2A model-family selection

Stage 2A selected within representation only, using equal-session mean Spearman
rank IC across the two 2023 model-selection blocks. It never selected rich
against conventional.

| Frozen cell | Selection statistic |
|---|---:|
| `C_LINEAR` | -0.067876 |
| `C_LIGHTGBM` | -0.031079 |
| `RICH_LINEAR` | -0.026921 |
| `RICH_LIGHTGBM` | 0.056390 |

`C_LIGHTGBM` and `RICH_LIGHTGBM` were selected. Neither within-representation
difference triggered the frozen ridge tie rule. `RICH_LIGHTGBM` then became the
sole rich challenger for decisive Stage 2B/2C evaluation; the unselected rich
cell could not rescue it.

## 3. Stage 2B development confirmation

Across 2024, mean session IC was 0.005886 for the selected rich model, 0.021092
for `C_LINEAR`, and -0.004789 for `C_LIGHTGBM`. The rich-minus-comparator mean
delta was therefore -0.015205 against `C_LINEAR` and +0.010675 against
`C_LIGHTGBM`. The paired bootstrap lower bounds were -0.075757 and -0.038807,
respectively. The rich representation failed the frozen development incremental
information requirement against both comparators.

The two half-years were not stable. Rich-minus-`C_LINEAR` IC changed from
+0.019384 in 2024 H1 to -0.049519 in H2; rich-minus-`C_LIGHTGBM` changed from
+0.025627 to -0.004157. The H2 and leave-block-out gates failed.

## 4. Stage 2C locked evaluation

Across complete locked blocks 2025 H1, 2025 H2, and 2026 H1, mean session IC was
0.039463 for the rich model, 0.064749 for `C_LINEAR`, and 0.018319 for
`C_LIGHTGBM`. Rich-minus-comparator mean delta was -0.025285 against `C_LINEAR`
and +0.021144 against `C_LIGHTGBM`; paired bootstrap lower bounds were -0.070670
and -0.019877. The rich representation again failed the decisive incremental
information requirement against both comparators.

The block evidence was mixed. Rich-minus-`C_LINEAR` IC was +0.033813, -0.010421,
and -0.099609 across the three locked blocks. Rich-minus-`C_LIGHTGBM` IC was
+0.019098, +0.036210, and +0.007757, but none of this could overcome the
negative paired lower bound or the required comparison with `C_LINEAR`.

## 5. General rank-information diagnostics

Positive standalone rich IC in the locked period is not the frozen claim. The
claim required stable incremental information against each fixed comparator.
The rich model trailed `C_LINEAR` in development and locked aggregate IC, and
the paired uncertainty bound was below zero against both comparators in both
populations. Approximately tying or selectively beating only one comparator is
failure by contract.

## 6. Selective opportunity-tail evidence

Development produced 2,538 raw candidate rows but only 198 non-overlapping
episode anchors across 43 opportunity sessions and 61 securities, or 12.82 raw
candidates per episode. Rich episode mean return was -0.4294%, median return was
-1.6338%, and the rate above +1% was 39.90%. Frequency-matched rich-minus-return
was -0.0343% versus `C_LINEAR` and +0.1538% versus `C_LIGHTGBM`; rich-minus-all-
eligible return was -0.1828%. Relevant mean, lower-bound, severe-outcome,
median, opportunity-count, and overlap gates failed.

Locked evidence produced 1,119 raw candidate rows but only 133 non-overlapping
episodes across 28 opportunity sessions and 59 securities, or 8.41 raw
candidates per episode. Rich episode mean return was +2.5818%, median was
+1.9149%, and the rate above +1% was 52.63%. However, frequency-matched
rich-minus-return was -0.6514% versus `C_LINEAR` and -1.2910% versus
`C_LIGHTGBM`; both bootstrap lower bounds were negative. The positive standalone
tail therefore did not establish superior selective opportunities.

## 7. Chronology and stability

Development candidate-row frequency fell from 30.07% in 2024 H1 to 4.05% in
H2; opportunity-session frequency fell from 74.19% to 20.00%. The H1 candidate
rate and both p95 candidate-count gates failed.

Locked candidate-row frequency was 13.74%, 0.92%, and 0.73% across the three
complete blocks; opportunity-session frequency was 52.85%, 8.73%, and 9.76%.
The 2025 H1 candidate/p95 gates and the minimum opportunity-session gates in
2025 H2 and 2026 H1 failed. The partial 2026 H2 monitoring block contains 35
sessions and 2,100 scored rows, with 1.29% candidate-row frequency and 62.86%
idle sessions. It has no loaded outcomes and is nongating.

The largest chronological episode quartile held 46.97% of development episodes
and 43.61% of locked episodes; both frozen concentration gates failed. Complete-
year positive performance versus `C_LINEAR` occurred in only half of the
eligible years, below the required 75%.

## 8. Session, period, security concentration and influence

Audit v2 adds the D0-required session dimension from the accepted episode
anchors. Development's largest session held 21.21% of 198 episodes, its top five
sessions held 56.57%, and session HHI was 0.09285. Locked evidence's largest
session held 27.07% of 133 episodes, its top five held 54.14%, and session HHI
was 0.10815. The largest half-year shares were 74.24% and 55.64%, with half-year
HHIs 0.61754 and 0.40935. No threshold was frozen for these reporting
diagnostics, so they do not change a gate or the verdict.

The absolute security counts and simple concentration statistics were not the
principal problem: the largest-security episode shares were 3.03% development
and 3.76% locked, with top-five shares of 12.63% and 15.79%. The stronger
leave-one-top-contributor-out requirements failed repeatedly, especially against
`C_LINEAR`, and the locked tail comparison remained negative after removing each
top contributor. Thus the result was not stable under the prespecified influence
checks.

## 9. Frozen market-state ablation

The `RICH_LIGHTGBM` minus `RICH_NO_M_LIGHTGBM` mean-session-IC difference was
-0.022349 in development and -0.028911 in locked evaluation on identical
populations. This ablation is diagnostic only. It suggests the carried market-
state block did not add rank information here, but it cannot change model
selection, alter the verdict, or authorize a new representation search.

## 10. Proximity-Q5 and secondary diagnostics

The 5- and 10-session forward-label ICs were computed exactly as nongating
diagnostics. They were mixed and cannot rescue the primary 20-session evidence.

The frozen proximity-Q5 diagnostic contained 2,988 development rows and 4,465
locked rows. Per-session IC is `NOT PROVEN` because no session met the frozen
45-observation IC minimum inside Q5. No pooled substitute or threshold change
was introduced after inspection.

Feature importance was optional and was not computed. MFE, MAE,
time-to-excursion, and path-shape diagnostics remain `DEFERRED BY CONTRACT`
because the frozen plan provided no formula. D2 did not invent one after seeing
results.

## 11. Inherited caveats

- Results are split-adjusted **price-only**, not total return. Cash
  distributions are excluded and known dividend price gaps remain visible.
- The locked period is historical, not genuinely untouched forward evidence.
  Historical outcomes through 2026-08-18 influenced the wider research program.
- No portfolio or realized trading economics were tested. Opportunity rows and
  episodes are not trades; the study contains no sizing, fills, costs, cash
  ledger, or portfolio-performance claim.
- Partial 2026 H2 is right-censored, outcome-free, and nongating.
- Stage 2A selected model family within each representation only; it did not
  select rich against conventional.
- The selected `RICH_LIGHTGBM` cell is the sole decisive rich challenger. The
  unselected rich cell and all secondary diagnostics cannot rescue it.
- Positive standalone rich IC or opportunity return is insufficient. The claim
  required material, stable superiority against both conventional comparators.
- Approximately tying a conventional model fails to justify additional
  complexity under the frozen rule.
- Locked evidence cannot rescue a failed development-confirmation requirement.

## 12. Complete gate matrix

The immutable machine gate matrix is:

`D:\Stock\data\ATS\phase_d_ml\evaluation_runs\phase-d2-evaluation-20260902-v6\final\gate_matrix.json`

| Category | PASS | FAIL | NOT PROVEN |
|---|---:|---:|---:|
| Execution integrity (historical asserted rows) | 26 | 0 | 0 |
| Validity | 8 | 0 | 0 |
| Reproducibility | 1 | 0 | 0 |
| Incremental rank information | 3 | 8 | 0 |
| Tail outcome separation | 2 | 22 | 0 |
| Chronological stability | 14 | 12 | 0 |
| Opportunity evidence | 4 | 4 | 0 |
| Frequency and abstention | 18 | 7 | 0 |
| Concentration | 23 | 25 | 0 |
| **Total** | **99** | **78** | **0** |

The table above reconciles the immutable accepted matrix. Its 26 historical
execution-integrity rows were emitted as unconditional values and are not
independent proof. Audit v2 derives thirteen artifact-backed integrity
dimensions as `PASS` but classifies the additional sequential-label-admission
claim `NOT PROVEN`; overall execution integrity is therefore `NOT FULLY
PROVEN`. The scientific predictive package is sufficient to verify `STOP`, but
independent coverage is bounded. Every individual gate ID, population,
comparator, operator, value, threshold, and classification is retained in the
machine matrix; this table is its complete category reconciliation.

## 13. Mechanical research verdict

With sealed validity/reproducibility evidence and decisive independently
recomputed failures, the frozen mapping still mechanically implies:

- frozen Phase D research verdict: **STOP — VERIFIED**;
- Phase D3 execution authorized: **NO**;
- portfolio/backtest work authorized: **NO**.

No diagnostic may reverse this result, and favorable locked standalone metrics
cannot cure a failed 2024 confirmation gate.

## 14. Actions deferred to owner review

This task stops at owner review. The negative result is retained as the Phase D2
decision. Execution integrity remains `NOT FULLY PROVEN`; that qualification
does not authorize a rerun. No additional indicator, horizon, objective, model,
infrastructure, Phase D3, portfolio translation, or deployment work is
authorized by this run.
