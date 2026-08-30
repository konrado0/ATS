# Phase A v2 bounded strategy test

This research-only adapter tests the frozen max-high Q5 portfolio against the
same-eligible-universe benchmark and a Q1 long-only control. It preserves the
accepted Phase A v2 and Phase C artifacts and publishes only immutable research
runs under `D:/Stock/data/ATS/phase_a_v2_strategy_test/runs`.

Use the repaired repository wrapper and an explicit working directory. Exact
commands are retained in the final run.

The accepted execution candidate is `config_v3.json`. Runs v1 and v2 are
preserved but their expanded-period results are rejected: v1 lacked PLAY's
cash settlement, and v2 misclassified 2020-12-22 as an executable exit session
despite the pinned candidate having no native open. The v3 overlay changes no
signal, schedule, weighting, cost, period, or economic-gate parameter.

`audit_run.py` verifies every manifest-declared file, independently recomputes
the frozen economic gate, fails closed on a terminal-unresolved sleeve, and
compares the primary and clean-reproduction hashes. It writes its audit outside
the immutable run directory.
