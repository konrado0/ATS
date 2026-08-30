# Phase A v2 bounded strategy test

This research-only adapter tests the frozen max-high Q5 portfolio against the
same-eligible-universe benchmark and a Q1 long-only control. It preserves the
accepted Phase A v2 and Phase C artifacts and publishes only immutable research
runs under `D:/Stock/data/ATS/phase_a_v2_strategy_test/runs`.

Use the repaired repository wrapper and an explicit working directory. Exact
commands are retained in the final run.

The accepted execution candidate is `config_v4.json`. Runs v1-v3 are preserved
as superseded evidence. v1 lacked PLAY's cash settlement; v2 misclassified
2020-12-22 as an executable exit session; v3 omitted the last cohort's exact
t+20 liquidation and annualized by resolved rather than elapsed observations.
The v4 overlay changes no signal, schedule, weighting, cost, period,
corporate-action term, or economic-gate parameter.

`audit_run.py` verifies every manifest-declared file, independently reconstructs
each terminal t+20 endpoint and post-endpoint cash path, recomputes the frozen
economic gate using shared elapsed-session duration, fails closed on a
terminal-unresolved sleeve, and compares the primary and clean-reproduction
hashes. It writes its audit outside the immutable run directory.
