# ATS Python crash diagnostic and repair report

Date: 2026-08-20  
Original environment: `C:\Users\konra\anaconda3\envs\ats-stack-research`  
Repaired clone: `C:\Users\konra\anaconda3\envs\ats-stack-research-repaired`

## Outcome

The native Python terminations observed during the post-Phase-A work were
reproduced and identified. The primary cause was launching the Conda
environment's `python.exe` directly on Windows. That invocation did not put the
environment's `Library\bin` on `PATH`. NumPy's LAPACK forwarding DLL loaded, but
its delayed call into `mkl_rt.3.dll` failed at first use and terminated the
process with signed exit code `-1066598273`, Windows exception `0xC06D007F`.

The same NumPy operations pass in the original environment when launched with
`conda run`, proving that Conda activation/DLL resolution—not the analytical
inputs or a NumPy API error—was the immediate crash trigger.

A cloned environment was repaired and validated. Phase A passes completely in
the clone. No original environment, Phase A implementation, trusted Phase A
run, or Phase B source/data file was altered as part of the environment repair.
Only the two command examples in the live source documentation were changed to
prevent the unsafe direct invocation.

## Findings

### 1. Confirmed native-crash mechanism

- Direct `...\ats-stack-research\python.exe` calls reproduced hard termination
  in `numpy.linalg.solve`, `numpy.polyfit`, `numpy.corrcoef`, pandas correlation,
  and Matplotlib rendering.
- NumPy's `_umath_linalg` depends on `libblas.dll` and `liblapack.dll`.
- `liblapack.dll` forwards LAPACK procedures such as `dgesv_` to
  `mkl_rt.3.dll`.
- Outside Conda activation, neither `liblapack.dll` nor `mkl_rt.3.dll` was on
  `PATH`. Under `conda run`, both resolve from the environment's `Library\bin`.
- The previously failing operations then complete normally in the unchanged
  original environment and in the repaired clone.

This is why imports and simple NumPy elementwise operations could pass while a
later linear-algebra or plotting call killed the process.

### 2. Secondary package-manager inconsistency

The cloned state inherited pip/Conda overlap for SciPy 1.17.1 and PyArrow 25.0.0.
Both had Conda records while pip metadata also claimed the distributions. The
clone was repaired by removing the pip-owned files, removing the stale Conda
records, and relinking the pinned Conda packages. `pyarrow-core` also had to be
relinked because it owns the actual PyArrow extension modules.

The repaired imports report `INSTALLER=conda`, and both SciPy and PyArrow pass
binary smoke tests. Conda 25.11.1 still renders them as pip-origin packages in
some `conda list`/export views despite the valid Conda records. For that reason,
the authoritative retained lock is the direct hash-pinned snapshot of all 366
`conda-meta` records, not Conda's pip-interoperability display.

### 3. VectorBT upstream metadata mismatch

The installed VectorBT 1.1.0 Python metadata says `numpy>=2.4.6`, so `pip check`
returns nonzero against NumPy 1.26.4. The Conda package record for the same build
says `numpy>=1.23` and `pandas>=3.0.3,<4`. Conda cannot solve NumPy 2.4.6 into
this Python 3.12 environment because the installed CatBoost line requires
NumPy below 2 and no compatible Python 3.12 NumPy 2.4.6 build is available.

VectorBT 1.1.0 imports and its Numba dependency compiles successfully with the
Conda-solved stack. This is retained as an upstream metadata defect rather than
papered over by editing installed metadata or destabilizing the environment
with broad downgrades. Consequently, `pip check` is expected to report this one
metadata conflict even though the tested import path works.

### 4. Temporary-directory permissions

Pytest initially produced ten setup errors because
`C:\Users\konra\AppData\Local\Temp\pytest-of-konra` was inaccessible. These were
permission errors, not interpreter crashes. A fresh workspace-local
`--basetemp` removed all ten errors. The retained wrapper creates unique local
TEMP, Matplotlib, and Numba cache directories for each invocation.

### 5. Phase B failures are separate from Python health

With a fresh temp root, the complete current suite collected 43 tests: 40
passed and 3 failed without a crash. The remaining failures are:

1. `test_phase_b_contracts.py`: its `security_aliases` fixture omits the current
   required fields `observed_from` and `observed_to`.
