# Phase D1 readiness v2 — narrow correctness repair

Status: **PASS — safe only to request a separate owner decision about Phase D2**

Assessment date: 2026-09-01

Controlling structural run: `phase-d1-structural-b4fb9bbc480c2026e423`

Phase D2 remains unauthorized. This report contains no real GPW forward-return
label value, real fit, real prediction, predictive metric, economic result or
model-family selection.

## Supersession

This report supersedes the rejected Phase D1 publication at commit
`be3cacd6fab9b67e98dc7e1e05b00ebac002c193`. The original
`PHASE_D1_READINESS.md`, `PHASE_D1_REQUIREMENT_AUDIT.json` and
`PHASE_D1_MANIFEST.json` remain preserved as v1 evidence; they are not accepted
readiness evidence.

The owner review identified four bounded defects:

1. the v1 report and manifest claimed a passing D0 validator although D1 had
   changed two D0-pinned documentation files;
2. matrices, targets and scores did not carry an ordered semantic row ledger;
3. the published structural validation command used the wrong CLI syntax; and
4. the observed candidate/WIG and membership/market-state calendar equalities
   were not asserted by code.

No feature formula, label definition, fold, purge rule, model family, parameter,
threshold, D0 scientific contract or real predictive result was reopened.

## Repair 1 — validation evidence is executable and consistent

`README.md` and `RESEARCH/IMPLEMENTATION_ROADMAP.md` were restored byte-for-byte
to the versions pinned by the unchanged D0 manifest. Their current hashes are:

| Artifact | SHA-256 |
|---|---|
| `README.md` | `a9ee08501e45e86d583fe1f92de128fb9f7f37f21d3f0456dfa770ccb70195bd` |
| `RESEARCH/IMPLEMENTATION_ROADMAP.md` | `2b3a5eadc1605daf21b2b825d18b0952cd70840172c610b0155b573b6666f67b` |

The documented Phase D0 validator now returns PASS in the repaired tree. The four
authoritative D0 anchors also remain unchanged:

| Artifact | SHA-256 |
|---|---|
| `RESEARCH/PHASE_D0_EXPERIMENT_PLAN.md` | `10645dd41f1aea1f74c9f137a2f0dfd34e0a0f41f6355854c0cf9ed4b9ba0baa` |
| `source/python/configs/phase_d0_reference.json` | `ef5a7f0fa76a104ff86cae7c2ad520867a0720e1c6e508558ef31316e7e153ae` |
| `source/python/configs/phase_d0_feature_registry.json` | `733bacb9c1132d98eacb4a190cfb3cd96b0163207af46f3745002206b3705ef6` |
| `RESEARCH/PHASE_D0_MANIFEST.json` | `7fe34d679511eb4d75b269f5a908c6ac5e624d624aa067645286576f0f9e918c` |

The v2 D1 validator runs the D0 validator as a subprocess and requires both exit
code zero and JSON status PASS. A future documentation/hash contradiction can no
longer pass the D1 publication validator.

## Repair 2 — immutable semantic row binding

Every `ModelMatrix`, `ModelTarget` and `ModelScores` object now carries the same
sealed ordered `SemanticRowLedger` with exactly:

```text
candidate_run_id
contract_version
decision_session
security_id
```

The ledger is normalized, duplicate-free, immutable and hashed in row order.
Registered model fixtures pin the expected semantic-row hash independently from
their numerical matrix and target hashes. Fit requires exact matrix/target ledger
equality. Prediction propagates the evaluation matrix ledger into the score
object, and score provenance includes that hash. Bound-frame accessors return the
keys beside predictors, target or score so downstream work does not need to
reconstruct positional meaning.

Input row reordering canonicalizes to the same ledger. Reassigning identities
changes the semantic-row hash and provenance even when the numerical predictors
remain identical. Identity fields remain excluded from the numerical predictor
allowlist. Reversed or substituted target ledgers fail before estimator fitting.

