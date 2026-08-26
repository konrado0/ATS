# GPW TOP60 split-normalization checkpoint

**Checkpoint date:** 2026-08-26

**Decision boundary:** evidence freeze plus bounded split/reverse-split/consolidation discovery and candidate-panel construction only

**Evaluation interval:** 2019-12-23 through 2026-08-18 inclusive

**History floor:** 2018-12-17

**Outcome:** conditional candidate panel published for owner review; Phase A v2 was not run

## Executive decision

Checkpoint 1A is **PASS**. The corrected denominator is independent of vendor coverage, the immutable correction reproduces, the 20+40 membership boundary fails closed, the normal suite collects the four offline Yahoo tests, accepted Phase A/B/C artifacts retain their prior hashes, and the evidence is frozen in Git commit `f79c7cfb068543047a5cd43319d922f3b8097872`.

Checkpoint 1B is **PASS WITH CAVEATS**. All two numerical candidates were resolved, Dino's in-universe split is normalized and independently checked, native observations and volume precision are preserved, and the candidate panel reproduces byte-for-byte. However, authoritative event-discovery coverage is **NOT PROVEN**: the KDPW corporate-event report that could provide structured interval coverage is a paid data package and was not available to this checkpoint. Public issuer/ESPI searches do not establish exhaustive no-event coverage for every ISIN and interval.

The panel is therefore **ACCEPT WITH CAVEATS**, and readiness for Phase A v2 is **OWNER DECISION REQUIRED**. There is no known unresolved event affecting a consumed window, but absence of additional events has not been authoritatively proven.

## Pinned evidence and run

- Candidate run ID: `gpw-split-normalization-20260826-v4`
- Run directory: `D:\Stock\data\ATS\gpw_split_normalization\runs\gpw-split-normalization-20260826-v4`
- Manifest: `D:\Stock\data\ATS\gpw_split_normalization\runs\gpw-split-normalization-20260826-v4\manifest.json`
- Manifest SHA-256: `E77CE37CB51C3A1E5608B4B2C9B112ABE51635BDAE1CE64DB0B5AA7D4780331A`
- Reproduction: `D:\Stock\data\ATS\gpw_split_normalization\runs\gpw-split-normalization-20260826-v4-reproduction`
- Checkpoint 1A evidence commit: `f79c7cfb068543047a5cd43319d922f3b8097872`
- Candidate implementation commit: `11367f4472ed9b3f32be0c7cd06a81126f78af6c`
- Exact run code commit: `89f0ba4ccc1da885d812d7810325797f0667338f`
- Environment lock SHA-256: `290334A1C972E3780B354ACFC607C076CE4AE6A77B0905EB41DFB5AA45E48A6D`

This is an immutable research candidate, not canonical Phase B data. Raw/vendor inputs were read in place and not modified.

## Checkpoint 1A — corrected evidence

The v8 audit set `expected_trading` from observed coverage, so a missing vendor bar could remove itself from the denominator. The v9 correction constructs the official membership grid first, subtracts only independently evidenced suspension/non-trading sessions, and only then tests whether a validated selected-source price bar exists.

| Measure | Count | Meaning |
|---|---:|---|
| Official member-sessions | 99,780 | 1,663 sessions times exactly 60 members |
| Independently established non-trading member-sessions | 59 | reason and evidence retained separately |
| Expected-trading member-sessions | 99,721 | independent denominator |
| Covered expected-trading member-sessions | 99,721 | selected-source price observation exists |
| Missing expected-trading member-sessions | 0 | empirical result |
| Coverage | 100% | `99,721 / 99,721`, not a definition |

The adversarial test removes a source bar from an expected member-session and verifies that the numerator decreases while the expected denominator does not. Separate fields retain official membership, expected-trading state, non-trading reason/evidence, observation presence, coverage, and unresolved/missing state.

