# ATS owner review notebooks

This suite explains the retained ATS system through the Phase D pooled-ML
decision. It is an executable, evidence-guided walkthrough for an owner who
understands software, mathematics, and trading concepts but did not implement
the platform. It does not rebuild or modify any canonical publication.

## Reading order

1. `00_orientation_and_system_map.ipynb` — responsibilities, boundaries, provenance, maintained areas, and implemented/deferred status.
2. `01_data_identity_and_point_in_time.ipynb` — pinned Phase B access, stable identity, official-universe denominator, temporal visibility, and physical layout.
3. `02_research_findings_and_diagnostics.ipynb` — frozen feature/label conventions, bounded real calculations, diagnostic classifications, and confounding.
4. `03_portfolio_ledger_and_end_to_end_flow.ipynb` — Phase C contracts, next-open execution, Decimal accounting, invariants, reproduction, and the actual feature-to-ledger boundary.
5. `04_phase_d_pooled_ml_review.ipynb` — Phase D chronology and pooled-model machinery, model selection, IC/tail/frequency/concentration findings, bounded audit-v2 coverage, and the verified `STOP`.
6. `05_phase_d_no_m_followup.ipynb` — sealed retrospective no-M rank, tail,
   concentration and classification evidence, plus the prospective-monitoring
   boundary; it does not refit models.

The notebooks share vocabulary and should first be read in order. Each repeats its own objectives, paths, retained identities, and imports so it can also execute from a fresh kernel independently.

## Environment

Use the existing repaired research environment through:

`D:\Stock\ATS\RESEARCH\prototypes\environment_repair\invoke_repaired_python.ps1`

The verified kernel is Python 3.12.13 with NumPy 1.26.4, pandas 3.0.5, Polars 1.43.2, PyArrow 25.0.0, DuckDB 1.5.5, Pydantic 2.13.4, nbformat 5.11.1, nbclient 0.11.0, and ipykernel 7.3.0. No package installation is required. The repaired kernelspec supplies the Conda native-library path and directs runtime state to ignored directories under `RESEARCH\.tmp`; notebook 00 verifies NumPy/SciPy delayed native loading from a fresh kernel.

The wrapper does not install the project, but it now supplies `source\python\src` through `PYTHONPATH`. The notebooks also add that path explicitly so their configuration remains visible. To repair a newly recreated or existing kernelspec idempotently, run:

```powershell
& 'D:\Stock\ATS\RESEARCH\environment\repair_jupyter_kernel.ps1'
```

## Expected retained inputs

- repository: `D:\Stock\ATS`; the Phase A/B/C snapshot notebooks retain their
  accepted `00e35d98a49492a7913a1e862117c5ae19757d06` checkpoint, while notebook 04
  pins Phase D by prediction and audit scientific hashes;
- data root: `D:\Stock\data\ATS`;
- Phase A: `phasea-2a2b3898aba37814`;
- extended Phase A: `phasea-9a50dcdb3a4538d7` in `decision_oriented_phase_a\runs\extension-20260820T163347Z`;
- GPW Phase B: `phaseb-f88fc2d38e9811ed1573`;
- U.S. Phase B metadata/profile: `phaseb-5d7086751156ac48cef3`;
- Phase C: `phasec-fa439d650410376aae9e`;
- Phase C reproduction: `phase_c\reproductions\00e35d9\phasec-fa439d650410376aae9e`.
- Phase D2 predictions: `phase_d_ml\prediction_runs\phase-d2-predictions-20260902-v4`.
- Phase D2 evaluation: `phase_d_ml\evaluation_runs\phase-d2-evaluation-20260902-v6`.
- Phase D2 audit: `audit-v2` beneath the accepted primary and reproduction evaluation roots.
- Phase D2-NM follow-up: `phase_d_ml\followup_runs\phase-d2-nm-followup-20260903-v1`.
- Phase D2-NM independent audit: `phase_d_ml\followup_reproductions\phase-d2-nm-followup-20260903-v1-independent`.
- Phase D2-NM repaired prospective registration: `phase_d_ml\prospective_streams\phase-d2-nm-post-freeze-2026-v2`; v1 is preserved and explicitly superseded empty.

Override paths without editing notebooks by setting any of: `ATS_REPO_ROOT`,
`ATS_DATA_ROOT`, `ATS_GPW_MANIFEST`, `ATS_US_MANIFEST`, `ATS_PHASE_A_RUN`,
`ATS_PHASE_A_EXTENDED_RUN`, `ATS_PHASE_C_RUN`, `ATS_PHASE_C_REPRODUCTION`,
`ATS_PHASE_D2_PREDICTION_RUN`, `ATS_PHASE_D2_EVALUATION_RUN`, or
`ATS_PHASE_D2_REPRODUCTION_RUN`.

## Fresh-kernel execution

Execute all six in documented order, with a new kernel for every notebook:

```powershell
& 'D:\Stock\ATS\RESEARCH\prototypes\environment_repair\invoke_repaired_python.ps1' `
  -PythonArgs @('D:\Stock\ATS\source\python\notebooks\execute_notebooks.py')
```

The driver overwrites only the six notebook files with their small executed
outputs and writes `execution_report.json`. It starts a fresh kernel per
notebook, stops at the first error, and does not write beneath `D:\Stock\data`.

To execute one notebook from a fresh kernel, pass its filename:

```powershell
& 'D:\Stock\ATS\RESEARCH\prototypes\environment_repair\invoke_repaired_python.ps1' `
  -PythonArgs @('D:\Stock\ATS\source\python\notebooks\execute_notebooks.py', '01_data_identity_and_point_in_time.ipynb')
```

A subset run writes a name-specific report such as
`execution_report__04_phase_d_pooled_ml_review.json`; it does not overwrite the
accepted report for the earlier complete notebook suite.

Execution is offline. The GPW manifest is validated in notebook 01; the accepted U.S. publication is represented by retained metadata/profile evidence so the walkthrough does not rescan the 30.9-million-row fact table. The review notes record the separate full live validation.

## Evidence discipline

The notebooks keep official denominators and missing states visible, distinguish diagnostic outcomes from executable returns, and mark real-run evidence separately from synthetic fixtures. `ats_features` and `ats_tracking` are absent; their proposed names are not presented as implemented modules. Failures are allowed to surface—cells do not swallow validation or assertion errors.
