# Phase A v2 research decision

## Primary recommendation

# CONTINUE TO A BOUNDED STRATEGY TEST

At least one primary hypothesis clears the frozen gate on the pinned GPW
split-adjusted panel. Proximity to the trailing high survives the new price
basis, remains positive on decision-aligned open-to-open labels, agrees across
the max-high and max-close definitions, is present in the common period without
the added 2019-2020 interval, survives the frozen influence checks, has coherent
quintile and momentum-conditional shape, and passes the bounded cost screen.

This is a research permission for one bounded test, not deployable alpha and not
a replacement for Phase B. No portfolio test was run here.

The exact signal authorized for a later bounded Phase C task is:

> At each pre-open decision session, rank official PIT WIG20 plus mWIG40 members
> on `proximity_to_max_high_252 = prior close / max(high)` over the exact 252
> sessions ending on the prior session. Use fixed Q5 versus Q1, a 20-session
> holding/rebalance horizon, every non-overlapping offset, decision-aligned
> open-to-open evaluation, and the established 10 bps commission plus 15 bps
> slippage assumption. Do not optimize the lookback, quantiles, horizon,
> schedule, or costs. Retain `proximity_to_max_close_252` as a predeclared
> semantic corroboration check, not as an alternative selected by performance.

The max-high definition is selected because it was the earlier frozen strict
proximity hypothesis, not because its result is marginally larger. The
max-close result independently corroborates it.

## Frozen design and input validation

The analysis plan was frozen before new results were inspected:

- plan SHA-256: `B5CAB4FA62A1D48E7CBA810CD331B5736191B2C727B021C8D7572E624440A831`;
- config SHA-256: `F083890516FA7E2A62774A09F74863C8102621A08F227C982DDFD2F4FA1D3A94`;
- candidate manifest SHA-256: `E77CE37CB51C3A1E5608B4B2C9B112ABE51635BDAE1CE64DB0B5AA7D4780331A` (matched the pinned expected value);
- 213 manifest/input/artifact hash checks: all `PASS`;
- cited commits `f79c7cf`, `11367f4`, `89f0ba4`, and `9676999`: resolved;
- accepted control manifest SHA-256 values remained
  `ACA68C...AC19` (trusted Phase A), `1A68F0...13A7F` (extended Stooq),
  and `EB1BC8...302FC` (accepted decision analysis).

The new basis is named `split_adjusted_price_return`: split-adjusted
source/native OHLC, no cash distributions, and preserved cash-dividend price
gaps. It is not total return, dividend-neutral return, or a reproduction of the
Stooq basis. Stooq is described only as the accepted Stooq-adjusted or
economic-return-like basis.

All 1,663 evaluation sessions from 2019-12-23 through 2026-08-18 retain exactly
60 official PIT members, including 2019-12-23. Features use only the immediately
prior official session. Labels use exact endpoints with no forward fill. The
open-to-open label is an execution-timing proxy, not proof of auction fillability.
Daily vendor availability before the next pre-open decision remains a
conservative assumption rather than verified vendor latency.

## Main evidence

The following are full-new-panel common-period, open-to-open results. HAC and
bootstrap intervals are for the session statistic; BH correction uses the
frozen primary family.

| Primary hypothesis | 20-session mean IC | Incremental/shape evidence | Frozen inference | 20-session gross screen |
|---|---:|---|---|---|
| Max-high proximity | +0.0768 | partial IC controlling momentum +0.0538; Q5-Q1 +1.4765%; M3 high-minus-low +1.4231% | HAC 95% partial IC [0.0209, 0.0868], bootstrap [0.0209, 0.0856], BH q 0.0020 | all 20 offsets positive; mean turnover 0.652; net at 25 bps +1.3135%; break-even 227 bps |
| Max-close proximity | +0.0721 | partial IC +0.0483; Q5-Q1 +1.3562%; M3 high-minus-low +1.6948% | HAC 95% partial IC [0.0155, 0.0811], bootstrap [0.0159, 0.0819], BH q 0.0045 | all 20 offsets positive; mean turnover 0.672; net +1.1881%; break-even 202 bps |
| 12-1 momentum | +0.0537 | Q5-Q1 +1.0305%; positive quantile-profile Spearman +0.8, but Q4 exceeds Q5 by 0.5495% | HAC 95% IC [0.0191, 0.0882], bootstrap [0.0177, 0.0870], BH q 0.0031 | all 20 offsets positive; turnover 0.442; net +0.9196%; break-even 233 bps |
| Realized volatility | -0.0408 | Q4-minus-Q5 avoidance spread +1.4738%; Q1-Q4 mean exceeds Q5 by 1.1853%; overall profile is non-monotonic | HAC 95% IC [-0.0718, -0.0097], bootstrap [-0.0717, -0.0111], BH q 0.0110 | all 20 offsets positive; turnover 1.389; net +1.1255%; break-even 106 bps |

