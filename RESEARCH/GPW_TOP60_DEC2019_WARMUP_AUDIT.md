# GPW TOP60 complete-PIT start and 252-session warm-up audit

**Date:** 2026-08-26  
**Endpoint:** accepted Phase A comparison endpoint, 2026-08-18  
**Boundary:** coverage and readiness measurement only; Phase A/B/C and canonical datasets were not changed

## Answer

The new ORBIS and PLAY Investing.com histories, together with the three clean WSE histories retained by the Yahoo experiment, close the bounded acquisition list.

- **Earliest complete-PIT TOP60 date:** 2019-12-23.
- **Expected-trading source/native price coverage:** **99,721/99,721 (100%)**, where the 99,721 denominator is established independently of source presence.
- **Unexplained price gaps:** **0**.
- **Additional histories needed for price coverage or Stooq-evidenced warm-up:** **0**.
- **Strict 252-session path readiness:** 98,517/99,780 member-sessions (98.7342%); 1,263 windows remain intentionally ineligible because of listing age, genuine/no-reference non-trading dates, or post-exit dates.
- **Recommended start for a future rebuilt experiment:** **2019-12-23**, with the existing feature-specific eligibility masks retained. This is a recommendation for the future raw-basis experiment, not authorization to rebuild Phase A now.

The first date on which all 60 then-current members happen to pass the conservative every-WIG-session 252-bar test is 2022-05-26. It is not recommended as the experiment start: it discards more than two years and does not make later newly listed entrants automatically eligible.

## Source contract

| Priority | Role |
|---|---|
| Bossa `mstall` | primary source/native observations |
| Bossa session-page files | bounded Bossa supplements |
| Investing.com | primary supplement, including ORBIS and PLAY |
| Yahoo Finance | tertiary supplement only for the three clean WSE mappings: BNPPPL, DEVELIA, CYBERFLKS |
| Stooq | independent adjusted gap/expected-trading reference; never selected into the raw panel |

The degraded historical Yahoo symbols for PLAY and ORBIS remain validation evidence only. They are not selected because their retained histories follow a US holiday calendar and contain zero-volume placeholder rows. The new Investing histories are preferred and cover 21 PLAY and 40 ORBIS sessions that Yahoo omits inside the respective Investing spans.

## Coverage result

The complete-PIT grid contains 1,663 WIG sessions, 60 official members per session, 99,780 member-sessions, and 100 unique securities.

The corrected audit computes `expected_trading` from official membership minus independently evidenced non-trading/suspension states. Only then does it join selected-source observation presence and compute `covered_expected_trading`. Absence from Bossa, Investing.com, Yahoo, or Stooq never proves non-trading. The machine-readable member-session output retains official membership, expected-trading state, non-trading reason/evidence, source observation presence, coverage result, and unresolved/missing state separately.

| Selected source/state | Member-sessions |
|---|---:|
| Bossa `mstall` | 91,415 |
| Bossa session-page supplement | 85 |
| Investing.com supplement | 8,221 |
| Yahoo supplement in official member rows | 0 |
| Covered expected-trading observations | **99,721** |
| Established suspension/non-trading rows | 56 |
| Explicit zero-volume ORBIS non-trading rows | 3 |
| Unexplained/history-missing rows | **0** |
| Official denominator | **99,780** |

