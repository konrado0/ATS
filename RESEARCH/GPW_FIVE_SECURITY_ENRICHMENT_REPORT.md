# GPW five-security enrichment — Phase A research checkpoint

Date: 2026-08-24

Scope: Phase A evidence only; no Phase B publication and no Phase C modification

Comparison window: 2020-11-27 through 2026-08-18 (2020 is partial)

Warm-up start: 2019-01-01

Official TOP60 denominator: 60 on every evaluation session

## Decision summary

1. **Are the histories sufficiently trustworthy?** **Yes for identity, session availability, raw displayed OHLC, and most non-distribution daily moves; not yet proven homogeneous with Stooq for return-based research.** Three owner-supplied 2014+ controls map Investing.com one-for-one to Stooq sessions and almost exactly on stable-scale daily returns. They also show persistent price-ratio steps at distribution events and reciprocal historical-volume scaling in Stooq. The five missing histories remain byte-pinned and internally valid, but have no same-identity Stooq overlap from which to recover their adjustment factors. Treating their raw/display returns as interchangeable with backward-adjusted Stooq can create ex-distribution artifacts.
2. **What does TOP60 coverage look like?** The post-start vendor-history limitation is eliminated. Old price coverage averaged 58.6266/60 and ranged 57–60; enriched coverage averages 59.9944/60 and ranges 59–60. Full 60/60 sessions rise from 630 to 1,422 of 1,430. The remaining eight 59/60 sessions are explicitly classified as non-tradeable suspension periods for LOTOS and PGNiG, not vendor gaps.
3. **Did the missing histories materially bias the previous findings?** **No numerical reversal in the completed sensitivity run, but the causal claim is now provisional.** The recovered observations materially improve denominators and cause 2.0%–2.6% of otherwise-comparable existing-member quintile assignments to move, predominantly near quantile boundaries. Overall mean rank-IC changes remain small. However, the run mixes raw/display Investing returns with backward-adjusted Stooq returns at distribution events, so it is evidence about coverage sensitivity, not a fully normalized vendor-replacement result.
4. **Should this later become the next canonical GPW Phase B version?** **No as-is; yes only after price-basis remediation.** Phase B must either adjust the five histories from authoritative corporate-action evidence into the pinned Stooq basis or retain a separate raw-price basis and exclude cross-basis return/volume features. Manual-copy provenance, rounded-volume uncertainty, visible missing sessions, and normal stage/validate/atomic publication remain additional conditions.

## Baseline and boundary record

- Git start HEAD: `ad1bbe4e4b926fe847ec6f6d334b27993a0adacf`.
- Git implementation commit: `0b3d7f89ad742a807c5efdfd06308acb6e8b0fae`.
- Accepted Phase A run: `D:\Stock\data\ATS\phase_a\runs\phasea-2a2b3898aba37814`; archive validation passed with 30 manifest artifacts, 76,320 panel rows, and 1,272 sessions.
- Identical-date old comparison baseline: `D:\Stock\data\ATS\decision_oriented_phase_a\runs\extension-20260820T163347Z`, run ID `phasea-9a50dcdb3a4538d7`, 85,800 rows and 1,430 sessions through 2026-08-18.
- Accepted diagnostic comparison evidence: `D:\Stock\data\ATS\decision_oriented_phase_a\analysis_runs\decision-20260820T164218Z`.
- Enriched Phase A run: `D:\Stock\data\ATS\phase_a\runs\phasea-7a3066ed3da2b075`; manifest SHA-256 `CD573A6004498733D3C37E66574CA4F2BA4E98A6AEC51270ED3382778AF3A6B5`.
- Compact comparison evidence: `D:\Stock\data\ATS\five_security_enrichment\runs\enrichment-phasea-7a3066ed3da2b075-v3`; manifest SHA-256 `3F291F450169482BE44B783693CB118628751891EBECE8347C8DC7B56F148171`.
- 2014+ vendor-overlap controls: `D:\Stock\data\ATS\five_security_enrichment\vendor_overlap_runs\investing-stooq-controls-2014-v2`; manifest SHA-256 `AE532BF8D0ADF49A18D709880AF609F9152A248E5E7C95B95B0D6C3CD4FCFC14`. The contract hard-excludes every pre-2014 Stooq row and compares only exact same-identity sessions through the shared endpoint.
- The fixed evaluation start, warm-up, end, PIT membership, official denominator, feature/label definitions, horizons, timing rules, quantiles, and inference settings are identical between the selected old baseline and the enrichment.