Proximity is the cleanest gate pass. Both executable definitions agree across
anchors and horizons, and their momentum-controlled results are positive. The
3x3 design is directionally coherent inside the strongest momentum tercile, but
many sessions have cells below five names. The aggregate cells are not tiny;
the sparse-session warnings nevertheless limit confidence in the conditional
selection and are why the later test should use the simpler frozen proximity
quintiles rather than treat the 3x3 cells as a deployable portfolio.

Momentum and volatility also pass the formal direction, uncertainty, influence,
and cost criteria. Their shapes are less clean: momentum repeatedly has Q4 above
Q5, while volatility works principally as an extreme-tail avoidance filter
rather than a monotonic standalone ranking. They are supporting hypotheses, not
the signal selected for the next test.

## Basis, coverage, period, and anchor separation

At 20 sessions on open-to-open labels:

| Feature | Paired Stooq IC | Paired new IC | Full-new IC | Paired basis effect | Recovered-coverage effect |
|---|---:|---:|---:|---:|---:|
| Momentum | +0.0641 | +0.0536 | +0.0537 | -0.0105 | +0.0001 |
| Max-high proximity | +0.0984 | +0.0781 | +0.0768 | -0.0203 | -0.0013 |
| Max-close proximity | +0.0943 | +0.0736 | +0.0721 | -0.0207 | -0.0014 |
| Realized volatility | -0.0538 | -0.0398 | -0.0408 | +0.0140 (weaker negative) | -0.0010 |

The new basis weakens magnitudes but does not reverse any primary conclusion.
Recovered coverage has a much smaller effect than price basis. For 20-session
open labels, max-high feature-rank agreement is 0.981 and mean quintile
reassignment is 14.3%; the mean absolute paired label difference is 0.246%.
Removing the top 1% of paired label differences still leaves the paired
max-high IC change negative but does not reverse the new result.

The added 2019-12-23 to 2020-11-26 interval is stronger than the common period,
but the common period independently remains positive/negative in every expected
direction. For example, max-high open-to-open IC is +0.1135 in the added interval
and +0.0768 in the common interval; momentum is +0.1203 versus +0.0537; volatility
is -0.0657 versus -0.0408. The expanded conclusion is therefore strengthened by,
but not dependent on, the COVID-era addition.

Close-to-close and open-to-open anchors agree directionally at all four
horizons. No anchor was selected by strength.

## Stability and influence

For the 10- and 20-session open labels, every frozen leave-one-full-year-out
result, Dino-window exclusion, top-1%-session exclusion, and leave-one-security
result preserves the expected direction. At 20 sessions:

- max-high leave-year results range from +0.0612 to +0.0935; leave-security
  results range from +0.0708 to +0.0817;
- max-close ranges are +0.0562 to +0.0884 and +0.0663 to +0.0770;
- momentum ranges are +0.0260 to +0.0722 and +0.0486 to +0.0577;
- volatility ranges are -0.0528 to -0.0306 and -0.0456 to -0.0338.

Calendar-year tables remain more uneven than the leave-year results: the partial
2020 common sample is adverse for momentum/proximity, 2022 is near zero or
slightly adverse, and 2024 momentum-controlled proximity is slightly negative.
The signal is therefore not described as uniformly stable.

The Dino window contributes essentially zero old/new label difference (floating
point noise below `2.3e-16`) and its exclusion changes common-period IC by less
than 0.0002. It does not control the decision.

Largest 20-session open-label paired difference contributors for max-high
proximity are Handlowy (`PLBH00000012`), XTB (`PLXTRDM00011`), Pekao
(`PLPEKAO00016`), Dom Development (`PLDMDVL00012`), and Develia
(`PLLCCRP00017`). The largest dates are 2023-06-15, 2023-06-19, 2023-06-16,
2025-06-10, and 2025-06-12. Leave-security and trimmed-difference results show
that none controls the sign.

WIG-regime results preserve direction. At 20 sessions, max-high IC is +0.0885
above the 200-session WIG mean and +0.0307 below it; momentum is +0.0669 and
+0.0018; volatility is -0.0356 and -0.0613. Regime differences are descriptive,
not a new timing rule.

## Coverage and missing-state audit

The common interval contains 85,800 official rows. At a 20-session open label:

- 85,794 prior-session prices are usable;
- feature eligibility is 84,805 for momentum, 84,828 for each proximity
  definition, 85,782 for volatility, 85,783 for relative volume, and 85,794 for
  five-session return;
- 84,550 labels are eligible; 1,200 rows are right-censored at the endpoint,
  42 miss the exact end session, and 8 miss the exact start session;
