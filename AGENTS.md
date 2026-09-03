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
6. the prespecified stop/continue rule; and
7. the evidence level: exploratory, retrospective robustness, prospective
   confirmation, or trading/deployment candidate.

Exploration and iterative hypothesis development are allowed. Evidence must be
tagged according to how the hypothesis, representation, model and thresholds were
selected. Reused historical evidence can guide a research-direction decision but
must not be relabeled as untouched or prospective. Require cleaner evidence as the
claim approaches capital allocation or deployment; do not impose deployment-grade
or pristine prospective standards on a bounded exploratory question.

Research must pull infrastructure. Challenge any proposed pipeline, data work,
framework, abstraction or validation step that has no plausible path to changing
the current decision. Prefer accepted ATS contracts and narrow adapters over new
general systems.

Minimum rigor still requires any decision-relevant PIT timing, leakage,
denominator/missing-state, price-basis and accounting semantics. A bounded known
imperfection may remain a caveat only when it cannot plausibly determine the
result; otherwise correct it, test a bounded sensitivity, or fail closed.

Do not optimize a frozen test after viewing its results, conduct an unbounded
search until something works, convert a secondary diagnostic into a confirmatory
claim, or ask an execution task to solve hypothetical future needs. A diagnostic
may motivate one explicitly selected, newly frozen bounded hypothesis; record that
selection history and downgrade the evidentiary claim appropriately. If work
expands materially beyond its original decision, stop and return the scope
expansion to the owner.

Preserve accepted evidence and unrelated dirty work. Bugs receive the smallest
contained correction; negative results are retained as decisions, not grown into
permanent subsystems.

Topic branches are temporary workspaces, not the final home of completed evidence.
When scoped work is correct, accurately qualified and its required checks pass,
integrate it into local `master` before declaring the task complete; owner review
gates follow-on action, not retention of finished knowledge. Prefer fast-forward
integration and revalidate the integrated state. If integration is unsafe or the
owner explicitly asked to keep the branch separate, report repository integration
as `INCOMPLETE` with the exact blocker and next command. Push only when publication
is explicitly authorized, and always report local/remote synchronization state.