The v2 fixture-registry hash is
`91e37cd8b8a2354316d83840e86422665329d3c2a6442b8f0c8d41cfeee522fa`.

## Repair 3 — supported structural command

The supported command is:

```powershell
Set-Location 'D:\Stock\ATS\source\python'
& 'D:\Stock\ATS\RESEARCH\environment\invoke_ats_python.ps1' -m ats_ml validate-structural --run-dir 'D:\Stock\data\ATS\phase_d_ml\structural_runs\phase-d1-structural-b4fb9bbc480c2026e423'
```

It returns PASS. The v2 D1 validator invokes this exact command form through the
current Python interpreter and checks its returned run ID, logical hash and file
hashes. The invalid v1 `structural-validate <path>` form is not retained as a
supported command.

## Repair 4 — calendar provenance is asserted

The structural builder now reads only the two calendar key columns required for
the assertion:

- `session_date` from the accepted market-state run's manifest-pinned
  `validated_wig.parquet`; and
- `decision_session` from the pinned `market_state_features.parquet`.

It compares the candidate calendar to validated WIG over the exact candidate
date range and compares sessions with official membership to accepted
market-state decision sessions. A missing or extra session on either side fails
closed before publication.

The controlling run records:

| Equality | Counts | Ordered calendar hash | Result |
|---|---:|---|---|
| Candidate vs validated WIG | 1,915 / 1,915 | `5b88b3a54bf496304de16dc18029aedbca602921e10077248711112336f7c7eb` | PASS |
| Official membership vs market state | 1,663 / 1,663 | `466b76b5f932364e97144121b99e48a143a024e778c5e886a5be1770dbe71d45` | PASS |

No market-state feature value was loaded for this assertion.

## Superseding structural evidence

Immutable directory:
`D:\Stock\data\ATS\phase_d_ml\structural_runs\phase-d1-structural-b4fb9bbc480c2026e423`

- Logical hash: `b4fb9bbc480c2026e423f59cc0c047d635571f58c3493fcdf1a64ab6b31f911a`
- Structural-resolution SHA-256: `6801c396932a7200960dfedd72b9454088e8f7875c9af9ef402ef212005a599b`
- Permitted-read-audit SHA-256: `7b48361fb082c305374d04dacfc2a50653b3c2616fd7dcf71aae2bd3c652a717`
- Candidate rows: 130,204; official member rows: 99,780; official
  denominator: exactly 60 per session.
- P structural population: 75,360 rows across 1,256 sessions through
  2024-12-30; all eight P features survive.
- The previously resolved purge boundaries and chronological bins are unchanged.
- Two consecutive `structural-resolve` calls returned the same run ID, logical
  hash and physical hashes.

The read audit records 13 candidate value columns plus the two calendar keys.
Adjusted open, forward labels, model scores, predictions, IC, tail outcomes and
economics were neither loaded nor derived.

## Verification

Final repaired results:

- Focused Phase D1 suite: **67 passed in 48.03s**.
- Supported complete `source/python` suite: **174 passed in 84.61s**.
- Pre-Phase-D market-state regression: **10 passed in 3.40s**.
- Phase D0 validator: **PASS**.
- Correct structural CLI: **PASS**.
- Structural publication replay: **PASS**, identical identity and bytes.

The superseding v2 validator additionally checks every v2 manifest artifact,
the requirement audit, D0 subprocess result, corrected CLI subprocess result,
calendar proof, structural authorization state and absence of real predictive
execution.

## Residual uncertainty and boundary

The inherited exhaustive split-discovery caveat and live 08:45 operational-feed
availability remain nongating NOT PROVEN items. They are not hidden or promoted
to canonical/deployment claims.

The repaired D1 evidence supports only this statement: it is safe to ask the
owner whether to authorize a separately bounded Phase D2. It does not itself
authorize D2, open MODEL_SELECTION_2022 to a model, or establish any predictive
or economic result.
