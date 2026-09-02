# Phase D2 independent evaluator and bounded audit repair

`evaluate_phase_d2.py` is a bounded independent implementation. It imports no
primary D2 metric functions. It validates sealed file inventories and hashes,
then independently recomputes model-family selection, denominators, session IC
and paired deltas, candidate/idle frequencies, episode anchors, tail separation,
severe outcomes, security and chronological-quartile concentration, and the
mechanical verdict. It reclassifies the remaining stored gate values; it does
not independently recompute every bootstrap, leave-contributor, annual, or
other gate input.

`audit_phase_d2_v2.py` is the frozen, versioned audit repair. It leaves the
accepted prediction and evaluation publications unchanged, validates their
seals, derives execution-integrity checks from retained artifacts, independently
recomputes the negative mean-IC anchors sufficient to retain `STOP`, and adds
largest-session, top-five-session, session-HHI, half-year-block-share, and
block-HHI diagnostics. The accepted v4 run has no literal sequential
label-admission trace, so the audit intentionally reports scientific
`STOP — VERIFIED` and execution integrity `NOT FULLY PROVEN`.

The primary runtime uses separate process commands:

```powershell
& RESEARCH/environment/invoke_ats_python.ps1 -m ats_ml.d2_cli stage1
& RESEARCH/environment/invoke_ats_python.ps1 -m ats_ml.d2_cli stage2a
& RESEARCH/environment/invoke_ats_python.ps1 -m ats_ml.d2_cli stage2b
& RESEARCH/environment/invoke_ats_python.ps1 -m ats_ml.d2_cli stage2c
```

Repeat the same commands with `--reproduction`, then finalize each run only after both complete. Commands print sealed identities, not metrics. Reports are rendered only from already-sealed machine artifacts.