Corrected audit run: `D:\Stock\data\ATS\top60_dec2019_warmup_audit\runs\top60-dec2019-warmup-20260826-v9-corrected`. Its reproduction directory is byte-identical. The corrected manifest SHA-256 is `A4B8E943B8B543B0CD04D8F25BB3FC45896C07854F8068FC0E8223A08BE79AAC`; the metrics SHA-256 is `7DBCF04B1ABB09FFA4AD0785BE5AF3D2C8E0ACF43212F068AD5EC9C67EC732C5`. Accepted v8 was retained unchanged and reconciled rather than overwritten.

The repository membership assertion records the inclusive 2019-12-23 to 2026-08-18 boundary, input paths and hashes, WIG20/mWIG40 roles, effective-snapshot/change-event semantics, 20+40 counts, duplicate/overlap rules, limitations, and schema version. Validation rejects dates outside the asserted boundary, role counts other than 20 and 40, duplicate keys, and cross-role identity overlap. Assertion SHA-256: `3A488DA4598336EFF134AA4DEF08C066D278BF8349C9E1F7D2BBB2C991742BDB`.

The normal repository command, run from `source/python`, collected and passed 107 tests. It automatically includes these offline, deterministic Yahoo tests:

- `test_normalization_preserves_identity_dates_and_actions`
- `test_validation_accepts_valid_ohlcv`
- `test_validation_rejects_duplicate_and_bad_high`
- `test_normalization_excludes_empty_calendar_placeholders`

## Universe and consumed-data boundary

The immutable universe contains exactly 100 security identities appearing in the PIT WIG20 plus mWIG40 history. The repository evidence `consumed_spans.csv` has one row per identity, including ISIN, first/last official session, bounded start/end, 252-session feature lookback, 20-session forward-label horizon, uncapped endpoint, and endpoint-censor flag.

The aggregate consumed boundary is 2018-12-17 through 2026-08-18. Per-security starts are bounded by the earlier of required lookback and the global floor; ends include the required post-membership forward window where available but never exceed the fixed dataset endpoint. Forward labels whose required future observations extend past 2026-08-18 remain explicitly censored. No earlier vendor history was scanned merely because a file contained it.

## Authoritative discovery leg

