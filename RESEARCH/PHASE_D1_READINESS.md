# Phase D1 readiness

Status: **PASS — safe to request separate owner authorization for Phase D2**
Assessment date: 2026-09-01
Controlling structural run: `phase-d1-structural-f6856e5c5f485c002b4b`

This checkpoint answers only whether ATS can reconstruct the frozen Phase D
observation/features/label endpoints/chronology and pass repository-authorized
synthetic fixtures through the two frozen model classes without PIT, identity,
preprocessing or execution-boundary leakage. It does not authorize or contain a
real GPW fit, prediction, model selection, performance result or D2 verdict.

## Bounded decision and scope

- Exact decision: whether the frozen D0 v2 experiment is technically safe to
  present for a separate D2 execution decision.
- Cheapest credible experiment: hand-built and deterministic synthetic fixtures,
  plus one label-blind real pass for the four prespecified structural facts.
- Must-have validity: exact PIT timing/windows, official denominator 60, causal
  missing states, source/factor validity, label isolation, endpoint-derived purge,
  fold-local preprocessing, identity-blind matrices, immutable provenance and a
  real-data fit/predict firewall.
- Useful nongating diagnostics: formula fingerprints, feature coverage counts and
  the registry-wide normalized-formula collision audit.
- Deferred: real model-family selection, real scores/evaluation, inference,
  episode/concentration/tail gates, final STOP/CONTINUE and portfolio translation.
- Stop rule: any in-scope FAIL, fewer than five P survivors, any real label/fit/
  prediction/performance access, or any D0 scientific change would stop D1.

## Starting-state verification

The requested starting commit
`5e971924023e6e19226269771a40492d113ebc43` was verified as the direct parent of
the actual starting HEAD `cbddb4ff13f4452aa37f427f0f3c09a3f3da1ae4`.
The intervening commit only adds the D0 feature-registry review table. The D0
validator passed before implementation. Unrelated pre-existing untracked
environment-repair files and `RESEARCH/environments/` were preserved.

Accepted D0 v2 byte anchors remain:

| Artifact | SHA-256 |
|---|---|
| `RESEARCH/PHASE_D0_EXPERIMENT_PLAN.md` | `10645dd41f1aea1f74c9f137a2f0dfd34e0a0f41f6355854c0cf9ed4b9ba0baa` |
| `source/python/configs/phase_d0_reference.json` | `ef5a7f0fa76a104ff86cae7c2ad520867a0720e1c6e508558ef31316e7e153ae` |
| `source/python/configs/phase_d0_feature_registry.json` | `733bacb9c1132d98eacb4a190cfb3cd96b0163207af46f3745002206b3705ef6` |
| `RESEARCH/PHASE_D0_MANIFEST.json` | `7fe34d679511eb4d75b269f5a908c6ac5e624d624aa067645286576f0f9e918c` |

These values are pinned independently in D1 code, so coordinated edits to the D0
manifest and its declared artifacts fail closed without a versioned amendment.

## Implemented D1 boundary

The minimal `ats_ml` package provides frozen-contract loading, guarded fixture
contexts, C/P/X/M calculation, observation eligibility, synthetic label values,
endpoint chronology, four-cell matrices, Ridge/LightGBM adapters, abstention and
fractional-tie mechanics, duplicate resolution and immutable structural evidence.

Important fail-closed properties are fixture-proven:

- feature inputs reject label/prediction columns before copying;
- label values are admitted only for repository-registered content hashes;
- model fitting accepts only immutable registered fixture matrix/target hashes;
- prediction requires an authentic sealed fit state bound to adapter class,
  estimator identity and serialized fitted-state hash, feature names, suite and
  fit provenance;
- raw arrays, arbitrary copied frames, public state mutation, unfitted adapters
  and estimator replacement cannot mint accepted scores;
- every emitted missing/exclusion code belongs to the frozen D0 vocabulary;
- the four numerical matrices are invariant to identity/ticker/source changes and
  row order while identity remains outside the predictor boundary.

## Structural resolution

Immutable directory:
`D:\Stock\data\ATS\phase_d_ml\structural_runs\phase-d1-structural-f6856e5c5f485c002b4b`

- Logical hash: `f6856e5c5f485c002b4bbd76a7c44a411353ffc26a5f1e1e9e9cebd8675a9e15`
- Structural-resolution bytes: `fe5df6c646140b4b48b6f3e032e0e5ce6ec43bca681b08c0652d9cc0fc644506`
- Permitted-read audit bytes: `106e0e774ff4638f8423fd829a6d9f00cf09abaeacac6d5883dbe249997b1cf1`
- Candidate rows: 130,204; official member rows: 99,780; official count:
  exactly 60 per session.
- P population: 75,360 rows over 1,256 sessions through 2024-12-30.
- P outcome: all eight predictors survive; there are no removal decisions.
- Registry formula audit: 30 declarations, 30 normalized formulas, zero collisions.

The builder loaded only `security_id`, session, adjusted close/high/low,
membership, price usability, source-treatment/factor and missing-state lineage
needed for the four resolutions. It did not load adjusted open or market-state
feature values and did not load/derive a forward label, fit, score, prediction,
feature-label association, IC, tail outcome, performance or economics.

### Resolved purge boundaries

Each entry is `last retained / first purged`.