2. GPW Phase B reference validation: the retained `security_aliases` Parquet
   schema no longer matches the current live schema contract.
3. U.S. Phase B reference validation: the same retained/live schema mismatch.

These are active Phase B source/test/publication drift. They were documented but
not changed because they are unrelated to the Python native crashes and Phase B
was explicitly in concurrent development.

## Changes made

- Created the clone `ats-stack-research-repaired`; the original environment was
  not modified.
- Reinstalled pinned Conda SciPy 1.17.1, PyArrow 25.0.0, and
  `pyarrow-core` 25.0.0 in the clone after clearing conflicting stale records.
- Replaced unsafe direct-Python examples with `conda run` in:
  - `source/python/README.md`
  - `source/python/PHASE_B.md`
- Added a reusable activated runner and smoke test under
  `RESEARCH/prototypes/environment_repair`.

## Validation results

| Validation | Result |
|---|---:|
| Retained compiled-stack smoke checks | 13/13 passed |
| Phase A tests | 22/22 passed |
| Trusted Phase A archive validation | passed |
| Full current ATS suite | 40/43 passed; 3 Phase B drift failures |
| Native interpreter terminations under activated clone | 0 |

The smoke family covers NumPy solve/SVD/polyfit/correlation; SciPy solve and
Spearman correlation; pandas correlation; scikit-learn regression; Numba JIT;
PyArrow Parquet round-trip; Matplotlib PNG output; PyTorch computation; and
imports of VectorBT, LightGBM, XGBoost, and CatBoost.

Trusted Phase A archive validation returned:

```json
{
  "git_commit_reconstructable": true,
  "manifest_artifacts": 30,
  "panel_rows": 76320,
  "parsed_files": 31,
  "passed": true,
  "sessions": 1272,
  "source_snapshot_valid": true,
  "validation_mode": "archive_integrity"
}
```

## Retained evidence

- `prototypes/environment_repair/invoke_repaired_python.ps1`: safe launcher.
- `prototypes/environment_repair/smoke_test.py`: reproducible smoke test.
- `prototypes/environment_repair/retained_smoke_final/smoke_results.json`: passing
  machine-readable results; SHA-256
  `4992b5aec9909407ae0240904ddfd622da5f37e9a599505a7208f9f839975f2a`.
- `prototypes/environment_repair/repaired_conda_meta_lock.json`: 366 exact Conda
  records and Python distributions; SHA-256
  `ab602cf7974b0785a8c38277b6d556069bac2560d103cdccae124f7e17cdec37`.
- `prototypes/environment_repair/repaired_environment.yml`: Conda export;
  SHA-256 `9fc84aa977fbd929d0b5d44e41b5d0b8d969bd9a856317a315455065b0be3fa5`.
- `prototypes/environment_repair/repaired_environment.json`: Conda export;
  SHA-256 `0cc692650d1de74feef0f17110b287cd36b72eafbe52b51a76a2e64aba7a4390b`.

The normal explicit-URL export was attempted and refused by Conda because its
pip-interoperability view still sees external packages. The direct
`conda-meta` lock above is the complete hash-pinned replacement.

## Commands to use now

For arbitrary Python arguments:

```powershell
& 'D:\Stock\ATS\RESEARCH\prototypes\environment_repair\invoke_repaired_python.ps1' -m ats_research validate --run-dir 'D:\Stock\data\ATS\phase_a\runs\phasea-2a2b3898aba37814'
```

To rerun the retained smoke test:

```powershell
& 'D:\Stock\ATS\RESEARCH\prototypes\environment_repair\invoke_repaired_python.ps1' 'D:\Stock\ATS\RESEARCH\prototypes\environment_repair\smoke_test.py' --output-dir 'D:\Stock\ATS\RESEARCH\prototypes\environment_repair\retained_smoke_rerun'
```

Equivalent direct Conda form:

```powershell
$conda = 'C:\Users\konra\anaconda3\Scripts\conda.exe'
& $conda run -n ats-stack-research-repaired --no-capture-output python <python arguments>
```

Do not return to calling
`C:\Users\konra\anaconda3\envs\ats-stack-research\python.exe` directly for code
that can reach compiled DLLs.
