# ATS research retention manifest

## Purpose and scope

This manifest records the Git-retention decision for the previously untracked `D:\Stock\ATS\RESEARCH` tree at the Phase A/B/C review checkpoint. Classification was read-only: excluded files were not deleted, moved, regenerated, or modified. Published data beneath `D:\Stock\data\ATS` is outside this Git inventory and remains immutable.

Inventory date: 2026-08-21 (Europe/Warsaw). Before review artifacts were added, the readable tree contained 4,485 files in 6,103 readable directories and 11,757,377,691 bytes (about 10.95 GiB). Git exposed 138 untracked files totaling 1,939,763 bytes and ignored 4,347 files totaling 11,755,437,928 bytes. Two old pytest temporary directories were ACL-inaccessible and could not be inspected: `prototypes\environment_repair\pytest-20260820T160327110` and `pytest-phase-a-20260820T160644838`. They are classified as temporary by name and excluded by rule; their contents are **not proven**.

## Durable content retained in commit 1

| Group | Included content | Why it is durable |
|---|---|---|
| Architecture and decisions | Root `README.md`, audits, architecture options/recommendation, technology comparison/matrix, roadmap, feedback assessment | Records evaluated alternatives, evidence, and decisions rather than generated data |
| Benchmarks | `LOCAL_BENCHMARKS.md`, `benchmark_results.csv`, prototype benchmark source/config/tests | Retains measured results, schema explanation, and code needed to reproduce bounded measurements |
| Phase A research | `POST_PHASE_A_DIAGNOSTIC_REPORT.md`, final `PHASE_A_DECISION_ORIENTED_REPORT.md`, decision-oriented and post-Phase-A source/config/plans | Retains favorable and unfavorable findings, exact conventions, and report-generating logic |
| Archived Phase A validation source | `prototypes\post_phase_a_diagnostics\phase_a_validation_source_caf76ee` | Self-contained source snapshot used when the shared checkout had evolved; supports archive-integrity evidence |
| Canonical environment | `environment\` portable specification, hash, recreation/repair scripts, wrapper, README, promotion and kernel-repair verification | Current reproducibility bundle; `environment.yml` is prefix-free, SHA-256 `290334A1C972E3780B354ACFC607C076CE4AE6A77B0905EB41DFB5AA45E48A6D` |
| Environment-repair forensic subset | wrapper, smoke/capture source, exact Conda-meta lock and hash | Explains the repaired execution path and exact package/build evidence without retaining a temporary environment or generated smoke artifacts |
| Diagnostics | `PYTHON_CRASH_DIAGNOSTIC_REPORT.md` and prototype sources | Durable diagnosis and reproduction procedure, not transient logs |
| Retention controls | this manifest, `RESEARCH\.gitignore`, and the nested cache `.gitignore` | Makes inclusion and exclusion intentional and reviewable |

The earlier post-Phase-A report is retained as a dated audit trail; the later decision-oriented report supersedes it for current classifications but does not erase the earlier evidence. Architecture/roadmap documents are retained as historical decision records and must not be read as claims that every proposed module was implemented.

## Content intentionally left uncommitted

| Path/category | Decision | Reason |
|---|---|---|
| `RESEARCH\.tmp` | Ignore, do not delete | Notebook/environment runtime scratch only |
| `prototypes\cache` (3,854 files; 11,746,939,668 bytes) | Ignore, do not delete | Generated benchmark data and layouts; nested `.gitignore` retains only its control file |
| Eight 1.0–1.6 GiB layout Parquet monoliths | Ignore, do not delete | Generated bulk datasets; largest material risk in the tree |
| All prototype cache Parquet/layout outputs | Ignore, do not delete | Rebuildable and too large; root benchmark CSV/reports retain durable results |
| Small cache CSV/JSON duplicates | Leave ignored | Root `benchmark_results.csv` and reports are the retained evidence; cache copies are generated intermediates |
| `environment_repair` runtime directories, pytest temp dirs, Matplotlib/Numba caches | Ignore, do not delete | Execution scratch/caches, including two ACL-inaccessible pytest directories |
| Repeated smoke PNG/Parquet/output directories | Ignore, do not delete | Generated environment tests; source, JSON/lock evidence, and reports are sufficient |
| `RESEARCH\environments` legacy exports | Leave uncommitted, visible for owner decision | Superseded by canonical `environment\`; YAMLs contain machine prefixes, explicit locks are Windows-specific, and one event export is documented as dirty |
| `environment_repair\repaired_environment.yml` and `.json` | Leave uncommitted | Superseded promotion-stage exports with former machine-local prefix/executable paths |
| logs/crash scratch | Ignore | No current log is required to support a durable report |
| notebook checkpoints | Ignore | Editor-generated state |
| credentials/tokens/secrets | Exclude | No credential assignment or embedded URL credential was found in accessible environment/research text; future secrets remain prohibited |

Excluded content remains on disk and recoverable subject to the existing filesystem. Nothing was deleted.

## `.gitignore` rule rationale

| Rule | Rationale |
|---|---|
| `.tmp/` | Existing ATS runtime scratch root |
| `.ipynb_checkpoints/` | Notebook editor checkpoints are generated |
| `.runtime/` | Environment-repair runtime files are generated |
| `pytest-*/` | Test base-temporary directories, including inaccessible old directories |
| `.matplotlib_cache/`, `.matplotlib_test/`, `mplcache/`, `numbacache/` | Generated library caches |
| `prototypes/environment_repair/retained_smoke*/` | Repeated generated smoke result directories |
| `prototypes/environment_repair/*.parquet`, `*.png` | Generated smoke binary artifacts only; rule is deliberately scoped to environment repair |
| `*.log` | Transient execution logs; durable findings belong in Markdown/JSON reports |

The pre-existing nested `prototypes\cache\.gitignore` uses `*` plus `!.gitignore`, excluding every generated cache payload while retaining the boundary file itself.

## Environment and secret review

- Canonical `environment\environment.yml` has no prefix and no observed credential/token assignment.
- Canonical scripts and `promotion_verification.json` contain machine paths such as `C:\Users\konra` and `D:\Stock`; these are documented current-machine instructions/evidence, not credentials.
- The exact Conda-meta forensic lock contains package/build and installed-prefix metadata. It is retained to reproduce the environment audit, not as a portable specification; `environment\environment.yml` remains the portable recreation source.
- Legacy `environments\*-environment.yml` files expose old machine prefixes and their exact exports are platform-specific. They remain uncommitted pending an explicit owner decision.
- No large binary, generated benchmark dataset, credential, token, connection secret, publication data, or temporary environment is authorized for staging.

## Uncertain or owner-decision items

1. Whether legacy, machine-prefixed environment exports have audit value beyond the canonical prefix-free environment bundle.
2. Whether the inaccessible old pytest temporary directories may eventually be removed; this checkpoint neither inspects nor deletes them.
3. Whether any ignored cache-only result JSON should be promoted into a future small, reviewed report. No promotion was needed because retained root CSVs/reports already carry the referenced conclusions.
4. Whether the self-contained Phase A source snapshot should remain in Git indefinitely after archive-validation tooling is institutionalized. It is retained now because it was materially used to distinguish checkout drift from archive corruption.

## Staging safety contract

Commit 1 is staged from an explicit whitelist, never `git add RESEARCH`. Before commit, the staged diff must show only the durable groups above, this manifest, and ignore controls. `RESEARCH\ATS_REVIEW_NOTES.md` is reserved for commit 2. `source\python\README.md`, production source, tests, configurations, publications, caches, binaries, and unrelated changes must remain unstaged.
