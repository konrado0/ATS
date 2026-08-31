# ATS Research Operating Policy

## Purpose

ATS is a research project first. Data, infrastructure, reproducibility and
execution work exist to support trustworthy research decisions; they are not
objectives by themselves.

> **The burden of proof is reversed: additional infrastructure must justify
> itself through a concrete research need. Research does not need to justify
> itself through additional infrastructure.**

Optimize time-to-decision, not artifact count. The preferred output of a bounded
research task is a credible `CONTINUE`, `STOP`, `DEFER` or `NOT PROVEN` decision.
Additional machinery is worthwhile only when it can materially improve confidence
in that decision or is required by a surviving result.

This policy governs future task design and review. It does not change the meaning
of accepted Phase A/B/C artifacts, supersede retained evidence, or amend a frozen
scientific contract after results have been inspected.

## Decision-proportional rigor

Choose rigor according to the decision being protected, not the sophistication
of the available tools.

| Level | Appropriate use | Minimum retained evidence | Normally deferred |
|---|---|---|---|
| Exploratory | Generate or cheaply reject hypotheses | Named data basis and period, enough code/configuration to understand the calculation, visible caveats, no confirmatory claim | Formal release manifests, exact physical reproduction, production architecture |
| Decision evidence | Authorize or stop a research line, model comparison, bounded strategy test or new engineering work | Frozen question and primary definitions before new outcomes, decision-relevant correctness checks, pinned logical inputs, reproducible decisive outputs, explicit stop/continue gate | Deployment operations and unrelated platform generalization |
| Deployment candidate | Capital allocation, broker/live integration or operational service | Full execution, liquidity, corporate-action, reconciliation, monitoring, rollback and operational guarantees appropriate to the deployment | Nothing required for safe operation may be waived as “research-grade” |

An exploratory result may suggest a confirmatory task, but it may not be described
retrospectively as frozen, out-of-sample or deployment evidence. A result that
changes the roadmap or authorizes significant implementation work is decision
evidence and must cross the corresponding reproducibility boundary.

## Non-negotiable research correctness

“Minimum rigor” never permits a known defect that can plausibly determine the
conclusion. For any affected experiment, preserve as applicable:

- point-in-time identity and membership;
- `available_ts <= decision_ts` and correct execution/label anchors;
- strict feature/label separation and fold-local learned preprocessing;
- the official universe denominator, usable count and missing/non-trading state;
- explicit price/return semantics, including whether splits and cash
  distributions are represented;
- chronological validation when observations or labels overlap through time;
- equivalent logical populations when comparing methods; and
- enough provenance to identify the exact data and code behind the decision.

A bounded imperfection may remain a caveat when there is concrete reason it cannot
materially change the current decision. Uncertainty that could reverse or
invalidate the result must be corrected, tested through a bounded sensitivity, or
made a fail-closed `NOT PROVEN` gate.

## Designing a bounded research task

Before implementation, state:

1. **Decision:** the single primary decision the task is meant to support.
2. **Cheapest credible experiment:** the smallest test capable of making that
   decision or falsifying the hypothesis.
3. **Must-have for validity:** work without which the decision could be wrong.
4. **Useful diagnostics:** bounded checks that clarify interpretation but do not
   open new branches.
5. **Defer:** attractive data, infrastructure, models or validation that cannot
   plausibly change this decision.
6. **Stop/continue rule:** defined before inspecting the controlling result.

Secondary diagnostics are allowed, but they may not silently become additional
primary questions, select a new model or parameter, or create a new phase.

## Research must pull infrastructure

Do not build a new canonical dataset, vendor pipeline, event system, execution
engine, ML platform, feature store, experiment service or generalized abstraction
for hypothetical future use.

Scope expansion normally requires one of:

1. a surviving result that concretely needs the additional capability; or
2. evidence that the missing capability can materially invalidate the current
   experiment.

Otherwise reuse accepted machinery, implement the narrow boundary required by the
experiment, or defer. Approximately matching a simpler model or representation is
failure to justify added complexity.

## Exploration, confirmation and falsification

- Prefer the cheapest prespecified falsification capable of rejecting a hypothesis
  over progressive refinement of a weak result.
- Once a hypothesis becomes interesting enough to influence a decision, freeze
  its primary definition, population, timing, metrics and gate before the next
  confirmatory result.
- Do not respond to weak evidence by searching more parameters, filters, horizons,
  models, vendors or datasets until one works.
- Use hashes, immutable manifests and exact reproduction at meaningful decision
  boundaries. Do not require release-grade ceremony for every scratch notebook or
  disposable diagnostic.
- Preserve negative decision evidence sufficiently to establish what was tested,
  why it failed and which branch was stopped. A failed experiment need not become
  a permanent subsystem.

## Bugs and corrections

A demonstrated bug requires the smallest correction that restores the affected
contract:

1. identify the affected evidence and whether the prior verdict is superseded;
2. preserve the old result when it has already influenced a decision;
3. freeze the bounded correction before inspecting repaired outcomes when the
   correction could change the conclusion;
4. rerun only the checks required to re-establish the decision; and
5. do not reopen unrelated architecture, data acquisition or research questions.

If containment cannot be demonstrated, broaden the audit only as far as needed to
establish it and return any material scope expansion to the owner.

## Research-grade versus deployment-grade

Research-grade data must be sufficiently PIT-correct and semantically explicit
that known limitations cannot plausibly drive the research decision. It may retain
bounded source, volume, corporate-action, coverage or execution caveats.

Deployment-grade work may later require authoritative corporate actions,
total-return economics, empirical liquidity/fillability, broker behavior,
operational monitoring, recovery and stronger reconciliation. Do not impose those
requirements on early hypothesis testing unless their absence already invalidates
the experiment being run.

## Time as evidence

When the unresolved question is genuinely future performance, freeze the surviving
strategy or model and accumulate prospective evidence. Additional historical
optimization is not a substitute for time. Historical segments already involved
in hypothesis development must not be relabeled as untouched validation.

## Application to Phase D

Phase D is one bounded pooled-ML research question, not an ML-platform project.
Phase D0/D1 should therefore:

- reuse ATS identity, PIT, feature, label, manifest and validation machinery;
- add only the minimal `ats_ml` dataset, split, preprocessing, model and evaluation
  boundaries required by the frozen 2x2 comparison;
- classify each proposed feature, diagnostic and component as must-have, useful or
  deferred;
- prove leakage, chronology, denominator, abstention and reproducibility contracts
  on fixtures before real predictive results;
- keep the market-state block numerical context rather than optimize a regime
  filter; and
- stop infrastructure expansion if the rich representation does not materially
  and stably beat the strongest conventional baseline.

The accepted Phase D charter and roadmap define the scientific direction. This
policy controls proportionality and scope; it does not authorize Phase D2 or
change any frozen model, feature or evidence threshold after results are seen.
