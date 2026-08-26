# GPW raw-price coverage audit

## Boundary and answer

The official TOP60 evaluation grid is the accepted Phase A grid from **2020-11-27 through 2026-08-18**: 1,430 sessions, exactly 60 official members per session. The **2019-01-01** boundary is the source-history warm-up start, not an additional membership/evaluation interval. Stooq is used only to define the comparison observations; no Stooq value is inserted into the source/native panel.

- **Bossa alone, including the two supplied Bossa session pages:** **No.** It covers 79,500 of 83,836 Stooq-covered member-sessions (94.8280%); 4,336 Stooq-covered observations remain absent from Bossa.
- **Bossa + existing Investing.com:** **Yes.** Together they cover **83,836/83,836 Stooq-covered member-sessions (100%)**.
- **Additional Investing histories needed for 100% versus Stooq:** **0**.

In this audit, `raw-price coverage` means **presence of a validated source/native vendor observation**, not proof that the vendor history is raw through every corporate action. Subsequent split forensics prove that Bossa is mixed across splits and that Investing.com BLOOBER is already split-adjusted. Coverage therefore passes independently of price-basis readiness. The rebuild decision and required normalization contracts are recorded in `GPW_PHASE_A_PRICE_BASIS_READINESS.md`.

This 100% result is bounded to the 2020-11-27 evaluation start. The later corrected complete-PIT/warm-up audit in `GPW_TOP60_DEC2019_WARMUP_AUDIT.md` begins on 2019-12-23 and requires 252 preceding WIG sessions. Its expected-trading denominator is established independently of vendor presence. Its former five-history acquisition list is now complete: ORBIS and PLAY come from Investing.com, while the Yahoo experiment supplies clean BNPPPL, DEVELIA, and CYBERFLKS prehistory. The corrected audit reports 99,721/99,721 expected-trading price coverage and zero additional price histories.

## Counts

| Measure | Member-sessions |
|---|---:|
| Total official member-sessions | 85,800 |
| Stooq-covered member-sessions | 83,836 |
| Bossa `mstall`-covered member-sessions | 79,415 |
| Additional Bossa-page supplements to `mstall` | 85 |
| Bossa-covered member-sessions after page supplements | 79,500 |
| Bossa missing where Stooq is covered | 4,336 |
| Investing-supplemented member-sessions, across the full official grid | 6,292 |
| Investing supplements that close a Stooq-covered gap | 4,336 |
| Bossa + Investing coverage where Stooq is covered | **83,836** |
| Remaining unexplained raw-price gaps versus Stooq | **0** |

The 6,292 remaining Investing supplements comprise SANPL/ERSTEPL 1,349, CCC/MODIVO 1,304, CIECH 714, COMARCH 977, LOTOS 417, LIVECHAT/TEXT 706, PGNIG 482, STSHOLDING 239, and TIM 104. Of these, 4,336 close Stooq-covered gaps. The other 1,956 observations belong to the five histories Stooq does not cover.

## Classification of Bossa-missing official rows

| Classification | Count |
|---|---:|
| Bossa available, including page supplements | 79,500 |
| Bossa missing, existing Investing available | 6,292 |
| Both raw sources missing and Stooq has a bar | **0** |
| Legitimate suspension/non-trading | 8 |
| Unresolved identity | 0 |
| Not yet listed / otherwise not expected to trade | 0 |

The eight legitimate no-bar rows are LOTOS on 2022-07-29, 2022-08-01, 2022-08-02, and 2022-08-03, and PGNIG on 2022-10-31, 2022-11-02, 2022-11-03, and 2022-11-04. Stooq also has no bars on those rows.

## Bossa page reconciliation and residual sessions

Both supplied pages reconcile to all 60 official members on their session dates and contain 120 valid OHLCV bars:

- 2025-11-12: 60/60 valid official bars; 25 supplement missing `mstall` rows.
- 2026-02-20: 60/60 valid official bars; all 60 supplement missing `mstall` rows.

All **73** rows in the prior residual list match exactly one valid page bar. The other 12 page supplements replace Investing observations for MBANK, KGHM, PKNORLEN, SANPL/ERSTEPL, CCC/MODIVO, and LIVECHAT/TEXT on the two page dates. The CCC/MODIVO 2025 row is bound validity-aware by exact GPW ticker `MDV` to ISIN `PLCCC0000016`; the other 119 official rows match the PIT short name directly.

Only 39 of the 120 Bossa page bars are numerically identical to Stooq across complete OHLCV. That does not affect presence coverage and is consistent with keeping source-native Bossa/Investing observations distinct from the independent Stooq reference; this audit does not normalize or splice prices. Numeric identity on an individual row does not establish a vendor-wide adjustment convention.

The immutable accepted run is `D:\Stock\data\ATS\raw_price_coverage_audit\runs\gpw-raw-price-coverage-20260824-v6`. Its `residual_missing_sessions.csv` is empty. It also contains the parsed page rows, 120-row official reconciliation, identity map, per-security summary, invalid-row audits, metrics, hashes, and source manifest. No Phase A/B/C artifact was changed.

For future use, the two page-derived sessions are also materialized below the Bossa directory at `D:\Stock\data\mstall\session_supplements\manual_page_copy_2026-08-24`. The session-scoped files use the standard seven-column MST schema and contain 355 valid bars for 2025-11-12 and 354 for 2026-02-20. They are deliberately separate from the vendor-downloaded per-security histories. The colocated `manifest.json` pins the raw-page, parser, materializer, and output hashes; `README.md` gives the exact recreation command and merge/conflict policy. The 9 and 10 explicit no-bar page rows are excluded and counted, not synthesized.

**Raw-price coverage vs Stooq: 100% — exactly 0 observations missing**

**Accepted replacement Phase A price-basis readiness: NOT ESTABLISHED BY COVERAGE ALONE**