The 56 suspension rows are the previously classified four LOTOS and four PGNiG rows plus 48 ORBIS rows from 2020-04-09 through its TOP60 exit. GPW Resolution 283/2020 suspended ORBIS from 2020-04-09; the Investing history ends on the last trading session, 2020-04-08. The three earlier official-session absences are ORBIS on 2020-02-07, 2020-03-24, and 2020-03-25. Investing and Stooq omit them, while the retained Yahoo rows have volume zero and flat OHLC, so they are classified as non-trading rather than missing raw prices. No bar is synthesized. See the [republished GPW resolution](https://strefainwestorow.pl/wiadomosci/20200409/gpw-w-sprawie-zawieszenia-obrotu-akcjami-spolki-orbis-sa) and [KDPW deregistration resolution](https://www.kdpw.pl/uploads/documents/resolutions/2020/0561-2020.pdf).

## Targeted Investing/Yahoo validation

| Security | Investing span | Shared Yahoo sessions | Median absolute close difference | Decision |
|---|---|---:|---:|---|
| PLAY | 2017-07-28–2021-03-19 | 829 | 0.00000061 PLN | Investing primary; Yahoo validation only |
| ORBIS | 2014-01-02–2020-04-08 | 1,512 | 0.00000076 PLN | Investing primary; Yahoo validation only |

Ordinary shared closes map very closely, but isolated larger differences remain and the Yahoo calendars are demonstrably unsuitable as primary GPW histories. The Yahoo experiment still contributes directly to warm-up coverage through its clean BNPPPL, DEVELIA, and CYBERFLKS histories. Because Bossa covers those identities once they are official members, Yahoo contributes pre-membership history rather than selected official member-session rows.

Two selected Investing price observations have blank displayed volume:

- PLAY, 2020-06-03 — Yahoo contains a complete same-day whole bar with matching rounded OHLC and volume 1,065,354;
- CCC, 2020-06-10 — no accepted alternate raw-volume observation was established by this experiment.

Therefore price coverage is 100%, but full source/native **volume** coverage is not yet 100%. A later implementation may accept the complete Yahoo PLAY bar as a whole-bar override after explicitly approving that row; it must not splice Yahoo volume into Investing OHLC. CCC relative-volume features that depend on 2020-06-10 remain unavailable unless an independent whole raw bar is acquired.

## Strict 252-session readiness

The test requires a source/native price observation on every one of the immediately preceding 252 WIG sessions. It is intentionally stricter than the current Phase A momentum endpoint formula.

| State | Member-session windows |
|---|---:|
| Strictly ready | **98,517** |
| Not ready — listing/source-age limitations | 985 |
| Not ready — internal no-reference dates | 156 |
| Not ready — known ORBIS zero-volume/non-trading dates | 116 |
| Not ready — established post-exit/suspension dates | 6 |
| Total not ready | **1,263** |

On 2019-12-23, 58 of 60 members pass. GETIN is missing nine January-2019 sessions with no Stooq reference; ORBIS is missing six documented zero-volume/non-trading sessions in the prior window. These are eligibility states, not requests for another vendor history. Across the full interval, newly listed ALLEGRO, ZABKA, GRUPRACUJ, PEPCO, HUUUGE, DIAG, and STSHOLDING account for the 985 listing-age windows.

## Start-date recommendation

Use **2019-12-23** as the evaluation start for a future rebuild because it is the earliest date at which:

1. the official WIG20+mWIG40 membership semantics are complete and preserve the 60-name denominator;
2. every expected-trading member-session price is available from the approved source hierarchy;
3. all previously identifiable history acquisitions are complete.

Keep feature-specific eligibility rather than delaying the entire cross-section until an incidental all-60 strict date. The 252-session price-history floor remains 2018-12-17. This recommendation does not remove the separate split-normalization, price-return-basis, or corporate-action gates.

## Verification

Corrected immutable run:

`D:\Stock\data\ATS\top60_dec2019_warmup_audit\runs\top60-dec2019-warmup-20260826-v9-corrected`

Byte-identical reproduction:

`D:\Stock\data\ATS\top60_dec2019_warmup_audit\runs\top60-dec2019-warmup-20260826-v9-corrected-reproduction`

- Manifest SHA-256: `A4B8E943B8B543B0CD04D8F25BB3FC45896C07854F8068FC0E8223A08BE79AAC`
- Metrics SHA-256: `7DBCF04B1ABB09FFA4AD0785BE5AF3D2C8E0ACF43212F068AD5EC9C67EC732C5`
- Membership assertion SHA-256: `3A488DA4598336EFF134AA4DEF08C066D278BF8349C9E1F7D2BBB2C991742BDB`
- Reproduction: **PASS — all seven retained files are byte-identical**
- v8 reconciliation: **PASS — official 99,780, expected 99,721, covered 99,721, independently non-trading 59; accepted v8 was not overwritten**
- Phase A/B/C modifications: **none**

## Conclusion

**Recommended future experiment start: 2019-12-23**  
**Expected-trading raw-price coverage: 100%**  
**Additional price histories needed: 0**  
**Strict 252-session readiness for every member-session: NOT 100% — 1,263 windows explicitly ineligible**  
**Full selected-source volume coverage: NOT 100% — 2 displayed-volume observations missing**
