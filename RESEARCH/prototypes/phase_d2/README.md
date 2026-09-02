# Phase D2 independent evaluator

`evaluate_phase_d2.py` is a bounded independent implementation. It imports no primary D2 metric functions. It validates sealed file inventories and hashes, then independently recomputes model-family selection, denominators, session IC and paired deltas, candidate/idle frequencies, episode anchors, tail separation, severe outcomes, concentration, gate classifications, and the mechanical verdict.

The primary runtime uses separate process commands:

```powershell
& RESEARCH/environment/invoke_ats_python.ps1 -m ats_ml.d2_cli stage1
& RESEARCH/environment/invoke_ats_python.ps1 -m ats_ml.d2_cli stage2a
& RESEARCH/environment/invoke_ats_python.ps1 -m ats_ml.d2_cli stage2b
& RESEARCH/environment/invoke_ats_python.ps1 -m ats_ml.d2_cli stage2c
```

Repeat the same commands with `--reproduction`, then finalize each run only after both complete. Commands print sealed identities, not metrics. Reports are rendered only from already-sealed machine artifacts.