The per-security `discovery_log.csv` contains 100 rows and records identity, ISIN, searched interval, sources, query method, check date, returned events, completeness claim, and limitations. The structured route investigated was the [KDPW Data Portal](https://data.kdpw.pl/) `GET/events` / `GET/events_2`, parameterized by ISIN and the in-scope split/reverse-split/consolidation event types. KDPW's [report pricing page](https://data.kdpw.pl/p/fees) identifies the corporate-event report as paid package 4; no entitlement was available. Public issuer and ESPI searches were used to resolve detected events but do not claim exhaustive interval coverage.

**Authoritative event-discovery coverage: NOT PROVEN.** A zero-result public search was never treated as proof that no event occurred. The bounded search stopped after establishing this source limitation.

## Independent numerical discovery leg

The scanner examined every consumed selected-source series for:

- native price-scale discontinuities;
- reciprocal price/volume scaling;
- stable selected-source-to-Stooq ratio regime changes;
- source-switch level discontinuities;
- structured vendor split records.

Stooq was used only for adjusted QA ratios and never selected into the panel. Numerical results are diagnostic, not event authority. The scan produced two relevant candidates:

| Identity/session | Diagnostic | Final disposition | Evidence |
|---|---|---|---|
| Dino, `PLDINPL00011`, 2025-07-31 | native close ratio 0.098825, reciprocal volume behavior, exact 0.1 Bossa/Stooq ratio step | confirmed split | [issuer current report 10/2025 / KDPW statement 672/2025](https://grupadino.pl/en/current-report-no-10-2025-kdpw-statement-regarding-the-designation-of-the-split-date-for-dino-polska-s-a-shares/) |
| OncoArendi, `PLONCTH00011`, 2020-11-06 | close 3.167x and volume 29.552x; no reciprocal unit change or Stooq ratio regime step | demonstrated non-split | [official current report 22/2020](https://molecure.com/app/uploads/2022/06/rb_22_2020.pdf) announcing the Galapagos licensing agreement after the prior session |

**Detected event and anomaly resolution: PASS.** Unresolved detected candidates: 0.

## Confirmed event and source-series treatment

The confirmed ledger contains one in-scope event:

| Field | Dino value |
|---|---|
| Security / ISIN | `isin:PLDINPL00011` / `PLDINPL00011` |
| Event | split; one old share became ten new shares |
| Last pre-event session | 2025-07-30 |
| First post-event/effective session | 2025-07-31 |
| Pre-event OHLC multiplier | 0.1 |
| Pre-event volume multiplier | 10 |
| Announcement/availability | 2025-07-28 |
| Evidence ID | `DINO_CURRENT_REPORT_10_2025_KDPW_STATEMENT_672_2025` |
| Event record | `ats.gpw.split_event.v1` |

Dino was an official WIG20 member on the event session. The issuer report states that 98,040,000 shares became 980,400,000 shares on 2025-07-31.

Treatment is event- and source-series-specific:

| Source series | Treatment |
|---|---|
| Bossa `mstall`, Dino input hash `c25a4c0…` | `source_unadjusted_for_event` |
| Consumed Bossa post-event session-page series | `source_already_adjusted_for_event` |
| Investing.com Dino policy | `unknown`; not selected in the consumed Dino boundary |
| Accepted Yahoo Dino policy | `unknown`; not selected in the consumed Dino boundary |
| Explicit missing state | `not_applicable` |

There is no vendor-global adjustment flag. An unknown treatment at a boundary fails closed.

## Transformer and Dino golden reconciliation

The transformer accepts source/native rows only, keeps native OHLCV, derives separate adjusted fields, applies cumulative confirmed factors only to source series classified unadjusted, passes already-adjusted rows through, and rejects invalid ratios, unresolved treatment boundaries, and derived input. It never combines fields from different vendors, preserves missing volume, and synthesizes no bars.

Its reproducibility contract is regeneration from the same immutable native observations, ledger, configuration, and code produces identical output. It does not claim that adjustment arithmetic is mathematically idempotent. The double-application guard rejects any input marked split-adjusted or derived.

| Dino session | Bossa native close | ATS split-adjusted close |
|---|---:|---:|
| 2025-07-30 | 502.00 | 50.20 |
| 2025-07-31 | 49.61 | 49.61 |

The native mechanical return is -90.1175%; `split_adjusted_price_return` is -1.1753%. Across the 15-session 2025-07-21 to 2025-08-08 event window, ATS adjusted/Stooq close ratios are 1.0 within floating-point tolerance and adjusted/Stooq volume ratios are 1.0. This is an event-window invariant, not a requirement for general price-level equality; Stooq may embed additional dividend adjustments.

## Volume basis and precision

| Precision state / basis | Rows | Relative-volume usable |
|---|---:|---:|
| `exact_source_reported_shares` / `shares` | 117,782 | 117,782 |
| `vendor_displayed_rounded_volume` / `vendor_displayed_shares` | 11,020 | 11,020 |
| `unknown_precision` / `shares_unknown_vendor_derivation` | 271 | 0 |
| `missing_volume` / `missing` | 1,131 | 0 |

Split multiplication preserves each row's original precision classification. Rounded Investing.com volume does not become exact. Missing volume remains missing and the relative-volume feature is unavailable. No cross-vendor OHLC/volume splice was made.

## Candidate-panel validation

The panel contains 130,204 bounded rows, of which 99,780 are official member-sessions. Whole-panel source counts are 117,693 Bossa `mstall`, 89 Bossa session-page, 11,023 Investing.com, 271 accepted Yahoo, and 1,128 explicit missing rows. Official-member source counts are 91,415 Bossa `mstall`, 85 Bossa page, 8,221 Investing.com, and 59 explicit non-trading/missing-state rows.

The official grid retains exactly 60 identities per evaluation session. Corrected expected versus usable counts reconcile at 99,721 expected-trading and 99,721 price-covered. Feature eligibility remains feature-specific; 129,076 panel rows are price-usable, while relative-volume availability follows the separate precision table above.

Validation established:

- native OHLCV unchanged;
- unaffected derived observations equal native observations;
- all OHLC fields use the same cumulative price factor and retain a valid envelope;
- Dino hand calculation and split-neutral return;
- unknown treatment and invalid ratio fail closed;
- reverse split and multiple cumulative-event fixtures;
- derived-input rejection;
- two independent regenerations have identical hashes for all 9 artifacts;
- candidate row counts agree across Arrow, Polars, and DuckDB;
- normal suite: 107 passed;
- accepted Phase A/B/C validators pass and accepted manifests retain their pre-checkpoint hashes.

Logical hashes:

- Native: `e486ae77fe3220d2a43d72398705dbf923aadedf1306f6370ac8541c78bfd8d8`
- Adjusted: `447fbadaac4418c04b257bd46bf8daa81b24b2546ac40b0f3ff89763ed9fdd4e`
- Candidate Parquet physical: `C23FFBFC6AAAB8BAFD466BD980F906EC4476FD051AEBCC8C0FA3B7E57A9F8C15`

## Scope and limitations

This is split-adjusted price data, not total-return data and not an execution-price series. If returns are materialized they are named `split_adjusted_price_return` with:

```text
cash_distributions_included = false
cash_dividend_price_gaps_preserved = true
```

Cash dividends, rights issues, spin-offs, merger/takeover accounting, execution accounting, and total-return construction were not added. Cash-dividend price gaps therefore remain in the series; total returns are future work.

SUNEX, BLOOBER, and CASPAR remain useful external transformer controls, but are not TOP60 evidence unless PIT membership places them in the experiment. Dino is the direct in-universe golden case.

## Completion audit

| Item | Verdict | Condition/evidence |
|---|---|---|
| Checkpoint 1A evidence freeze | PASS | scoped commit `f79c7cf…` |
| Independent denominator | PASS | source absence cannot reduce expected denominator |
| Structured membership boundary | PASS | hashed assertion, fail-closed 20+40 validation |
| Normal test discovery | PASS | 107 passed; four Yahoo tests collected offline |
| Authoritative split-event discovery coverage | NOT PROVEN | comprehensive KDPW event feed unavailable; public searches non-exhaustive |
| Numerical anomaly scan | PASS | all five diagnostic classes applied to 100 consumed identities |
| Resolution of every detected relevant candidate | PASS | two of two resolved; zero unresolved |
| Dino normalization | PASS | hand calculation and Stooq invariant |
| Per-event/source-series treatment | PASS | explicit independent treatment records |
| Derived-input rejection | PASS | tested fail-closed guard |
| Deterministic regeneration | PASS | all 9 primary/reproduction files byte-identical |
| Native observations preserved | PASS | validated and hashed separately |
| Volume basis and precision preserved | PASS | four controlled states retained |
| Candidate panel complete and reproducible | PASS WITH CAVEATS | complete for fixed selected-source contract; authoritative event absence not proven |
| Accepted Phase A/B/C unchanged | PASS | validators and manifest hashes rechecked |
| Repository evidence committed | PASS | scoped evidence-freeze and implementation commits; final small evidence/report commit encloses this report |
| Ready to run Phase A v2 | OWNER DECISION REQUIRED | no known unresolved event, but authoritative all-identity/all-interval discovery remains NOT PROVEN |

## Mandatory stop

- **Checkpoint 1A: PASS**
- **Authoritative split discovery: NOT PROVEN**
- **Detected-event resolution: PASS**
- **Checkpoint 1B: PASS WITH CAVEATS**
- **Candidate split-adjusted panel: ACCEPT WITH CAVEATS**
- **Ready for Phase A v2: OWNER DECISION REQUIRED**

The sole readiness caveat is residual split/reverse-split/consolidation discovery uncertainty outside the two detected and resolved candidates: sufficiently complete authoritative coverage for all 100 identities and their consumed intervals was not established. A later owner may accept that residual risk or require access to a comprehensive KDPW/equivalent feed and an updated discovery assertion. A newly identified unresolved event affecting a consumed feature or label window changes readiness to **NO**.

Phase A v2, Phase B publication, Phase C changes, strategy research, and the requested basis/interval comparisons were not performed.
