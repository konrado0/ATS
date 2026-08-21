# Prespecified post–Phase A diagnostic analysis plan

Frozen before new exploratory calculations. This plan reanalyzes the immutable Phase A run `phasea-2a2b3898aba37814`; it does not alter that run, develop a strategy, select securities, optimize parameters, simulate a portfolio, or estimate trading costs.

## Confirmatory reanalysis

The confirmatory family is the 16 Phase A rank-IC tests formed by four registered cross-sectional features (`momentum_12_1__v1`, `realized_volatility_20__v1`, `relative_volume_20__v1`, and `return_5__v1`) and the trusted 3/5/10/20-session labels. WIG trend remains a market-level regime and is never ranked. Session ICs are Spearman correlations. Report distributional summaries, horizon-lag HAC intervals, deterministic moving-block-bootstrap intervals with block length `max(20, horizon)`, all non-overlapping offsets, calendar years, the fixed early/late split at 2023-07-01, a 252-session rolling mean (126-session minimum), and Benjamini–Hochberg adjustment across all 16 tests. The label horizon is the HAC lag because adjacent outcomes overlap for that many market sessions.

Quantile diagnostics preserve Phase A’s five fixed quantiles (`ceil(percentile rank × 5)`). Report every quantile, adjacent differences, top-minus-bottom, linear rank gradient, interior Q2-to-Q4 gradient, calendar-period cells, session counts, and constituent counts. No quantile definition will be changed after viewing results. Quantile outcomes are descriptive diagnostic gross returns, not portfolio returns.

Non-overlapping samples use the full WIG decision-session index and every offset `0..h-1`; missing IC values do not shift the offset schedule. Endpoint sensitivity is limited to dropping the first 20 sessions, dropping the last 20 sessions, and dropping both. No arbitrary breakpoint search is allowed.

## Conditional exploratory family: trend-conditioned pullbacks

Use the registered five-session return rank, split into fixed within-session terciles (bottom/middle/top), and the registered positive versus non-positive WIG 200-session trend regime. Within positive-trend sessions, evaluate gross forward outcomes, a fixed 3×3 momentum-by-short-term-return double sort, and partial rank IC after linearly residualizing both short-term-return rank and forward-return rank on momentum rank within each session. The four positive-trend partial-IC horizon tests form one Benjamini–Hochberg family. Non-positive-regime and calendar-period estimates are descriptive comparators. Cell sizes are mandatory.

## Conditional exploratory family: proximity to trailing high

Primary definition: on the feature-input session immediately before the decision, prior-session close divided by the maximum daily high over the trailing 252 WIG sessions including that prior session and excluding the decision session; all 252 highs must exist. The sole near-high threshold is `ratio >= 0.95`.

Availability sensitivity: repeat incremental association using the same 252-session window but allow at least 240 observed highs, with no forward fill. No other lookback or threshold is examined. Incremental methods are (1) within-session partial rank IC controlling momentum and (2) the standardized proximity coefficient from a within-session cross-sectional rank regression of forward outcome on momentum and proximity. These `2 definitions × 2 methods × 4 horizons = 16` tests form one Benjamini–Hochberg family. A fixed 3×3 momentum-by-proximity double sort uses the strict primary definition. All years, horizons, cells, and null/unfavorable results are retained.

## Label-anchor sensitivity family

Trusted Phase A labels remain unchanged: decision-session close `t` to close `t+h`. Phase A’s decision is at 08:45 before the open and uses inputs from the preceding WIG session. Two alternatives are therefore defensible from daily bars: decision-session open `t` to close `t+h`, and decision-session open `t` to open `t+h`. These prices are observations, not guaranteed fills; exact auction availability and tradeability are unresolved. The 32 alternative-anchor feature/horizon tests form one Benjamini–Hochberg family. Report entry/exit states, actual calendar/session exposure semantics, sample changes, IC, quantile ordering for momentum, and annual stability. Do not select an anchor.

## Coverage, membership, and exit families

The official denominator is always 60. Fixed groups are 60/60 usable, fewer than 60, exactly 57 (the observed minimum and prespecified low-coverage threshold), 58–59, within ±5 WIG sessions of any membership effective date, outside those windows, any active unresolved benign-exit member, and none active. For each of the five benign exits, compare 20 WIG sessions before first exposure, the full official-member exposure, and 20 sessions after last exposure where available. Report price, feature, label, and missing-reason counts alongside IC and quantile summaries. Missing members are never silently removed from the official-universe denominator.

## Statistical and interpretive constraints

- Security-date rows are constituent observations; the time-series sample is the number of session ICs. A dependence-adjusted effective-session diagnostic is `sample variance / HAC variance of the mean`, capped at the observed number of sessions; it is descriptive.
- Cross-sectional dependence is not removed by a large constituent row count. Overlapping labels and market-regime concentration remain limitations.
- HAC and bootstrap intervals are diagnostics, not proof. Normal iid standard errors are not used for overlapping daily ICs.
- Figures are limited to momentum rolling IC, momentum quantile profiles, and price coverage; tables carry their sample sizes.
- Adjustment semantics, unresolved vendor identities, membership timing, and missing exit outcomes are reported as unresolved when the retained evidence cannot settle them.
- Every claim in the report must map to a retained table or validation artifact.
