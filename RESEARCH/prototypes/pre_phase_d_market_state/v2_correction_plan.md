# Pre-Phase-D market-state diagnostic v2 correction plan

## Status and authority

This correction is frozen on 2026-08-30 before calculating any repaired v2
market-state result. Owner review demonstrated that v1 drifted from the agreed
feature contract and that its documented repository-root test command failed.
That is the only authority for this bounded correction.

V1 remains immutable evidence and its exact source is preserved by Git commit
`797a433dcd5f7fc0c2ce31baae089b64f9dfa62a`. V1's `safe to proceed: YES` and
exact-block acceptance are superseded pending successful v2 primary execution,
reproduction, independent audit, and scoped source commit. The broad v1
interpretation remains a non-controlling observation until v2 is complete.

## Pinned base and v1 evidence

- base analysis plan SHA-256:
  `ec7da3e408dfb7e247163146247ead837e8ad2352c6a70e998ae0d63581fd6d3`;
- base configuration SHA-256:
  `dff1ea399df74d273ed1ec40e9dac56d50b6fd6813db9b26858c2d7f763fbd56`;
- v1 primary manifest SHA-256:
  `3e6453292022f7a14e69eb05ee52c722c1f3ea29923ab2137f934cdd2fde388f`;
- v1 reproduction manifest SHA-256:
  `050610ac0d1ec063a586fb6d61e4d0585bea11494d5603122e540f6fad9a223d`;
- v1 reproduction audit SHA-256:
  `3acf8b98d2fdb8fdae4e488c8b1e9c30a0ad6851c690212d0f85de658deab3cf`.

All v1 input paths, physical hashes, WIG validation, PIT timing, official
denominator, episode selection, proximity/label basis, tercile cut convention,
uncertainty method, materiality thresholds and interpretation limits remain
frozen unless explicitly corrected below.

## Demonstrated definition corrections

1. `top60_return_dispersion_20` becomes the cross-sectional interquartile
   range of usable exact 20-session split-adjusted member log returns:
   `quantile(0.75, method=linear) - quantile(0.25, method=linear)`.
   It is not sample standard deviation.
2. `top60_positive_leadership_share_20` becomes the sum of the five strongest
   positive usable exact 20-session member log returns divided by the sum of all
   positive usable returns. It is not a top-12 share.
3. `wig_volatility_ratio_20_60` becomes
   `std(log_return[-20:], ddof=1) / std(log_return[-60:], ddof=1) - 1`.
   Centering is definition fidelity; it must not change ranks or terciles.

No variable is added, removed, or selected. The optional share-within-5%-of-high
supplement remains outside the block.

## Outcome population correction

Outcome-conditioned descriptive terciles, overall summaries, year summaries,
all 20 offsets and block uncertainty use only decision sessions with at least
one row jointly eligible for unchanged proximity and the exact
`label__open_to_open__20`. State feature publication and feature coverage remain
through 2026-08-18. Right-censored sessions after the final available exact
label remain in the feature table with explicit label-unavailable state but do
not enter outcome-conditioned tercile thresholds or results.

Offset zero remains the zero-based ordinal modulo 20, now within the corrected
ordered outcome-available decision-session population. This is a population
correction, not a schedule search.

## Denominator proof correction

For every TOP60 aggregation, the implementation must publish an
`aggregation_denominator` equal to its usable member count and an explicit
`unavailable_members_in_aggregation` count equal to zero. Share variables also
publish their positive-observation numerator where applicable. The independent
feature gate must calculate, rather than initialize, unavailable-as-negative
violations from those proof fields. Any nonzero proof violation is FAIL.

Breadth-change validity requires independently valid current and lag-10 breadth
values, each formed on its own PIT membership and usable denominator.

## Validation repair

The repository-root documented test command must pass without relying on the
current working directory. Add focused fixtures that exercise:

- IQR and top-five leadership formulas;
- centered WIG volatility ratio;
- exact previous-information-session attachment;
- official denominator 60 and a 45/60 fail-closed boundary;
- one missing member remaining excluded, not becoming a negative breadth or
  leadership observation;
- correlation exact-history/coverage behavior; and
- outcome-population exclusion of right-censored sessions.

The accepted command is frozen as:

`D:/Stock/ATS/RESEARCH/environment/invoke_ats_python.ps1 -m pytest -q D:/Stock/ATS/RESEARCH/prototypes/pre_phase_d_market_state/tests`

executed from `D:/Stock/ATS`.

## Outputs and correction gate

Primary immutable v2 run:
`D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v2`.
Reproduction:
`D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v2-reproduction`.
Independent audit:
`D:/Stock/data/ATS/pre_phase_d_market_state/runs/pre-phase-d-market-state-20260830-v2-reproduction-audit.json`.

The same separate verdicts are issued. `Safe to proceed to Phase D0/D1: YES`
requires all of: WIG PASS, repaired block causality/coverage PASS, v2 block READY
or READY WITH CAVEATS, exact primary/reproduction logical match, all artifact
logical hashes match, focused tests pass from repository root, and the scoped
v2 plan/config/code/tests/report are committed. Until all conditions hold, the
verdict is NO.

No result-dependent change is allowed after this freeze except a new versioned
correction of another demonstrated implementation bug. Do not start Phase D.
