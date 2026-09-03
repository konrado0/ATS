# Phase D2 C+P+X model-mechanism results

**Mechanical verdict:** `NONLINEARITY-DEPENDENT — WEAK`

**Integrity:** `PASS`

**Evidence level:** `RETROSPECTIVE_HYPOTHESIS_DEVELOPMENT_AND_ROBUSTNESS`

The frozen C+P+X representation has positive pooled incremental rank information
under Ridge, but that increment is not chronologically broad enough to pass the
prespecified gate against `C_LINEAR`. With C+P+X held fixed, LightGBM passes the
broad-increment gate against Ridge. The accepted no-M LightGBM cell also retains
positive pooled deltas and at least four of seven positive half-years against
both conventional comparators. The mechanical result is therefore
`NONLINEARITY-DEPENDENT — WEAK`.

This is retrospective mechanism evidence selected after inspecting D2 and D2-NM.
It does not overturn the original D2 `STOP`, establish alpha, provide prospective
confirmation, authorize a 48-month run, authorize portfolio work, or authorize
deployment. The only result-dependent permission is to discuss—not execute—the
separately frozen 36m-versus-48m rank-only diagnostic.

## Freeze, prediction seal, and reproduction

The prose plan and authoritative JSON contract were committed in `a26d8eb`
before the first real fit. The implementation used for the successful primary
and reproduction runs was committed at `a979072`.

The primary prediction-only package contains 207,608 rows: four cells on
identical semantic rows across seven complete half-years. It contains no label,
outcome, return, IC, classification, threshold, candidate, or episode column.
All 21 accepted per-block control comparisons—seven blocks for each of
`C_LINEAR`, `C_LIGHTGBM`, and `RICH_NO_M_LIGHTGBM`—matched exactly. The clean
reproduction produced byte-identical `predictions.parquet` bytes:

`21b918448fbb98e47dd299ad63f735f6949d7fede89d02f44efa473db66f19c2`

Three failed staging attempts are preserved under `.failed-*` directories. They
stopped before immutable publication and before outcome access: one at a
categorical-metadata row-ledger proof, one at a Windows CRLF/raw-byte provenance
check, and one at an in-memory-versus-persisted Parquet identity check. The
smallest validation corrections were committed separately; no scientific choice
changed.

The independently coded evaluator imports no primary metric functions. Its
decision-core hash exactly matches the primary evaluator:

`70731235fb59251b6e7609d1f9ab3f5405be1ac1f669c650a4b99dab968098c7`

The sealed evaluation manifest logical hash is
`b99a37ae5457836f0e01285037ff47e8b06439aa38ffe553adb001f90b929310`.

## Pooled cell results

All statistics use equal weight per defined session over 871 sessions and
average-rank Spearman ties.

| Cell | Mean session IC | Median session IC |
|---|---:|---:|
| `C_LINEAR` | +0.014201 | +0.024118 |
| `C_LIGHTGBM` | -0.002465 | -0.005143 |
| `RICH_NO_M_LINEAR` | +0.030122 | +0.027674 |
| `RICH_NO_M_LIGHTGBM` | +0.043755 | +0.049094 |

## Frozen contrasts

| Contrast | Mean delta | Median delta | Positive half-years | Positive sessions | 20-session MBB 95% interval | Broad increment |
|---|---:|---:|---:|---:|---:|---|
| Ridge C+P+X − `C_LINEAR` | +0.015921 | +0.013615 | 3/7 | 54.08% | [-0.020346, +0.055449] | **FAIL** |
| Ridge C+P+X − `C_LIGHTGBM` | +0.032587 | +0.034676 | 6/7 | 58.44% | [-0.006533, +0.070425] | **PASS** |
| LightGBM C+P+X − Ridge C+P+X | +0.013633 | +0.016004 | 5/7 | 54.65% | [-0.016452, +0.042350] | **PASS** |
| LightGBM C+P+X − `C_LINEAR` | +0.029554 | +0.023261 | 4/7 | 54.76% | [-0.008742, +0.070653] | **FAIL** |
| LightGBM C+P+X − `C_LIGHTGBM` | +0.046221 | +0.046513 | 6/7 | 60.85% | [+0.018968, +0.072022] | **PASS** |

Bootstrap intervals are uncertainty diagnostics and are not classification
gates. The Ridge representation result fails for three frozen reasons against
`C_LINEAR`: only 3/7 half-years are positive, the median half-year delta is
negative, and omitting 2023 H1 makes the pooled delta negative (-0.007675).
It passes the pooled materiality and concentration checks. LightGBM's nonlinear
increment passes every broad-increment gate despite its interval crossing zero.

## Half-year mechanism decomposition

| Half-year | Ridge C+P+X − `C_LINEAR` | Ridge C+P+X − `C_LIGHTGBM` | LightGBM C+P+X − Ridge C+P+X |
|---|---:|---:|---:|
| 2023 H1 | +0.158068 | +0.069708 | +0.034765 |
| 2023 H2 | -0.012387 | +0.001559 | +0.002093 |
| 2024 H1 | -0.034208 | -0.027966 | +0.027957 |
| 2024 H2 | -0.044081 | +0.001280 | +0.064512 |
| 2025 H1 | +0.046859 | +0.032144 | -0.023850 |
| 2025 H2 | -0.002850 | +0.043781 | +0.048319 |
| 2026 H1 | +0.001420 | +0.108787 | -0.060042 |

The standout 2023 H1 Ridge representation delta reflects a very weak
`C_LINEAR` level (-0.122430) and a positive Ridge C+P+X level (+0.035638).
LightGBM C+P+X was higher again (+0.070403). Because removing 2023 H1 reverses
the pooled Ridge-versus-`C_LINEAR` sign, this is not a broad Ridge representation
result.

Every tied largest-security removal remains positive for the three decisive
mechanism comparisons. Their largest positive security shares are 5.87% for
Ridge C+P+X versus `C_LINEAR`, 10.13% versus `C_LIGHTGBM`, and 7.96% for
LightGBM versus Ridge; corresponding largest positive half-year shares are
33.96%, 20.10%, and 19.66%. No 50% concentration gate triggers.

## Interpretation and boundary

The data support a narrow mechanism interpretation: C+P+X is not useless under
Ridge, but its historical advantage over the strongest Ridge baseline is too
dependent on 2023 H1 to count as a stable representation result. The fixed
LightGBM procedure extracts a broader incremental rank signal from the same
features, yet the accepted C+P+X LightGBM result remains weak against the
conventional set because it has only 4/7 positive half-years versus `C_LINEAR`.

Per the frozen action rule, discussion of a bounded 36m-versus-48m rank-only
diagnostic is permitted. Execution is not authorized. The existing prospective
LightGBM stream remains byte-for-byte unchanged and may continue to accumulate
under its existing contract.