| Fold | Fit | Calibration | Evaluation/right-censor |
|---|---|---|---|
| MODEL_SELECTION_2022 | 2020-11-30 / 2020-12-01 | 2021-12-01 / 2021-12-02 | 2022-12-01 / 2022-12-02 |
| DEV_2023 | 2021-12-01 / 2021-12-02 | 2022-12-01 / 2022-12-02 | 2023-11-29 / 2023-11-30 |
| DEV_2024 | 2022-12-01 / 2022-12-02 | 2023-11-29 / 2023-11-30 | 2024-11-27 / 2024-11-28 |
| LOCKED_2025_2026 | 2023-11-29 / 2023-11-30 | 2024-11-27 / 2024-11-28 | 2026-07-21 / 2026-07-22 |

### Resolved chronological concentration bins

| Fold | Bin 1 | Bin 2 | Bin 3 | Bin 4 |
|---|---|---|---|---|
| MODEL_SELECTION_2022 | 2022-01-03..2022-03-24 (58) | 2022-03-25..2022-06-20 (58) | 2022-06-21..2022-09-09 (58) | 2022-09-12..2022-12-01 (57) |
| DEV_2023 | 2023-01-02..2023-03-23 (58) | 2023-03-24..2023-06-20 (58) | 2023-06-21..2023-09-08 (57) | 2023-09-11..2023-11-29 (57) |
| DEV_2024 | 2024-01-02..2024-03-21 (58) | 2024-03-22..2024-06-17 (57) | 2024-06-18..2024-09-05 (57) | 2024-09-06..2024-11-27 (57) |
| LOCKED_2025_2026 | 2025-01-02..2025-05-22 (97) | 2025-05-23..2025-10-08 (97) | 2025-10-09..2026-03-03 (97) | 2026-03-04..2026-07-21 (96) |

## Environment and verification

Structural fingerprints record Python 3.12.13 on Windows 11 and exact hashes for
every `ats_ml` source file, every registered formula, the D0 registry, D1 fixture
registry and environment lock. Installed decision-relevant versions are NumPy
1.26.4, pandas 3.0.5, Polars 1.43.2, pyarrow 25.0.0, scikit-learn 1.9.0 and
LightGBM 4.7.0. Exact complete fingerprints and fixed parameter dictionaries are
in `source/python/configs/phase_d1_structural_resolution.json`.

Final verification results:

- Focused Phase D1: **64 passed in 47.76s**.
- Supported complete `source/python` suite: **171 passed in 68.61s**.
- Pre-Phase-D market-state regression: **10 passed in 3.35s**.
- Phase D0 validator: **PASS**.
- Structural publication: **PASS**, repeated twice with identical logical and
  physical identities.

Supported reproduction commands:

```powershell
Set-Location 'D:\Stock\ATS'
& 'D:\Stock\ATS\RESEARCH\environment\invoke_ats_python.ps1' 'D:\Stock\ATS\RESEARCH\prototypes\phase_d0\validate_phase_d0.py'
& 'D:\Stock\ATS\RESEARCH\environment\invoke_ats_python.ps1' -m pytest -q 'D:\Stock\ATS\RESEARCH\prototypes\pre_phase_d_market_state\tests'
& 'D:\Stock\ATS\RESEARCH\environment\invoke_ats_python.ps1' -m pytest -q source/python/tests/test_phase_d1_contract_firewall.py source/python/tests/test_phase_d1_features.py source/python/tests/test_phase_d1_labels_chronology.py source/python/tests/test_phase_d1_models_opportunity.py source/python/tests/test_phase_d1_observations_structural.py
Set-Location 'D:\Stock\ATS\source\python'
& 'D:\Stock\ATS\RESEARCH\environment\invoke_ats_python.ps1' -m pytest -q
& 'D:\Stock\ATS\RESEARCH\environment\invoke_ats_python.ps1' -m ats_ml structural-validate 'D:\Stock\data\ATS\phase_d_ml\structural_runs\phase-d1-structural-f6856e5c5f485c002b4b'
Set-Location 'D:\Stock\ATS'
& 'D:\Stock\ATS\RESEARCH\environment\invoke_ats_python.ps1' 'D:\Stock\ATS\RESEARCH\prototypes\phase_d1\validate_phase_d1.py'
```

`structural-resolve` is intentionally omitted from routine reproduction because
the immutable run already exists; invoking it again is collision-safe and was
used once for the recorded reproduction check.

## Independent review and residual uncertainty

Two bounded independent reviews challenged formulas/fixtures and the execution
firewall. Their actionable failures were corrected before the final structural
pass. During the first feature review, a reviewer inadvertently saw an already
published pre-Phase-D association-summary line while locating definition evidence.
The exposure was disclosed, did not include a real Phase D label/prediction, and
did not change a fixture or frozen choice.

Nongating `NOT PROVEN` items remain explicit:

1. Authoritative exhaustive split-event discovery for the inherited candidate
   panel remains unproven. The pinned panel remains research-grade and accepted
   with caveats, not canonical data.
2. Live operational data/feed availability at 08:45 is not proven by historical
   timestamp semantics. D1 is not deployment or auction-execution evidence.

## Readiness judgment

All D1 gating requirements are PASS. It is safe to ask the owner whether to
authorize Phase D2, but Phase D2 remains unauthorized. Any future authorization
must keep this exact structural run, D0 v2 bytes, P survivors, boundaries,
feature/model parameters and firewall lineage pinned; it must not follow a
mutable pointer or reinterpret this readiness result as predictive evidence.