The pre-existing modified `source/python/README.md` and untracked environment-export material were recorded at task start and were not included in the scoped implementation commit. No raw or generated history was staged in Git.

## Raw archive and provenance

The original bytes are archived under:

`D:\Stock\data\raw\investing_com\gpw\daily\manual_page_copy_2026-08-24\`

Archive provenance files:

- `SOURCE.md`
- `source_manifest.json` — SHA-256 `9E67102F5141DE383A391DB4AA1AD9D91ADA47302135998379DABEA1798C16E2`

The authenticated Investing.com download feature was not used. Acquisition method is `manual_copy_paste_from_displayed_web_table`. Exact acquisition time, page URLs, and vendor instrument IDs are `unknown`. File-to-ISIN mappings were supplied externally by the owner and then checked against the existing stable ATS identities, official membership, observed price ranges, and exit evidence. The five exact convenience files were removed from the Stooq tree only after archived byte length and SHA-256 matched; no replacement is represented as Stooq.

At the owner's request, byte-identical copies of all five archives now also reside under `D:\Stock\data\reference\investing.com\` beside the three controls. `reference_manifest.json` (SHA-256 `73362602C0F603FFF7CBA9CDFE384448EC066CE67020D051B3143FC3A27805CE`) records roles, byte lengths, hashes, identities, and authoritative raw paths. The raw archive above remains authoritative.

| Security | ISIN | Stable `security_id` | Rows | Observed range | Bytes | SHA-256 |
|---|---|---|---:|---|---:|---|
| LOTOS | PLLOTOS00025 | bd52f489-c099-53f7-bf4f-c0a8522ab691 | 2,143 | 2014-01-02–2022-07-28 | 109,089 | CE4BEEDC0EB6329B16AC1913443E7DEC2C03235BA85E24A9674DF30A46C35AD3 |
| PGNiG | PLPGNIG00014 | 0a091b66-5a77-5e09-a77f-3f8ee3495374 | 2,207 | 2014-01-03–2022-10-28 | 99,394 | D743EBB9EB77EF4D35F6C6201B8FD0FAF0A541217E9C2ADD9B3FB832CBC1CAA6 |
| CIECH | PLCIECH00018 | ff9065f8-dd14-5c1a-a82c-6ca53812d287 | 2,459 | 2014-01-09–2023-11-06 | 123,330 | AF41D016AAB896CFCDC01E149B43B2719883716965377865C0CE6F0A90D963D2 |
| STS Holding | PLSTSHL00012 | 5e6e6cb6-c8ca-5f5f-afec-094eec3f3786 | 452 | 2021-12-16–2023-10-04 | 22,743 | 9DD03EC93468E288B117E480ED690D9970BC8E3CEBBAB7175BF19605163C93B0 |
| TIM | PLTIM0000016 | 05d3c2df-e256-5452-94e0-6a4be766041a | 2,535 | 2014-01-07–2024-03-01 | 120,704 | 18D05ECCCDE44E8949F5F09EA4DA4D1293EDFA46EF27272B4A395D463B936121 |

## Format and parser validation

All files are strict UTF-8/ASCII-compatible CRLF text. After empty display-layout lines, each has the vertical header `Data`, `Ostatnio`, `Otwarcie`, `Max.`, `Min.`, `Wol.`, `Zmiana%`, followed by seven-field tab-separated observations in reverse chronological order.

The narrow parser `investing_com_manual_tsv_v1`:

- accepts only `DD.MM.YYYY`, decimal-comma OHLC, and observed `K`/`M` volume suffixes;
- sorts observations chronologically;
- rejects duplicate dates, malformed fields, unsupported volume suffixes, nonpositive prices, negative volumes, and OHLC violations;
- excludes `Zmiana%` from canonical OHLCV and uses it only as a consistency diagnostic;
- retains raw path, SHA-256, Investing.com source, manual-copy flag, rounded-volume flag and uncertainty, acquisition date, unknown URL/instrument ID, and `vendor_adjusted_semantics_unverified`;
- uses established modeled GPW `event_ts` and `available_ts` for historical fields while keeping the 2026 acquisition date separate;
- selects one whole bar per security/session with explicit Investing.com supplemental priority and never splices fields across vendors.

Observed validation results:

- all five files: zero duplicate dates, malformed rows, or OHLC violations; expected first/last file dates match;
- all five contain both `K` and `M` volume forms;
- LOTOS, CIECH, TIM: maximum `Zmiana%` consistency error is 0.005 percentage point; STS maximum is 0.0657 percentage point;
- PGNiG: 15 rows exceed 0.15 percentage-point error, maximum 0.2602 percentage point. Price continuity contains no >25% jump, so the discrepancy is consistent with the redundant display percentage and rounded two-decimal prices; it is retained as a caveat, not used to modify OHLC;
- TIM: one >25% close change, +28.33% on 2023-03-27. OHLC is internally consistent and the move is an isolated market gap, not sufficient evidence of a split or adjustment defect;
- zero same-identity overlaps still exist for the five recovered securities because they have no validated Stooq or Bossa histories. The three new controls provide indirect evidence about how the same Investing.com representation maps to Stooq; they do not manufacture overlap for LOTOS, PGNiG, CIECH, STS, or TIM.

The displayed volumes are central rounded quantities, not exact shares. Two-decimal `K` implies approximately ±5 shares; two-decimal `M` implies approximately ±5,000 shares. Unsupported suffixes fail closed.

The enriched immutable run retains `adjustment_state = vendor_adjusted_semantics_unverified`, because that was the truthful state at construction and no immutable artifact was rewritten. The new controls refine the interpretation to `likely_raw_display_prices_versus_stooq_backward_adjusted; missing-security_factor_unresolved`. No series was transformed to resemble Stooq.

## Investing.com to Stooq mapping controls — 2014 onward only

The control contract uses no Stooq observation before `2014-01-01`. ORLEN and mBank comparisons begin on `2014-01-02`; KGHM begins on its first copied observation, `2014-01-24`. All comparisons stop at the shared Stooq endpoint, `2026-08-18`; later Investing rows are retained in the source files but excluded from overlap metrics.

Identity mapping is high-confidence and validity-aware: ORLEN `PLPKN0000018 → PKN`, KGHM `PLKGHM000017 → KGH`, and mBank `PLBRE0000012 → MBK`, with the earlier BRE name preserved as the same ISIN. The parser kept one ORLEN displayed volume on 2020-06-01 explicitly missing and accepted mBank's Polish dot thousands separator only through opt-in comparison flags; default production parsing remains fail-closed.

| Control | Shared sessions | Investing-only | Stooq-only | Raw close ratio first → last | Persistent scale steps | Stable-scale return Pearson | Stable pairs within 0.05 pp |
|---|---:|---:|---:|---:|---:|---:|---:|
| ORLEN | 3,156 | 0 | 0 | 1.80050 → 1.00000 | 13 | 0.9999994 | 100.000% |
| KGHM | 3,141 | 0 | 0 | 1.17660 → 1.00000 | 8 | 0.9999954 | 99.968% |
| mBank | 3,156 | 0 | 0 | 1.04687 → 1.00000 | 2 | 0.9999975 | 99.936% |

The evidence supports four bounded findings:

1. **Identity and calendar mapping pass.** Every Investing observation inside each shared span has the same Stooq session; there are no source-only dates in either direction.
2. **Stable-scale OHLC returns map almost exactly after display rounding.** Median absolute close-return differences are 0.00035, 0.00049, and 0.00000 percentage point for ORLEN, KGHM, and mBank. The apparent full-sample outliers are concentrated on price-ratio step dates.
3. **Raw price levels are not interchangeable.** Persistent Investing/Stooq ratios decline toward 1.0 over time. Checked steps line up with ex-sessions immediately before official dividend record dates: ORLEN changes on 2023-08-09 before its 2023-08-10 record date, KGHM changes on 2024-06-27 before its 2024-06-28 record date, and mBank changes on 2018-05-23 before its 2018-05-24 record date. This is strong evidence—still explicitly an inference—that Investing supplies raw/display history while the local Stooq archive backward-adjusts historical prices for cash distributions. [ORLEN official report](https://raportzintegrowany2022.orlen.pl/en/financial-results/explanatory-notes/14-explanatory-notes/14-9-equity/14-9-6-proposal-for-distribution-of-the-parent-company-s-profit-for-2022-and-the-dividend-payment-in-2023/), [KGHM AGM resolution](https://kghm.com/sites/default/files/2024-06/Resolutions_AGM_7.06.2024_1.pdf), [mBank investor relations](https://www.mbank.pl/en/investor-relations/shares/).
4. **Volume is scaled reciprocally in Stooq and rounded in Investing.** The median product of the close-price ratio and volume ratio is 1.000001 for ORLEN, 1.000002 for KGHM, and 1.000009 for mBank. Thus Stooq's historical volume is not the same unit-level observation as the displayed Investing volume even when turnover is approximately preserved. These columns must not be spliced.

There are 31 close-ratio moves above 0.5% across the three controls: 23 persistent steps and eight transient one-session dislocations. The transient cases reinforce the need to keep immutable vendor evidence and never infer a corporate action from price behavior alone.

### Implication for the five-security enrichment

The controls substantially improve confidence that the five files refer to the intended GPW session structure and that ordinary daily moves are represented consistently with Stooq after accounting for a scale factor. They also disprove the stronger assumption that the files can be dropped into the Stooq-adjusted panel unchanged.

For LOTOS, PGNiG, CIECH, STS, and TIM, the time-varying factor cannot be estimated from a same-identity overlap. Until authoritative dividends, splits, rights issues, mergers, and other adjustment inputs are assembled and independently reconciled, these histories should be used as raw price-availability evidence. The completed Phase A comparison remains a useful coverage sensitivity, but return, momentum, volatility, proximity, and relative-volume observations involving the five names are not yet normalized to the surrounding Stooq basis.

## Session completeness and terminal boundaries

Relative to WIG sessions within each observed range:

- LOTOS, PGNiG, CIECH, and STS have no internal missing WIG sessions after their first observation.
- [STS debuted on 2021-12-10](https://stsholding.pl/sts-holding-s-a-cena-ostateczna-w-ofercie-publicznej-zostala-ustalona-na-23zl-za-akcje/), but the file begins 2021-12-16. Four WIG sessions between debut and first observation are absent. Those are genuine post-listing source gaps, not `not_yet_listed`; pre-2021-12-10 remains `not_yet_listed`. The gap predates STS TOP60 membership and does not create a TOP60 price gap, but it contributes to limited post-listing warm-up.
- TIM omits seven isolated WIG sessions within the 2014–2024 observed range: 2014-01-14, 2014-07-10, 2014-07-23, 2014-10-21, 2015-12-03, 2016-03-08, and 2017-03-27. Every gap is one session long. Given TIM's thin trading and the prohibition on synthesized flat bars, they remain explicit no-observation sessions; they are outside the evaluation window.

The histories agree with the existing ATS last-trade boundaries:

| Security | Last observation | Boundary finding | Post-trade event remains outside this task |
|---|---|---|---|
| LOTOS | 2022-07-28 | Confirms high-confidence last trade | ORLEN merger; 1.075 ORLEN shares per LOTOS share |
| PGNiG | 2022-10-28 | Confirms high-confidence last trade | ORLEN merger; 0.0925 ORLEN shares per PGNiG share |
| STS Holding | 2023-10-04 | Confirms existing last-trade evidence | PLN 24.80 takeover/compulsory settlement evidence |
| CIECH | 2023-11-06 | Confirms existing last-trade evidence | PLN 54.25 compulsory settlement evidence |
| TIM | 2024-03-01 | Supports the previously medium-confidence date; source agreement raises confidence but is not independent exchange proof | PLN 50.69 compulsory settlement evidence |

No merger conversion, takeover settlement, post-delisting value, suspension bar, or synthetic observation was created.

## TOP60 price coverage

Comparison uses identical dates and official membership rows.

| Metric | Old | Enriched | Change |
|---|---:|---:|---:|
| Sessions | 1,430 | 1,430 | 0 |
| Official denominator | 60 | 60 | 0 |
| Mean priced members | 58.6266 | 59.9944 | +1.3678 |
| Minimum priced members | 57 | 59 | +2 |
| Vendor-gap member-sessions | 1,964 | 0 | -1,964 |
| Unresolved vendor identities | 5 | 0 | -5 |
| Sessions at 57/60 | 455 | 0 | -455 |
| Sessions at 58/60 | 254 | 0 | -254 |
| Sessions at 59/60 | 91 | 8 | -83 |
| Sessions at 60/60 | 630 | 1,422 | +792 |

Annual price coverage:

| Period | Old mean/min | Enriched mean/min | Interpretation |
|---|---:|---:|---|
| 2020 partial | 57.000/57 | 60.000/60 | LOTOS, PGNiG, CIECH restored |
| 2021 | 57.000/57 | 60.000/60 | LOTOS, PGNiG, CIECH restored |
| 2022 | 57.275/57 | 59.968/59 | Recovered names; eight legitimate LOTOS/PGNiG suspension member-sessions remain |
| 2023 | 58.260/58 | 60.000/60 | STS, CIECH, TIM episode coverage restored as applicable |
| 2024 | 59.896/59 | 60.000/60 | TIM history restored for its final TOP60 episode |
| 2025 | 60.000/60 | 60.000/60 | Unchanged |
| 2026 partial | 60.000/60 | 60.000/60 | Unchanged |

The eight remaining price exclusions are exactly:

- LOTOS: 2022-07-29, 2022-08-01, 2022-08-02, 2022-08-03;
- PGNiG: 2022-10-31, 2022-11-02, 2022-11-03, 2022-11-04.

All are `suspended_non_tradeable`. There are no remaining evaluation-window vendor gaps or unresolved identities.

## Feature-specific eligibility

Price coverage and feature eligibility remain separate. Mean/min eligible member counts change as follows:

| Feature | Old mean/min | Enriched mean/min | Change in mean |
|---|---:|---:|---:|
| 252-session 12–1 momentum | 57.9979 / 55 | 59.3210 / 57 | +1.3231 |
| 20-session realized volatility | 58.6182 / 57 | 59.9860 / 59 | +1.3678 |
| 20-session relative volume | 58.6189 / 57 | 59.9867 / 59 | +1.3678 |
| 5-session return | 58.6266 / 57 | 59.9944 / 59 | +1.3678 |

LOTOS, PGNiG, CIECH, and TIM all have non-null 252-session features at the 2020-11-27 accepted start (TIM is not then an official member but has sufficient history). Their complete official membership episodes are long-lookback eligible except the legitimate LOTOS/PGNiG suspension dates.

STS has no prelisting warm-up. It is price-usable for all 239 TOP60 member sessions, but its 252-session momentum is `insufficient_lookback` for 64 sessions from 2022-09-19 through 2022-12-19 and first becomes eligible on 2022-12-20; it is eligible for 175 member sessions.

Other long-lookback limitations remain visible and are unrelated to the five-file correction: ZABKA 244 sessions, ALLEGRO 220, GRUPRACUJ 123, PEPCO 108, HUUUGE-S144 106, DIAG 97, and BIOMEDLUB 1. Consequently, long-lookback coverage does not reach 60 on every date even though vendor price coverage is essentially complete.

## Diagnostic comparison

The numbers below are unchanged outputs from the immutable enrichment run. In light of the control mapping, they are interpreted as a **coverage sensitivity under mixed price bases**, not as a validated adjusted-price replacement. Small aggregate changes do not prove that individual ex-distribution feature/label rows are comparable.

### Overall rank IC

Mean rank IC old → enriched:

| Feature | 3 sessions | 5 sessions | 10 sessions | 20 sessions |
|---|---:|---:|---:|---:|
| Momentum 12–1 | 0.03365 → 0.03374 | 0.03926 → 0.03903 | 0.05018 → 0.04958 | 0.06202 → 0.06173 |
| Return 5 | 0.00067 → 0.00050 | -0.00101 → -0.00141 | -0.00536 → -0.00509 | 0.00671 → 0.00492 |
| Realized volatility 20 | -0.01967 → -0.02040 | -0.02106 → -0.02151 | -0.02973 → -0.03000 | -0.05395 → -0.05441 |
| Relative volume 20 | 0.00940 → 0.00887 | 0.01146 → 0.01147 | 0.01855 → 0.01920 | 0.03052 → 0.03031 |
| Strict 252-session proximity | 0.04781 → 0.04708 | 0.05470 → 0.05355 | 0.06912 → 0.06727 | 0.09330 → 0.09105 |

Median IC, annual IC, WIG-regime IC, quantile returns, top-minus-bottom spreads, and monotonicity are retained in `diagnostic_comparison.csv`. The largest full-year change in annual mean registered-feature IC is -0.00964 for 20-session momentum in 2021 (0.00955 to -0.00009); larger changes occur only in partial 2020. Temporal instability therefore remains important even though overall estimates are stable.

Momentum's overall Q4-minus-Q5 diagnostic gross-return hump persists after coverage repair and changes only modestly:

| Horizon | Old Q4-Q5 | Enriched Q4-Q5 |
|---|---:|---:|
| 3 | 0.1549% | 0.1744% |
| 5 | 0.2611% | 0.2923% |
| 10 | 0.4713% | 0.5280% |
| 20 | 0.9453% | 0.9545% |

This rejects the narrow hypothesis that the five missing histories created that hump. It does not remove calendar instability: the contrast remains negative in 2024 and partial 2026 for all four horizons.

The prespecified strong-momentum deep-pullback-minus-nonnegative contrast remains negative at every horizon: enriched values are -0.155%, -0.197%, -0.225%, and -0.670% for 3/5/10/20 sessions. The prior “pullback not supported” conclusion is unchanged.

### Rank and quantile sensitivity

Adding recovered names necessarily changes normalized cross-sectional ranks even when the ordering of old members is unchanged.

| Feature | Existing observations | Mean absolute percentile-rank change | Existing quintile changes | Change rate |
|---|---:|---:|---:|---:|
| Momentum | 82,937 | 0.00412 | 1,798 | 2.17% |
| Return 5 | 83,836 | 0.00479 | 2,184 | 2.61% |
| Realized volatility | 83,824 | 0.00493 | 1,688 | 2.01% |
| Relative volume | 83,825 | 0.00472 | 2,129 | 2.54% |
| Proximity 252 | 82,933 | 0.00448 | 2,136 | 2.58% |

Between 87.7% and 93.7% of changed quintile assignments were already within one old-member rank step of a quintile boundary. No new fixed selection rule or top-N boundary was introduced.

### Rounded-volume sensitivity

Excluding all five recovered names from the enriched relative-volume IC reproduces the old-name-only result. Full enriched versus recovered-names-excluded mean rank IC differs by:

- -0.000524 at 3 sessions;
- +0.000008 at 5 sessions;
- +0.000657 at 10 sessions;
- -0.000213 at 20 sessions.

The rounded volumes therefore do not materially change the prior `WEAK` relative-volume conclusion. This check does not make the rounded volume exact or suitable for execution/accounting.

## Principal conclusion classification

| Prior conclusion | Enriched classification | Reason |
|---|---|---|
| Momentum: `DATA-CONFOUNDED` | **Still data-confounded; normalization now an explicit blocker** | The coverage sensitivity barely changes overall IC, but raw Investing ex-distribution returns are not homogeneous with Stooq-adjusted returns. Calendar/year instability also remains. |
| Strong-stock pullback: `NOT SUPPORTED` | **Numerically unchanged, provisional under mixed basis** | Prespecified contrasts remain negative, but the five recovered series require normalized rerun before treating this as a clean vendor-replacement result. |
| Strict proximity-to-high: `PROMISING` | **Provisional; mixed price levels can distort the feature** | The numerical sensitivity is small, but proximity is level/path dependent and the control factors vary through time. |
| Relative volume: `WEAK` | **Still weak; cross-vendor volume is non-comparable as stored** | Aggregate exclusion sensitivity is small, but Stooq reciprocally scales volume while Investing is display-rounded. |
| Volatility: `PROMISING` as conditioning/risk | **Provisional; distribution events need normalization** | Most stable-scale returns map closely, but raw ex-distribution drops can inflate realized-volatility windows. |

Overall classification: **MIXED and provisional; no numerical reversal, but homogeneous adjusted-price comparability is NOT PROVEN**.

## Recommendation for later Phase B publication

**NO AS-IS. CONDITIONAL YES AFTER PRICE-BASIS REMEDIATION:**

1. Owner review must explicitly accept the manual page-copy acquisition method and confirm the intended storage/use basis for Investing.com-displayed data.
2. Before publication into a Stooq-adjusted panel, independently assemble authoritative corporate actions for each of the five securities and reproduce a pinned adjustment factor, or publish a separate raw-price basis that is excluded from homogeneous Stooq return/volume features. The control-derived factor must not be copied across identities.
3. Phase B must retain source `investing_com_manual_history`, original raw hashes, archive manifest, manual-copy flag, source URL/instrument ID as `unknown`, display-rounded volume uncertainty, and the actual price-basis state. No row may be labeled Stooq or assigned a Stooq adjustment version merely because a transformed value resembles Stooq.
4. The four STS post-listing/pre-first-observation gaps and seven isolated TIM sessions must remain explicit missing/no-trade observations; no flat or synthetic bars may be created.
5. The PGNiG redundant-percentage discrepancies and TIM 2023-03-27 price gap must remain quality evidence. No “correction” is authorized without stronger source evidence.
6. The canonical schema must represent rounded-volume uncertainty truthfully. Investing and Stooq volumes must not be spliced; if a valid adjustment cannot be reproduced, volume features for these rows remain excluded or separately qualified.
7. Merger conversion, takeover cash settlement, and post-delisting valuation must remain separate corporate-event work. This enrichment restores pre-exit bars only.
8. A new Phase B version may be staged only after adjusted-versus-raw semantics, focused tests, full suite, GPW reconciliation, source/identity validation, artifact hashing, and atomic-publication validation pass. No existing version or pointer may be overwritten, and no catalog pointer may advance until the owner separately approves publication.

## Verification and handoff

- Baseline focused Phase A archive tests: **2 passed**.
- Baseline complete Python suite: **80 passed**.
- Focused Investing.com parser/identity tests before controls: **8 passed**.
- Focused parser tests after explicit missing-volume and Polish-thousands control handling: **10 passed**; default fail-closed behavior is tested.
- Post-control implementation complete Python suite: **90 passed**.
- Enriched run strict validation: **PASS** — 33 manifest artifacts, 85,800 panel rows, 1,430 sessions, valid source snapshot, reconstructable Git commit.
- Enriched run reproduction: **PASS** — run ID, configuration, environment lock, metrics, logical artifact hashes, and manifest logical hash all match.
- Compact comparison manifest: **PASS** — every retained file's byte length and SHA-256 match its manifest.
- 2014+ overlap-control contract: **PASS** — no pre-2014 Stooq row was used; 9,453 exact shared sessions and zero session disagreements across the three bounded spans.
- Overlap-control scale interpretation: **PASS WITH CAVEATS** — stable-scale returns map almost exactly and checked persistent steps align with dividend timing; eight transient ratio dislocations remain visible, so no automatic corporate-action inference is authorized.
- Five-security adjusted-price equivalence: **NOT PROVEN** — no same-identity Stooq overlap exists and no authoritative adjustment factor has yet been built.
- Accepted Phase A archive after enrichment: **PASS** — unchanged trusted run validates with 30 artifacts, 76,320 rows, and 1,272 sessions.
- Phase B pointer remains `phaseb-f88fc2d38e9811ed1573`; pointer SHA-256 `F23D14C63A53419C942855380906573E27475E19F6A43FA40041FC6915057013` and timestamp remain from 2026-08-20.
- Accepted Phase C run manifest remains `phasec-fa439d650410376aae9e`; SHA-256 `81B9B301E86A0BDB28304C2F05AF55A1AD0160C352EDC8178651A16CF4B7B21A` and timestamp remain from 2026-08-21.
- No Phase B version was published, no catalog pointer was advanced, and no Phase C run/code/contract was created or modified.

Final checkpoint:

- Investing.com provenance: **PASS WITH CAVEATS**
- Investing.com parsing, identity, and session mapping: **PASS WITH CAVEATS**
- Investing-to-Stooq adjusted-price equivalence for the five histories: **NOT PROVEN**
- 2020-11-27 onward TOP60 price coverage: **PASS WITH CAVEATS**
- Homogeneous cross-vendor return/volume features: **NOT PROVEN**
- Previous Phase A conclusions: **MIXED AND PROVISIONAL**
- Recommend canonical Phase B publication: **NO AS-IS; CONDITIONAL YES AFTER PRICE-BASIS REMEDIATION**

This checkpoint stops here for owner review. It does not authorize Phase B publication, a catalog-pointer change, corporate-event settlement implementation, a Phase C run, or strategy development.
