# ATS Agent Instructions

Read [`README.md`](README.md) and
[`RESEARCH/RESEARCH_OPERATING_POLICY.md`](RESEARCH/RESEARCH_OPERATING_POLICY.md)
before designing or executing an ATS research task. Then read the controlling
phase contract/report for the area being changed.

For every new bounded research task, identify before implementation:

1. the exact decision being made;
2. the cheapest experiment capable of making it credibly;
3. must-have validity work;
4. useful but non-gating diagnostics;
5. deferred infrastructure/data/model work; and
6. the prespecified stop/continue rule.

Research must pull infrastructure. Challenge any proposed pipeline, data work,
framework, abstraction or validation step that has no plausible path to changing
the current decision. Prefer accepted ATS contracts and narrow adapters over new
general systems.

Minimum rigor still requires any decision-relevant PIT timing, leakage,
denominator/missing-state, price-basis and accounting semantics. A bounded known
imperfection may remain a caveat only when it cannot plausibly determine the
result; otherwise correct it, test a bounded sensitivity, or fail closed.

Do not optimize after viewing results, convert secondary diagnostics into new
research branches, or ask an execution task to solve hypothetical future needs.
If work expands materially beyond its original decision, stop and return the
scope expansion to the owner.

Preserve accepted evidence and unrelated dirty work. Bugs receive the smallest
contained correction; negative results are retained as decisions, not grown into
permanent subsystems.
