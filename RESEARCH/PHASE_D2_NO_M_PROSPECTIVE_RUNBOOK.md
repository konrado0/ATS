# Phase D2-NM prospective prediction runbook

This is a manual, prediction-only procedure. There is no daemon, service, or
scheduler. Run it only when a truthfully represented post-freeze session is
available early enough to seal before 08:45 Europe/Warsaw.

## Required pinned package

Create one immutable directory containing:

- `observations.parquet`: official TOP60 rows, exact frozen 18-feature inputs,
  `model_score_eligible`, `model_exclusion_reason`, `information_session`,
  `decision_ts`, and `official_expected_count=60`;
- `training_labels.parquet`: only label rows admitted for the current refit,
  with exact 20-session endpoint timestamps strictly before the refit timestamp;
- `walk_forward_block.json`: one January/July block with the frozen trailing
  36-month final fit and three six-month calibration blocks; and
- `input_config.json`: schema `ats.phase_d2_nm.prospective_input.v1`, SHA-256 for
  each file, refit session, requested decision sessions, and exact target start,
  endpoint, and label-availability timestamps.

Do not update a mutable discovery pointer. A new data publication receives a new
immutable path and hash. Missing or unknown split, identity, membership, source,
or trading state remains excluded with its reason visible.

## Score and seal

From `D:\Stock\ATS`:

```powershell
$atsPython = 'D:\Stock\ATS\RESEARCH\environment\invoke_ats_python.ps1'
& $atsPython 'D:\Stock\ATS\RESEARCH\prototypes\phase_d2_no_m\prospective.py' `
  score-pinned `
  --package-dir 'D:\absolute\immutable\input-package' `
  --output 'D:\absolute\temporary\prediction-batch.parquet'
```

The command refits and scores exactly `RICH_NO_M_LIGHTGBM`, `C_LINEAR`, and
`C_LIGHTGBM`; preserves all 60 official rows and exclusion reasons; emits no
outcomes; records generation and seal timestamps from the host clock rather than
accepting caller-supplied timestamps; and computes prospective eligibility solely
from the recorded seal timestamp. Late finite predictions become monitoring-only
permanently.

Publish the validated batch append-only:

```powershell
& $atsPython 'D:\Stock\ATS\RESEARCH\prototypes\phase_d2_no_m\prospective.py' `
  publish-batch `
  --input 'D:\absolute\temporary\prediction-batch.parquet' `
  --batch-id 'post-freeze-2026-09-04-v1'
```

Never reuse a batch ID. Conflicting semantic duplicates are rejected across all
prior batches.

## Missed session

If the input cannot be represented and sealed by 08:45, do not backfill it:

```powershell
& $atsPython 'D:\Stock\ATS\RESEARCH\prototypes\phase_d2_no_m\prospective.py' `
  record-missed `
  --decision-session '2026-09-04' `
  --reason 'Pinned official input was unavailable before the decision timestamp.'
```

After at least 40 timely decision sessions and maturity of the last exact
20-session outcome, a separately bounded evaluation may report the early
checkpoint. Fewer than 40 sessions is `INSUFFICIENT`. Do not pool this cohort with
the retrospective evidence or alter the frozen procedure.
