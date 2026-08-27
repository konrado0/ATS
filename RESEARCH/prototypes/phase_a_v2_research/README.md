# Phase A v2 research gate

This directory contains the frozen Phase A v2 plan, thin candidate-panel
adapter, bounded audit supplement, tests, and reproducibility records.

The main runner writes only to a new directory beneath
`D:/Stock/data/ATS/phase_a_v2_research/runs`. It validates all pinned inputs,
constructs exact-session features and both label anchors, runs the three frozen
comparison scopes, and refuses to overwrite an existing run.

The audit supplement adds explicit missing/censored-state, denominator,
WIG-regime, and proximity-semantic mapping tables without changing analysis
results.

Published decision: `RESEARCH/PHASE_A_V2_RESEARCH_DECISION.md`.
