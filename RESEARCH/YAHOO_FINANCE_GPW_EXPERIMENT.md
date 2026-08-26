# Yahoo Finance GPW source experiment

**Accepted experiment:** `yahoo-gpw-20260826-v3`  
**Acquired:** 2026-08-26  
**Scope:** 2014-01-01 through 2026-08-25 for active histories; source lifecycle where shorter  
**Gate:** `YAHOO_USEFUL = YES`  
**Decision:** **ADOPT YAHOO AS SUPPLEMENTAL SOURCE**

Yahoo is useful as a separately retained supplemental observation and corporate-action source. It is not suitable as the primary GPW source. Three of the five warm-up targets have clean WSE-equity metadata and cover every required history session. PLAY and ORBIS expose historical bars, but Yahoo now assigns them degraded `YHD/MUTUALFUND` metadata and a US rather than GPW trading calendar. They therefore remain evidence with an identity/session warning and do not fully close the exact-session warm-up gaps.

No Yahoo row was injected into Phase A/B/C, no accepted pointer changed, no fallback vendor supplied a missing Yahoo bar, and no fields were spliced across vendors.

## 2026-08-26 Investing.com target-history follow-up

The subsequently supplied Investing.com PLAY and ORBIS histories resolve the Yahoo experiment's exact-session limitation. Investing is now the preferred source for both legacy identities; Yahoo remains validation and non-trading evidence only for them. Across the Investing spans, PLAY has 829 shared Yahoo sessions and ORBIS 1,512. Median absolute close differences are approximately `6.1e-7` and `7.6e-7` PLN, while Investing additionally covers 21 PLAY and 40 ORBIS sessions omitted by Yahoo's US calendar.

Yahoo's clean BNPPPL, DEVELIA, and CYBERFLKS histories are accepted as tertiary warm-up supplements. They resolve all 72, 180, and 19 previously Stooq-evidenced pre-Bossa dates. They contribute no selected official member-session rows because Bossa already covers those identities during their membership intervals.

The combined result in `GPW_TOP60_DEC2019_WARMUP_AUDIT.md` is now 100% expected-trading price coverage from 2019-12-23 and zero additional price histories. The start recommendation for a future rebuild is 2019-12-23 with feature-specific eligibility retained. This follow-up does not promote Yahoo to primary-source status or change its split/event caveats.

## Acquisition mechanism and semantics

The retained acquisition used `yfinance 1.6.0`, `Ticker.history`, daily interval, a start-inclusive/end-exclusive request, and these explicit settings:

```text
auto_adjust=False
back_adjust=False
repair=False
actions=True
keepna=True
rounding=False
```

The untouched yfinance table is retained before normalization. Empty post-delisting calendar placeholders produced by `keepna=True` remain in `yfinance_native.csv` but are excluded from `normalized_daily.csv`; the exclusion count is recorded in each provenance file. No timezone conversion or price adjustment is applied. The acquisition-day bar was excluded to avoid retaining a potentially incomplete session.

