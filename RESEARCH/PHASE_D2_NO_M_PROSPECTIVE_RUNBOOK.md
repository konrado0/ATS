# Phase D2-NM prospective prediction runbook — repaired v2

This is a manual, prediction-only procedure. There is no daemon, service, or
scheduler. Stream v1 is preserved as a non-operational, superseded empty
registration. All new work uses `phase-d2-nm-post-freeze-2026-v2`.

## Required immutable input package

Create one versioned directory containing these files and bind every SHA-256 in
`input_config.json` (schema `ats.phase_d2_nm.prospective_input.v2`):

- `observations.parquet`: exactly 60 unique official identities per decision
  session, with the frozen feature columns, `model_exclusion_reason`, preceding
  `information_session`, exact 08:45 Europe/Warsaw `decision_ts`, and
  `official_expected_count=60`;
- `training_labels.parquet`: only block-admitted labels with the exact
  20-session endpoint strictly before the refit timestamp;
- `walk_forward_block.json`: the frozen January/July block, trailing 36-month
  final fit, and three six-month calibration blocks;
- `pit_membership.parquet`: the independently pinned point-in-time membership
  artifact with exactly 60 unique official identities for every requested
  decision session; and
- `official_calendar.parquet`: the ordered, unique official session calendar,
  extending through every frozen 20-session target endpoint.

The config lists the requested sessions and target records. Each target record
must bind the preceding official information session, decision session, exact
08:45 decision timestamp, same-session target start, twentieth subsequent
official-session endpoint, and its 09:00 Europe/Warsaw availability timestamp.
Missing, extra, duplicate, or wrong identities fail closed regardless of any
declared count.

## Score, then publish

From `D:\Stock\ATS`:

```powershell
$atsPython = 'D:\Stock\ATS\RESEARCH\environment\invoke_ats_python.ps1'
& $atsPython 'D:\Stock\ATS\RESEARCH\prototypes\phase_d2_no_m\prospective.py' `
  score-pinned `
  --package-dir 'D:\absolute\immutable\input-package-v2' `
  --output-dir 'D:\absolute\immutable\score-package-v2'
```

The scorer fits exactly `RICH_NO_M_LIGHTGBM`, `C_LINEAR`, and `C_LIGHTGBM` and
atomically finalizes a directory containing `predictions.parquet`,
`scorer_audit.json`, and `manifest.json`. It emits no outcomes, publication
timestamp, eligibility, or monitoring claim.

```powershell
& $atsPython 'D:\Stock\ATS\RESEARCH\prototypes\phase_d2_no_m\prospective.py' `
  publish-batch `
  --score-package 'D:\absolute\immutable\score-package-v2' `
  --batch-id 'post-freeze-2026-09-04-v2'
```

The publisher re-verifies the scorer sidecar and manifest, every pinned input
hash, both contract bindings, accepted feature allowlists and model definitions,
the exact PIT TOP60 identity sets across all cells, and all calendar/timing
semantics. It writes into a temporary sibling directory and atomically finalizes
the batch. Only then does it record `publication_completed_ts` in a separately
immutable receipt bound to the finalized batch manifest. This post-finalization
timestamp is the sole eligibility authority. A completion after 08:45 makes the
session permanently monitoring-only, even if scoring began earlier. Never reuse
a batch ID; semantic duplicates are rejected across prior batches.

## Missed session

If the package cannot be published by 08:45, do not backfill it:

```powershell
& $atsPython 'D:\Stock\ATS\RESEARCH\prototypes\phase_d2_no_m\prospective.py' `
  record-missed `
  --decision-session '2026-09-04' `
  --reason 'Pinned official input was unavailable before the decision timestamp.'
```

After at least 40 timely decision sessions and maturity of the last exact
20-session outcome, a separately bounded evaluation may report the early
checkpoint. Fewer than 40 sessions is `INSUFFICIENT`. Do not pool this cohort
with retrospective evidence or alter the frozen procedure.

## Repository-manifest verification

The evidence manifest declares Git blob bytes as authoritative. Verify the
containing commit without checking out or line-ending conversion:

```powershell
& $atsPython 'D:\Stock\ATS\RESEARCH\prototypes\phase_d2_no_m\validate_manifest.py' `
  --root 'D:\Stock\ATS' --commit HEAD
```

Checkout-byte verification is diagnostic and must be requested explicitly with
`--working-tree`; on Windows it may differ because of CRLF conversion.
