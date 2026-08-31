# Phase D0 v2 feature registry — owner-review table

**Contract:** `phase-d0-20260831-v2`

**Authoritative source:** `source/python/configs/phase_d0_feature_registry.json`

**Authoritative registry SHA-256:** `733bacb9c1132d98eacb4a190cfb3cd96b0163207af46f3745002206b3705ef6`

This is a concise presentation view of the frozen 30-feature registry. The JSON registry controls if this table and the machine-readable artifact ever differ. The table changes no feature, formula, eligibility rule, model input, or Phase D authorization.

## Shared notation and eligibility

- `d` is the 08:45 decision session; `i` is the immediately preceding official WIG information session. Every feature has lag 1.
- `c/o/h/l/v` are split-adjusted stock close/open/high/low/volume; `W` is validated WIG close; `r` and `Rw` are stock and WIG log returns.
- Windows are exact official-session windows. A missing, unusable, nonpositive, or source-treatment-unresolved required price makes only the dependent feature null; no fill or shortened window is allowed.
- Volume additionally must be finite, positive, and explicitly comparable. X/M TOP60 aggregates require at least 45 usable members and retain `n/60`; unavailable members are never counted as negatives.
- Origin: **A-v2** = accepted Phase A v2 formula; **D0** = frozen D0 formula requiring narrow D1 implementation; **X** = deterministic same-session transform; **MS-v2** = accepted corrected pre-Phase-D v2 market-state implementation.

## C — conventional stock state (6)

| Feature | Frozen formula | Exact window / minimum | Range | Origin |
|---|---|---:|---:|---|
| `proximity_to_max_high_252` | `c[i] / max(h[i-251..i])` | 252 / 252 close+high | `(0,1]` | A-v2 |
| `proximity_to_max_close_252` | `c[i] / max(c[i-251..i])` | 252 / 252 closes | `(0,1]` | A-v2 |
| `momentum_12_1` | `c[i-21] / c[i-252] - 1` | 253 / exact 232-close measurement span | `(-1,+inf)` | A-v2 |
| `return_5` | `c[i] / c[i-5] - 1` | 6 / 6 closes | `(-1,+inf)` | A-v2 |
| `realized_volatility_20` | sample SD of 20 simple returns ending at `i` | 21 / 21 closes, 20 returns | `[0,+inf)` | A-v2 |
| `relative_volume_20` | `v[i] / mean(v[i-19..i]) - 1` | 20 / 20 comparable volumes | `(-1,+inf)` | A-v2 |

## P — stock path and evolution (8)

| Feature | Frozen formula | Exact window / minimum | Range | Origin |
|---|---|---:|---:|---|
| `stock_log_return_20` | `ln(c[i] / c[i-20])` | 21 / 21 closes | `(-inf,+inf)` | D0 |
| `stock_log_return_60` | `ln(c[i] / c[i-60])` | 61 / 61 closes | `(-inf,+inf)` | D0 |
| `stock_path_efficiency_20` | `abs(sum(r)) / sum(abs(r))`; 0 if denominator is 0 | 21 / 21 closes, 20 returns | `[0,1]` | D0 |
| `stock_positive_return_share_20` | `count(r>0) / 20`; zero is not positive | 21 / 21 closes, 20 returns | `[0,1]` | D0 |
| `stock_drawdown_depth_60` | `c[i] / max(c[i-59..i]) - 1` | 60 / 60 closes | `[-1,0]` | D0 |
| `stock_recovery_from_low_60` | `c[i] / min(c[i-59..i]) - 1` | 60 / 60 closes | `[0,+inf)` | D0 |
| `stock_volatility_ratio_20_60` | `sample_sd(r20) / sample_sd(r60) - 1` | 61 / 61 closes, 60 returns | `[-1,+inf)` | D0 |
| `stock_close_location_value_20` | `(c[i]-min(l20)) / (max(h20)-min(l20))` | 20 / 20 valid OHLC; positive range | `[0,1]` | D0 |

## X — stock-relative cross-sectional context (4)

All X values use average-tie percentile ranks among feature-eligible official members on the decision session. They are null below 45 eligible members and retain the official denominator.

| Feature | Frozen formula | Base window / cross-section minimum | Range | Origin |
|---|---|---:|---:|---|
| `xrank_momentum_12_1` | `xrank(momentum_12_1)` | 253 / 45 of 60 | `[1/n,1]` | X |
| `xrank_proximity_to_max_high_252` | `xrank(proximity_to_max_high_252)` | 252 / 45 of 60 | `[1/n,1]` | X |
| `xrank_realized_volatility_20` | `xrank(realized_volatility_20)` | 21 / 45 of 60 | `[1/n,1]` | X |
| `xrank_relative_volume_20` | `xrank(relative_volume_20)` | 20 / 45 of 60 | `[1/n,1]` | X |

## M — frozen market state (12)

| Feature | Frozen formula | Exact window / minimum | Range | Origin |
|---|---|---:|---:|---|
| `wig_log_return_20` | `ln(W[i]) - ln(W[i-20])` | 21 / 21 WIG closes | `(-inf,+inf)` | MS-v2 |
| `wig_log_return_60` | `ln(W[i]) - ln(W[i-60])` | 61 / 61 WIG closes | `(-inf,+inf)` | MS-v2 |
| `wig_trend_200` | `W[i] / mean(W[i-199..i]) - 1` | 200 / 200 WIG closes | `(-1,+inf)` | MS-v2 |
| `wig_trend_acceleration_20_60` | `wig_log_return_20/20 - wig_log_return_60/60` | 61 / both returns valid | `(-inf,+inf)` | MS-v2 |
| `wig_drawdown_252` | `W[i] / max(W[i-251..i]) - 1` | 252 / 252 WIG closes | `[-1,0]` | MS-v2 |
| `wig_downside_semivolatility_20` | `sqrt(mean(min(Rw,0)^2)) * sqrt(252)` | 21 / 21 closes, 20 returns | `[0,+inf)` | MS-v2 |
| `wig_volatility_ratio_20_60` | `sample_sd(Rw20) / sample_sd(Rw60) - 1` | 61 / 61 closes, 60 returns | `[-1,+inf)` | MS-v2 |
| `top60_breadth_positive_60` | usable members with positive 60-session log return / usable members | 61 / at least 45 of 60 | `[0,1]` | MS-v2 |
| `top60_breadth_change_10` | current breadth minus breadth 10 official sessions earlier | 71 / both breadth values valid, each 45 of 60 | `[-1,1]` | MS-v2 |
| `top60_return_dispersion_20` | linear Q75 minus linear Q25 of usable 20-session member log returns | 21 / at least 45 of 60 | `[0,+inf)` | MS-v2 |
| `top60_average_pairwise_correlation_60` | mean upper triangle of complete-vector Pearson correlations | 61 / at least 45 nonzero-variance vectors | `[-1,1]` | MS-v2 |
| `top60_positive_leadership_share_20` | five largest positive member returns / all positive member returns | 21 / at least 45 of 60; positive sum > 0 | `(0,1]` | MS-v2 |

## Block and model-use summary

| Block | Count | Primary use |
|---|---:|---|
| C | 6 | Both conventional cells and both rich cells |
| P | 8 before frozen label-blind D1 duplicate resolution | Rich cells only |
| X | 4 | Rich cells only |
| M | 12, complete corrected v2 block | Rich cells only; also the fixed C+P+X versus C+P+X+M LightGBM ablation |
| **Total** | **30 before permitted P resolution** | Positive model-input allowlist; identity, lineage, raw price/volume, and missingness indicators are excluded |
