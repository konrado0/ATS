# Pre-Phase-D market-state diagnostic

This directory contains the bounded, descriptive pre-Phase-D diagnostic. It
does not implement Phase D, train a model, alter Phase C, or create a
regime-timing strategy.

V1 inputs and semantics are in `analysis_plan.md`, `config.json`, and
`plan_freeze.json`. The accepted correction is frozen in `v2_correction_plan.md`,
`config_v2.json`, and `plan_freeze_v2.json`. Each plan/config pair was hashed
before its corresponding market-state results were calculated.
`run_diagnostic.py` validates the pinned WIG source, computes the
fixed numerical block, reads the accepted v4 composite NAV without rerunning the
strategy, attributes the predefined episodes, and publishes immutable tables.
`audit_reproduction.py` compares the primary and clean reproduction.

Use the retained wrapper from repository root `D:\Stock\ATS`:

```powershell
& 'D:\Stock\ATS\RESEARCH\environment\invoke_ats_python.ps1' -m pytest -q 'D:\Stock\ATS\RESEARCH\prototypes\pre_phase_d_market_state\tests'
& 'D:\Stock\ATS\RESEARCH\environment\invoke_ats_python.ps1' 'D:\Stock\ATS\RESEARCH\prototypes\pre_phase_d_market_state\run_diagnostic.py' --config 'D:\Stock\ATS\RESEARCH\prototypes\pre_phase_d_market_state\config_v2.json'
& 'D:\Stock\ATS\RESEARCH\environment\invoke_ats_python.ps1' 'D:\Stock\ATS\RESEARCH\prototypes\pre_phase_d_market_state\run_diagnostic.py' --config 'D:\Stock\ATS\RESEARCH\prototypes\pre_phase_d_market_state\config_v2.json' --reproduction
& 'D:\Stock\ATS\RESEARCH\environment\invoke_ats_python.ps1' 'D:\Stock\ATS\RESEARCH\prototypes\pre_phase_d_market_state\audit_reproduction.py'
```

V1 is preserved and superseded for exact feature-block acceptance. The repaired
candidate is `pre-phase-d-market-state-20260830-v2`. Run directories are
immutable and the runner refuses to overwrite them.
