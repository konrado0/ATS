# Phase C: deterministic daily portfolio ledger

Phase C is an accounting and execution simulator. It consumes frozen external
target-weight intents; it does not calculate signals, select a strategy, or turn
its outputs into evidence of alpha. Close-to-close Phase A labels are diagnostic
only and are not executable-return targets.

## Task 0 gate and workstreams

The pre-implementation gate was run on commit
`94a0e6e0792937a4b6ec8dc69c66fca85908a877` with the repaired research
environment (Python 3.12.13). The existing suite collected 47 tests and passed
47/47. Phase A archive validation passed with 30 artifacts, 76,320 panel rows,
and 1,272 sessions. The pinned GPW manifest validated with 147,687 bars; the
pinned U.S. manifest validated with 30,937,812 bars. GPW reconciliation passed
with exact bar semantic-key and numeric hashes, membership and identity hashes,
and preserved denominator/usable counts.

The workstreams and dependencies are:

1. freeze portfolio contracts, numeric policy, event order, timing, and action
   interaction policy;
2. implement the engine against those contracts;
3. independently construct hand-calculated golden fixtures and state-transition
   tests against the frozen written policy;
4. add immutable run publication, independent validation, and reconciliation;
5. run a bounded pinned-GPW integration only after synthetic ledgers pass;
6. perform an adversarial audit, commit only Phase C scope, then publish and
   reproduce a final run from that clean commit.

The modified `source/python/README.md`, all existing `RESEARCH` work, Phase A
runs, and Phase B publications are outside Phase C's write scope.

## Frozen contracts and identities

Portfolio contracts live in `ats_contracts.portfolio` and use Pydantic models
with `extra="forbid"`, immutable instances, exact schema-version literals, and
explicit enums. Decimal values serialize as decimal strings. IDs are stable
caller IDs for inputs and SHA-256-derived deterministic IDs for outputs. An
output semantic key is `(run_id, sequence)` and sequences are strictly increasing.
Duplicate input IDs, duplicate intent semantic keys, duplicate event revisions,
unknown schemas/enums/security IDs, mutable discovery pointers, and unpinned or
hash-mismatched manifests fail closed.

Each intent carries its batch, identity, decision/availability/eligibility,
currency, source version, pinned manifest, denominator, usable and eligible
counts, exclusions, reason, and provenance. Counts must satisfy
`0 <= eligible <= usable <= official`; inline exclusions contain exactly
`official - eligible` distinct official-member states. V1 deliberately rejects
exclusion-artifact references until a retained path-and-hash contract exists.
Batch metadata and target weights must agree, and the nonnegative batch weights
may sum to at most one. The engine never silently renormalizes them. V1 also
rejects multiple batches resolving to the same execution session; callers must
combine them explicitly. Omitting a held security does not imply liquidation—an
explicit zero-weight intent is required.

## Numeric and rounding policy

Cash, fees, quantities, prices, weights, notionals, and corporate-action terms
use Python `Decimal` constructed from decimal text, never binary-float text
round-trips. Input scale is unrestricted within finite Decimal values. Persisted
cash, fee, notional, and valuation amounts are rounded half-even to 0.000001
account-currency units; quantities to 0.000000000001 shares; prices to
0.00000001; and weights/rates to 0.000000000001. Calculations use precision 38
and round only at the documented ledger boundary. The complete-valuation
reconciliation tolerance is 0.000001 currency units. Canonical float64 bar
prices are converted with `Decimal(str(value))`; tests bound the resulting
ledger reconciliation at the same tolerance.

## Session event order and market-field timing

For each ordered market session the engine performs:

1. record beginning state;
2. at the modeled exchange open, apply eligible known corporate/security events;
3. reveal only that session's `open` field;
4. select eligible intent batches and translate targets to orders;
5. execute sells before buys, then record fills, costs, cash, and position moves;
6. at the modeled bar-completion event, reveal `high`, `low`, `close`, and volume
   (only close is used by Phase C valuation);
7. value positions, enforce invariants, and emit the end-of-session snapshot.

Before the open event none of the session's OHLCV is visible. At open, only the
open is visible. A fill records the canonical source row, `price_field=open`,
the modeled market-open timestamp, calendar, source adjustment state/version,
and the field-availability policy. The completed daily bar's Phase B
`available_ts` is not reinterpreted as open availability. Close-derived
information requires `information_available_ts <= decision_ts < eligible_open`;
same-close fills are impossible. Later revisions are usable only after their own
availability and never leak backward.

## Target translation, costs, and cash feasibility

Execution equity is shared cash plus every held quantity times a valid execution
mark. The current session open is preferred. If a held security has no open, the
most recent already-revealed close may be used only when the configured stale
policy permits its age and provenance. If any holding has no admissible execution
mark, the entire batch is deferred because target quantities cannot be defined.