The [yfinance history documentation](https://ranaroussi.github.io/yfinance/reference/yfinance.price_history.html) defines `end` as exclusive and documents the adjustment/repair flags. The [price-repair documentation](https://ranaroussi.github.io/yfinance/advanced/price_repair.html) confirms that `repair=True` may alter prices, dividend adjustments, missing data, and split treatment; it was deliberately disabled here. yfinance is not affiliated with or endorsed by Yahoo and directs users to Yahoo's terms, as stated in the [upstream project](https://github.com/ranaroussi/yfinance). A working request is not evidence of a stable production API.

Empirical semantics, bounded to the tested GPW cases:

- `Open/High/Low/Close` are already placed on the post-split scale for all three tested splits even though yfinance auto/back adjustment is disabled. `Close` is not cash-dividend-adjusted.
- `Adj Close` is split-adjusted and also changes its historical factor at every one of the 29 observed target dividend records. It is suitable for validation, not assumed to be a complete total-return truth.
- Volume is generally transformed inversely across splits. One source defect is retained: BLOOBER volume on 2021-03-17 is 224,900, ten times Stooq's split-adjusted 22,490 and one hundred times Bossa's raw 2,249. The other 39 BLOOBER window sessions agree with the split-adjusted reference.
- Cash dividends and splits are explicit event columns. A `Capital Gains` column appeared only on legacy `YHD` tables and had no nonzero event in the five targets. Other-action completeness is not proven.

## Yahoo capabilities

| Capability | Result | Evidence boundary |
|---|---|---|
| GPW daily OHLCV | YES | Five targets plus three split controls returned daily bars |
| old/delisted GPW histories | CONDITIONAL | PLAY, ORBIS and old BZW exist; LOTOS, PGNiG, CIECH and COMARCH did not resolve |
| ticker-change continuity | CONDITIONAL | Current `MBK.WA`, `EBP.WA`, and `TXT.WA` span prior names; old/current symbol discovery is inconsistent |
| dividend events | YES | 29 explicit events across the five targets |
| split events | YES | Correct date and ratio for SNX, BLO and CSR |
| other corporate actions | CONDITIONAL | No comprehensive non-dividend/non-split event coverage proven |
| split-adjusted validation | CONDITIONAL | Price treatment is clear; one 10x BLO volume anomaly is retained |
| economic-return validation | CONDITIONAL | `Adj Close` and dividends are informative, but action completeness and DEVELIA/Stooq differences remain unresolved |
| suitable as primary GPW source | NO | Delisted coverage, legacy calendar metadata, completeness and endpoint stability fail that bar |
| suitable as ATS supplemental | YES | Useful whole-source histories, actions and independent controls when provenance and warnings are retained |

## Five target histories

| Security | Yahoo ticker | Found | First | Last | Valid price rows | Price semantics | Actions | Saved |
|---|---|---:|---:|---:|---:|---|---:|---:|
| PLAY | `PLY.WA` | CONDITIONAL | 2017-07-27 | 2021-04-01 | 927 | split-adjusted Close; YHD/US-calendar warning | 3 dividends | YES, warned |
| ORBIS | `ORB.WA` | CONDITIONAL | 2014-01-02 | 2020-06-25 | 1,631 | split-adjusted Close; YHD/US-calendar warning | 5 dividends | YES, warned |
| BNPPPL | `BNP.WA` | YES | 2014-01-01 | 2026-08-25 | 3,222 | WSE equity; Close matches Bossa overlap | 3 dividends | YES |
| DEVELIA | `DVL.WA` | YES | 2014-01-01 | 2026-08-25 | 3,222 | WSE equity; Close matches Bossa overlap | 10 dividends | YES |
| CYBERFLKS | `CBF.WA` | YES | 2017-12-29 | 2026-08-25 | 2,194 | WSE equity; Close matches Bossa overlap | 8 dividends | YES |

All normalized target tables passed chronological unique-date, positive-price, OHLC-relationship, and nonnegative-volume validation. Yahoo does not provide these ISINs through the tested yfinance mechanism; the saved provenance therefore carries the explicit owner-provided security/ISIN-to-Yahoo-symbol mapping rather than relying on ticker alone.

### Effect on the accepted warm-up gaps

This is a read-only comparison to the accepted `top60-dec2019-warmup-20260826-v4` missing-detail artifact, not a Phase A rerun.

| Security | Unique required history sessions | Present in Yahoo | Still absent | Interpretation |
|---|---:|---:|---:|---|
| PLAY | 484 | 473 | 11 | not an exact GPW-session replacement |
| ORBIS | 371 | 362 | 9 | not an exact GPW-session replacement |
| BNPPPL | 72 | 72 | 0 | bounded gap covered |
| DEVELIA | 180 | 180 | 0 | bounded gap covered |
| CYBERFLKS | 19 | 19 | 0 | bounded gap covered |

The 20 residual dates are US market holidays on which GPW traded. PLAY lacks 2019-01-21, 2019-02-18, 2019-05-27, 2019-07-04, 2019-09-02, 2019-11-28, 2020-01-20, 2020-02-17, 2020-05-25, 2020-07-03, and 2020-09-07. ORBIS lacks the first nine of those through 2020-05-25. This mechanically confirms that Yahoo's legacy `YHD` calendar is not safe for exact GPW session joins. No bars may be synthesized or re-dated.

### Vendor overlap diagnostics

- BNPPPL, DEVELIA and CYBERFLKS Yahoo `Close` have median ratios of exactly 1.0 to Bossa over 1,842, 1,735 and 759 matched sessions. Median absolute daily-return differences are approximately `1.56e-8`, `2.39e-8`, and `0`.
- Yahoo `Adj Close` approximately matches Stooq for BNPPPL and CYBERFLKS, but not for DEVELIA: median Yahoo-Adj-Close/Stooq-Close ratios are 1.0013, 1.0010 and 0.8286 respectively. This is a useful warning that economic adjustment completeness cannot be assumed from the split tests.
- No existing Investing.com target history was present, so there was no target-level Investing overlap to compare. PLAY and ORBIS had no local Bossa/Stooq target history either; their warning remains unresolved rather than being hidden.

## Split results

Each case has at least 20 Yahoo sessions before and after. Official dates/ratios were treated as ground truth; local Bossa and Stooq were comparison references only.

| Security | Event | Yahoo split record | Last pre / first post Close | Last pre / first post volume | Close treatment | Volume treatment | Confidence |
|---|---|---:|---:|---:|---|---|---|
| SUNEX | 1:5, 2020-09-15 | 5.0 on 2020-09-15 | 5.00 / 6.26 | 73,555 / 565,604 | split-adjusted | split-adjusted | high |
| BLOOBER | 1:10, 2021-03-18 | 10.0 on 2021-03-18 | 19.34 / 20.20 | 224,900 / 78,336 | split-adjusted | mostly adjusted; 10x anomaly on 2021-03-17 | high |
| CASPAR | 1:5, 2021-11-04 | 5.0 on 2021-11-04 | 15.80 / 15.60 | 0 / 5 | split-adjusted | split-adjusted over the comparison window | high |

For BLOOBER, Yahoo/Bossa median ratios before versus after are 0.1 to 1.0 for Close and 10.0 to 1.0 for volume, proving the inverse split transformation. Yahoo volume matches Stooq on 39/40 sessions; the event-eve observation is the explicit exception. For CASPAR the comparable Yahoo/Bossa medians are 0.2 to 1.0 for Close and 5.0 to 1.0 for nonzero volume. SUNEX matches Bossa's already adjusted series on both sides. Yahoo `Adj Close` has a stable ratio to Stooq before and after each event, so no split-factor step remains in either adjusted price series.

## Continuity and delisting results

- `MBK.WA` spans 2000-01-03 onward and crosses the BRE Bank to mBank rename.
- `EBP.WA` spans 2001-06-26 onward and is the current WSE/PLN Yahoo identity for Erste Bank Polska, formerly Santander Bank Polska; it retains the earlier BZ WBK/Santander history. The [current Yahoo profile](https://finance.yahoo.com/quote/EBP.WA/) confirms the Warsaw listing and 2026 company rename. `SPL.WA` now returns 404.
- `TXT.WA` spans its 2014 listing through the LiveChat-to-Text rename. `LVC.WA` did not resolve.
- The old `BZW.WA` history exists through 2018-09-14 but carries degraded `YHD/MUTUALFUND` metadata.
- `LTS.WA`, `PGN.WA`, `CIE.WA`, and `CMR.WA` did not return histories. Yahoo is therefore not a reliable delisted-GPW archive.

## Tooling and retained artifacts

Code and tests:

- `RESEARCH/prototypes/yahoo_finance_gpw_experiment/yahoo_gpw.py` — acquisition, native preservation, normalization, validation, hashes and provenance;
- `RESEARCH/prototypes/yahoo_finance_gpw_experiment/run_experiment.py` — bounded targets, continuity, action/split analysis, vendor diagnostics and manifest;
- `RESEARCH/prototypes/yahoo_finance_gpw_experiment/tests/test_yahoo_gpw.py` — four network-free focused tests, all passing;
- `probe_candidates.py`, `probe_metadata.py`, and `probe_search.py` — retained symbol-discovery evidence.

Accepted evidence and data:

- run: `D:\Stock\data\ATS\yahoo_finance_gpw_experiment\runs\yahoo-gpw-20260826-v3`;
- run manifest SHA-256: `C6C2F5CA85C2E932C657E859EC5B5AF1C8A775099A161FA95FAE4F316968A69E`;
- target data: `D:\Stock\data\raw\yahoo_finance\gpw\daily\acquisition_2026-08-26`;
- 20 target files, 3,233,906 bytes: native CSV, normalized CSV, Yahoo metadata JSON and provenance JSON for each security;
- 11 run-evidence files: target, split, dividend, continuity, WIG-session, accepted-gap and vendor diagnostics plus capabilities and manifest.

Earlier failed/superseded experimental runs were preserved under explicit `.failed-v1` or `.superseded` names and are excluded from the accepted decision. The accepted evidence is v3 only.

## Final decision

**ADOPT YAHOO AS SUPPLEMENTAL SOURCE.**

Use Yahoo only as a separately manifest-backed whole-history/action source with per-symbol metadata and calendar validation. It can cover the bounded BNPPPL, DEVELIA and CYBERFLKS warm-up needs and provides valuable explicit split/dividend evidence. Do not use the retained PLAY or ORBIS tables as exact GPW-session replacements without independent identity/calendar resolution, do not auto-repair the observed BLOOBER volume defect silently, and do not treat Yahoo as a primary or stable production GPW API.