- the candidate input records eight explicit current-session missing/non-trading
  states in the common period; the established decision feature-input audit has
  six prior-session price-unusable rows.

No prices were synthesized or forward-filled. Missing, documented non-trading,
and right-censored states are separate in the audit supplement.

## Secondary controls

- Strong-stock pullback remains unsupported. Open-to-open deep-minus-nonnegative
  contrasts are small and anchor/horizon sensitive, ending at -0.336% and
  -0.276% at 20 sessions under the two frozen strength conditions.
- Relative volume remains weak/conditional. Open-to-open rank IC rises from
  +0.0050 at three sessions to +0.0230 at 20 sessions, but it is not promoted.

## Changes to accepted conclusions

| Historical conclusion | Phase A v2 conclusion change |
|---|---|
| Momentum was data-confounded | **Strengthens**: now positive on both bases and anchors after split/coverage correction, though Q4-over-Q5 shape remains a caveat. |
| Proximity was promising | **Direction unchanged; magnitude weakens on the new basis; robustness strengthens** because both definitions, both anchors, common period, and influence checks agree. |
| Extreme volatility was a promising filter | **Direction unchanged; magnitude weakens on the new basis; filter case strengthens** through the open-label Q4-Q5 screen. |
| Pullback unsupported | **Unchanged.** |
| Relative volume weak | **Unchanged** despite a modest positive 20-session association. |

These changes do not prove that one vendor is better. Paired differences can
reflect vendor selection, split treatment, cash-dividend treatment, or other
coverage choices.

## Confirmation diagnostics

`COMPLETED`:

- Newey-West/HAC uncertainty;
- deterministic 1,000-sample circular moving-block bootstrap;
- Benjamini-Hochberg correction within the two frozen families;
- all non-overlapping offsets;
- leave-one-full-year-out;
- added-interval exclusion;
- Dino-window exclusion;
- security and session concentration;
- top-1% paired return-difference exclusion;
- bounded 25 bps turnover/cost and break-even screen.

`NOT RUN`:

- exhaustive cash-dividend-gap and source-switch attribution. Producing it would
  require the corporate-action/total-return infrastructure explicitly outside
  this task. Its absence means the residual Stooq/new difference cannot be
  uniquely attributed, so the result remains a bounded research hypothesis.

`INCONCLUSIVE`:

- auction fillability and realized trading costs. Open-to-open labels and the
  turnover proxy are not execution evidence.

The leave-security diagnostic removes each name while retaining the frozen
full-session ranks. This isolates contribution concentration without turning
the confirmation check into a re-ranking framework extension.

## Completion audit

| Mandatory item | Classification |
|---|---|
| Pinned candidate manifest and hashes validated | PASS |
| Accepted historical Phase A controls validated | PASS |
| Accepted Phase A/B/C artifacts unchanged | PASS |
| Exactly 60 official members per evaluation session | PASS |
| Feature and label timing has no leakage | PASS |
| Price-basis semantics explicit | PASS |
| Paired common-period comparison completed | PASS |
| Coverage effect separated from basis effect | PASS |
| Expanded-period effect isolated | PASS |
| Both proximity definitions independently reported | PASS |
| Decision-aligned labels completed | PASS |
| Mandatory hypothesis diagnostics completed | PASS |
| Immutable run reproduced | PASS |
| Configured normal suite, including all four Yahoo tests | PASS (107 configured + 4 targeted adapter tests) |
| Final recommendation follows frozen gate | PASS |

No accepted Phase A/B/C artifact or pinned input was overwritten. Repository
status shows only the scoped Phase A v2 files plus pre-existing unrelated
untracked environment files.

## Immutable artifacts

- Primary run: `D:/Stock/data/ATS/phase_a_v2_research/runs/phase-a-v2-20260827T150000Z`
- Reproduction: `D:/Stock/data/ATS/phase_a_v2_research/runs/phase-a-v2-reproduction-20260827T153000Z`
- Matching main logical hash:
  `1332B211B076B93FDE56085974F0FA65B53F1A103D47BC2C12866E41D1B8A0B7`
- Audit supplement: `D:/Stock/data/ATS/phase_a_v2_research/runs/phase-a-v2-audit-supplement-20260827T160000Z`
- Supplement reproduction:
  `D:/Stock/data/ATS/phase_a_v2_research/runs/phase-a-v2-audit-supplement-reproduction-20260827T160500Z`
- Matching supplement logical hash:
  `060E6B3F9CF3B6FF84C9F100EA76C716BFC091CA1074E16C8A932DCC28864FA9`

Stop here. Do not automatically begin Phase C, broader corporate-action work,
total-return construction, or canonical publication.