For each batch, desired quantity is `execution_equity * target_weight / raw_open`.
Unavailable new targets are rejected and their weight remains cash. An existing
position without an open cannot trade and retains its shares; its target is
deferred. Available target deltas are sorted by security ID. Sells execute first.
The buy cash requirement includes adverse slippage and commission. When it
exceeds cash after sells, all buys in that batch are reduced by one common
deterministic scale. The scale is the largest value on the persisted
0.000000000001 weight grid whose per-order rounded notionals and commissions sum
to no more than available cash; the shortfall is explicit. Negative cash is an
unconditional invariant failure and is never clamped or adjusted outside the
cash-movement ledger. No short, borrowing, or negative-cash configuration is
accepted. Tiny residual cash remains explicit.

Default commission is 10 bps of absolute fill notional. Default slippage is 15
bps applied to raw open (higher for buys, lower for sells). Commission and
slippage are separate fill fields. A fill emits a signed trade cash movement of
`-(quantity * fill_price)` and a separate negative commission movement; their
sum is `-(quantity * fill_price) - commission` and reconciles to the fill exactly.

## Missing data and valuation

Execution prices are never zero-filled or forward-filled. Missing opens produce
rejected/deferred records, not fills. At close, a current close is preferred. A
prior revealed close is allowed only under an explicit maximum stale-session age;
each stale valuation records its source timestamp, session age, price source, and
reason. Without an admissible mark, each affected position is listed as
unvalued, portfolio status is `unresolved`, and market value/equity are null.
Quantity and cash conservation still apply. A complete valuation satisfies
`cash + marked position value = equity` within the declared tolerance.

Official denominator, usable/eligible counts, exclusions, rejected/deferred
weight, and unallocated weight remain ledger-visible. A 57/60 batch is never
recast as a 57-member universe.

## Corporate and security events

Stable `security_id` owns the position; ticker/identifier changes update metadata
without moving it. Suspensions block fills until a known resumption. Delisting
marks an instrument terminal; absent explicit cash or conversion terms, retained
shares are unvalued rather than assigned zero. A split changes quantity by its
ratio. A merger removes source shares and adds `source_quantity * ratio` successor
shares. A cash takeover removes source shares and adds
`source_quantity * cash_amount` cash. Each change has an explicit application
and independently reconcilable position/cash movements.

Only the highest revision available by the event's modeled processing timestamp
is eligible. A correction already available before effectiveness replaces the
earlier revision on replay. A correction learned after application emits
`replay_required` and is not retroactively or doubly applied in that run.

`raw_with_explicit_actions` accepts only raw bars for securities receiving
actions. `adjusted_without_actions` accepts adjusted or vendor-unverified bars
but prohibits explicit economic actions. Any ambiguous adjusted-bar plus action
combination fails closed; Phase C never infers actions from price discontinuities.

## Run and validation policy

Runs publish through a staging directory to immutable `runs/<run_id>`. Identity
pins exact Phase B manifest bytes/hash, normalized configuration, exact intent
and event bytes/hashes, contract versions, implementation commit/file hashes,
environment lock, numeric/timing/action policies, calendar, costs, and seed.
Every ledger artifact is listed with byte and logical hashes. Validation ignores
stored success claims: it re-hashes inputs and artifacts, parses every row through
the contracts, checks sequence/set coherence, timing, quantities, cash equations,
independently rebuilds execution equity and target-to-order translation (including
sell proceeds, requested quantities, the common buy scale, and generated quantities),
complete/incomplete valuations, and manifest provenance. Reconciliation is
trade-by-trade and session-by-session. Existing completed runs are never edited
or overwritten.

Generated ending equity is only an accounting checksum. Phase C reports no
Sharpe ratio, alpha, optimized parameter, or investment conclusion.

## Reference fixture and commands

`configs/phase_c_reference.yaml` pins only
`phaseb-f88fc2d38e9811ed1573` and bounds the ledger to 2020-11-27 through
2020-12-11. Its immutable external intent file has three batches. The first
retains the actual 57/60 state (CIECH, LOTOS, and PGNiG unavailable) and includes
an unavailable LOTOS target as an explicitly unsupported-pullback negative
control. Later batches rebalance two available identities and explicitly exit
them. Momentum, proximity-to-high, and extreme-volatility labels are metadata
only: data-confounded or unconfirmed research conditions, never Phase C rules.

Use the repaired wrapper with `PYTHONPATH=source/python/src`:

```powershell
& D:\Stock\ATS\RESEARCH\prototypes\environment_repair\invoke_repaired_python.ps1 `
  -m ats_portfolio run --config D:\Stock\ATS\source\python\configs\phase_c_reference.yaml
& D:\Stock\ATS\RESEARCH\prototypes\environment_repair\invoke_repaired_python.ps1 `
  -m ats_portfolio validate --run-dir D:\Stock\data\ATS\phase_c\runs\<run_id>
& D:\Stock\ATS\RESEARCH\prototypes\environment_repair\invoke_repaired_python.ps1 `
  -m ats_portfolio reconcile --run-dir D:\Stock\data\ATS\phase_c\runs\<run_id>
```

`run --output-root <directory>` creates a same-identity reproduction beneath a
separate root. Equality is defined by run identity plus every ledger logical
hash; wall-clock creation timestamps and physical manifest bytes are not logical
ledger output. Existing run directories are never overwritten.

## Deliberate Phase C limits

The reference engine has one account currency and no FX conversion, borrowing,
margin, shorts, integer lots, intraday execution, broker interface, optimizer,
strategy selection, or packaged-engine adapter. Explicit dividends, rights, and
spinoffs are also deferred: unknown action enums fail rather than applying
partial economics. Security-event state is visible through rejection reasons and
position snapshots; later corrections require replay. Phase D and live trading
remain out of scope.

## Stage 1 candidate audit

The fresh pre-commit audit collected 78 tests: all 47 pre-Phase-C tests and 31
Phase C contract/golden/state/property tests passed. Phase A archive validation,
both pinned Phase B manifests, and exact GPW reconciliation passed again. Dirty
candidate `phasec-5a1773781a6dbbdea398` validated 16 artifacts, 60 events, five
canonical-source-checked fills, 11 canonical-source-checked valuation rows, and
11 sessions. Its five trades and all sessions reconciled with hash
`bd5c184c33a69bba43eb9d0c7e2a5380d5b8a39d67a2929c0ad3c49662c906bd`;
a separate candidate reproduction had the same run ID and all ten ledger logical
hashes. Ending equity `1007072.062997` is an accounting checksum only.

An independent adversarial review identified and prompted fixes for held-currency
mixing, exclusion-evidence bypass, ambiguous same-session batches, canonical
fill/valuation source checks, valuation arithmetic and stale age, action/event
revision validation, action timing, fill currency, and session-date provenance.
The follow-up focused suite passed after those remediations. An isolated copied
candidate with one undeclared artifact failed validation with an artifact-set
mismatch.

| Requirement | Stage 1 status | Evidence or remaining gate |
|---|---|---|
| Preserve pre-Phase-C behavior | PASS | 47/47 baseline tests still included in 78/78 full pass |
| Validate Phase A archive | PASS | 30 artifacts, 76,320 panel rows, archive-integrity mode |
| Validate pinned GPW and U.S. manifests | PASS | 147,687 GPW bars; 30,937,812 U.S. bars |
| Reconcile GPW to trusted Phase A | PASS | exact semantic-key/numeric/membership/identity hashes |
| Versioned neutral contracts and fail-closed inputs | PASS | `test_phase_c_contracts.py`; `ats_contracts.portfolio` |
| Next-open causality and field timing | PASS | golden timing case; every candidate fill causality flag true |
| Costs, fractional translation, cash feasibility | PASS | hand-calculated trade CSV and property tests |
| Missing/stale/unresolved valuation semantics | PASS | hand-calculated state CSV; complete/unresolved tests |
| 57/60 denominator and exclusions | PASS | golden 57/60 test plus pinned real negative control |
| Corporate/security state transitions and revisions | PASS | 15 state-transition tests and independent validator replay |
| Adjustment/action ambiguity | PASS | both ambiguous modes reject in tests |
| Immutable run, artifact validation, and tamper detection | PASS | 16-artifact candidate; undeclared-file audit rejected |
| Pinned real GPW reconciliation | PASS | five trades, 11 sessions, canonical bars/marks re-read |
| Deterministic candidate reproduction | PASS | same candidate run ID and ten ledger logical hashes |
| Clean scoped implementation commit | PENDING FINAL PUBLICATION | candidate intentionally records dirty provenance |
| Final run from exact clean commit and clean reproduction | PENDING FINAL PUBLICATION | performed only after this candidate is committed |

No Stage 1 item other than the two intentionally deferred clean-publication gates
is FAIL or NOT PROVEN.

## Stage 2 repair audit

A subsequent review invalidated the original completion verdict. It reproduced a
one-money-quantum overspend after proportional buy scaling: the old engine
tolerated `-0.000001` and silently replaced it with zero outside the cash ledger.
It also showed that artifact integrity alone did not prove the semantic
target-to-order translation. The earlier retained run is immutable but
superseded as completion evidence.

The repair removes the clamp and selects the largest affordable common buy scale
on the persisted weight grid after quantity, notional, and commission rounding.
The exact `690176.600000` cash / `82935.90000000` open / `0.998228` target case is
a regression test. Thirty generated cash/price/weight cases now run through the
independent validator, not only engine-local assertions.

Validation now independently reconstructs each real-data order from its retained
intent, pre-order cash and positions, pinned canonical session open, cost model,
and numeric policy. It verifies execution equity, current and requested quantity,
target weight, side, sell proceeds, the common cash scale, generated quantity,
and the exact expected order set. The reviewer’s in-memory rewrite to target
weight `0.999`, execution equity `1`, and requested quantity `999` is an explicit
negative regression.

The repaired audit passed 33/33 focused Phase C tests and 80/80 full tests. The
Phase A archive revalidated with 30 artifacts and 76,320 panel rows; pinned GPW
and U.S. manifests revalidated with 147,687 and 30,937,812 bars; exact GPW
reconciliation passed again. Applying the new validator to the prior retained
real ledger independently reconstructed all five orders and checked all five fill
sources and eleven valuation sources. Final immutable publication and a separate
same-hash reproduction follow from the exact documentation-complete commit.
