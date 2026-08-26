# GPW Phase A price-basis rebuild readiness

**Checkpoint date:** 2026-08-25  
**Scope:** determine whether the accepted GPW Phase A can be rebuilt from a Bossa-primary, Investing.com-supplemented observation layer, with Stooq retained only as an independent adjusted reference  
**Decision boundary:** reporting and verification only; no Phase A/B/C run, canonical publication, parser change, corporate-action implementation, or source-file mutation

## 2026-08-26 targeted warm-up enrichment — final coverage update

The owner-supplied ORBIS and PLAY Investing.com histories and the retained Yahoo experiment close the previously reported five-history acquisition list. The accepted complete-PIT audit now uses Bossa `mstall`, Bossa session-page supplements, Investing.com, then only the three clean Yahoo WSE histories (BNPPPL, DEVELIA, CYBERFLKS). The degraded Yahoo PLAY/ORBIS legacy symbols are validation evidence only.

From 2019-12-23 through 2026-08-18 the layered sources cover **99,721/99,721 expected-trading price observations (100%)**, with zero unexplained price gaps and zero additional price histories required. The other 59 official member-session rows are explicit non-trading states: 56 suspension rows and three zero-volume ORBIS sessions. Strict every-WIG-session 252-bar readiness is 98,517/99,780 (98.7342%); the 1,263 ineligible windows are listing-age, no-reference/non-trading, or post-exit limitations rather than acquisition requests.

For a future rebuilt experiment, the recommended evaluation start is **2019-12-23**, the first complete-PIT TOP60 date, with feature-specific eligibility retained. Only 58/60 members pass the deliberately conservative every-session 252-bar test on that first date; delaying to the first incidental 60/60 strict date (2022-05-26) would discard more than two years and would not solve later listing-age eligibility.

Price coverage and complete OHLCV coverage must remain distinct. PLAY on 2020-06-03 and CCC on 2020-06-10 have selected Investing price bars with blank displayed volume. The retained Yahoo PLAY history contains a complete matching whole bar, but no accepted alternate CCC raw-volume bar was established. No field was spliced and no bar was synthesized.

This changes the observation-acquisition gate from **FAIL** to **PASS for prices**. It does not change the overall rebuild decision below: authoritative split-event coverage, per-series/event adjustment state, and a validated derived split-adjusted OHLC/volume view are still required before a replacement Phase A run.

## Superseded 2026-08-26 pre-enrichment warm-up addendum

The earlier coverage pass below begins at the accepted Phase A evaluation start, 2020-11-27. The official membership reference supports complete PIT TOP60 semantics earlier, from **2019-12-23**. Extending the coverage contract to that date and requiring the immediately preceding 252 WIG sessions changes the acquisition result: existing Bossa+Investing data lack direct official observations for PLAY and ORBIS and lack Stooq-evidenced warm-up history for BNPPPL, DEVELIA, and CYBERFLKS. Exactly **five** additional Investing.com histories are needed for the expanded contract. See `GPW_TOP60_DEC2019_WARMUP_AUDIT.md` for the bounded spans, residual listing/no-trade states, immutable run, and byte-identical reproduction.

This pre-enrichment acquisition result is retained for audit history and is superseded by the targeted update above. It does not change the separate conditional approval to implement source/native ingestion and split normalization.

## Decision

**The proposed layered design is the correct target architecture, but an accepted replacement Phase A rebuild is NOT READY today.**

Two narrower statements do pass:

1. **Observation coverage: PASS.** Bossa plus the existing Investing.com histories cover every Stooq-covered official TOP60 member-session in the accepted Phase A evaluation interval. They also cover every other expected official row except eight explicitly classified non-trading rows.
2. **Source/native panel construction: READY WITH CAVEATS.** It is possible to select one complete source-native bar per security/session using Bossa first and Investing.com only where Bossa is absent, while retaining source and display precision.

The replacement research panel remains gated because source-native split treatment is not uniform. Bossa is demonstrably mixed across the tested splits, and Investing.com is demonstrably split-adjusted for BLOOBER even though the cash-dividend controls behave like unadjusted displayed prices relative to Stooq. A complete authoritative split ledger and a fail-closed per-series/event normalization map are therefore required before split-adjusted features can be trusted. ATS total returns additionally require cash-distribution and other economic corporate-action data and are not yet proven.

## Required data flow

```text
SOURCE OBSERVATIONS
├── Bossa          -> primary source-native OHLCV
├── Investing.com  -> supplemental source-native/display OHLCV
├── Yahoo Finance  -> tertiary, only for accepted clean WSE histories
└── Stooq          -> independent adjusted reference; never a raw fallback

DERIVED ATS DATA
├── source/native OHLCV
├── split-adjusted OHLC
├── split-adjusted volume
├── raw price returns
└── eventually ATS total returns
```

The term `source/native` means exactly what the selected vendor currently stores. It must not be interpreted as `raw_through_splits`. The term `raw price return` in this design means a **split-neutral price-only return with no cash distribution reinvestment**. It must be computed from the validated split-adjusted close, not blindly from the source-native close. A less ambiguous implementation name would be `price_return_no_distributions`.

## Coverage evidence

The official evaluation grid contains 1,430 sessions from 2020-11-27 through 2026-08-18 and preserves exactly 60 official members per session. The 2019-01-01 boundary is the warm-up start.

| Measure | Member-sessions | Result |
|---|---:|---|
| Official denominator | 85,800 | fixed at 60 per session |
| Stooq-covered observations | 83,836 | comparison denominator |
| Bossa `mstall` | 79,415 | source-native observations |
| Bossa page supplements | 85 | retained separately from `mstall` histories |
| Bossa after page supplements | 79,500 | 94.8280% of Stooq-covered rows |
| Existing Investing.com supplements | 6,292 | used only where Bossa is absent |
| Bossa + Investing expected observations | 85,792 | all except eight legitimate no-bar rows |
| Bossa + Investing where Stooq is covered | 83,836 | **100%** |
| Unexplained raw-source gaps versus Stooq | 0 | **PASS** |

The Investing.com supplement is required for nine identity chains:

| Security identity | Supplemented member-sessions |
|---|---:|
| SANPL / ERSTEPL | 1,349 |
| CCC / MODIVO | 1,304 |
| CIECH | 714 |
| COMARCH | 977 |
| LOTOS | 417 |
| LIVECHAT / TEXT | 706 |
| PGNIG | 482 |
| STSHOLDING | 239 |
| TIM | 104 |

The eight uncovered official rows are legitimate no-bar rows, not unexplained source gaps: LOTOS on 2022-07-29, 2022-08-01, 2022-08-02, and 2022-08-03; and PGNIG on 2022-10-31, 2022-11-02, 2022-11-03, and 2022-11-04. Stooq also has no bars on those rows. No bars may be synthesized.

## Split-treatment forensics

The event dates and ratios below were supplied as the official ground truth. Each comparison uses 20 matched sessions before and 20 matched sessions after the event in both local Bossa and Stooq histories.

| Security | Split/date | Last pre -> first post close | Bossa treatment | Stooq treatment | Confidence |
|---|---|---|---|---|---|
| SUNEX | 1:5, 2020-09-15 | Bossa 5.00 -> 6.26; Stooq 4.85522 -> 6.07876 | split-adjusted price and volume | split-adjusted price and volume | high |
| BLOOBER | 1:10, 2021-03-18 | Bossa 193.40 -> 20.20; Stooq 19.34 -> 20.20 | raw through the split | split-adjusted price and volume | high |
| CASPAR | 1:5, 2021-11-04 | Bossa 79.00 -> 15.60; Stooq 13.4464 -> 13.2762 | raw through the split | split-adjusted price and volume | high |

The ordinary-session cross-source ratios make the classifications mechanical rather than dependent on normal market movement:

| Security | Bossa/Stooq close ratio before -> after | Bossa/Stooq volume ratio before -> after | Diagnostic |
|---|---:|---:|---|
| SUNEX | 1.029818 -> 1.029814 | 0.971053 -> 0.971051 | no factor-of-five step; same split treatment |
| BLOOBER | 10.0 -> 1.0 | 0.1 -> 1.0 | exact reciprocal factor-of-ten step |
| CASPAR | 5.875145 -> 1.175029 | 0.1702085 -> 0.8510425 | exact factor-of-five step around a separate persistent scale factor |

Therefore:

- **Bossa:** `mixed_or_other`. It is not suitable as-is for technical time-series features across splits.
- **Stooq:** `split_adjusted_price_and_volume` for all three tested events.
- **Bossa requirement:** ATS needs a derived split-adjusted price and volume view. The transformer must apply an event only when the source-native history is proven unadjusted for that event; otherwise it risks double adjustment.

### Investing.com BLOOBER control

The supplied Investing.com BLOOBER history covers 2020-01-02 through 2026-08-25 with 1,665 unique valid rows. Around the 1:10 split:

| Source | 2021-03-17 close / volume | 2021-03-18 close / volume | Pre/post close ratio |
|---|---:|---:|---:|
| Investing.com | 19.34 / 22,490 | 20.20 / 78,340 | 0.957426 |
| Stooq | 19.34 / 22,490 | 20.20 / 78,336 | 0.957426 |
| Bossa | 193.40 / 2,249 | 20.20 / 78,336 | 9.574257 |

Across the same 20+20 session window, Investing.com prices equal Stooq exactly on all 40 sessions. Every displayed Investing.com volume agrees with Stooq within the declared `K` display-rounding tolerance of plus or minus five shares. Before the split, median Investing/Bossa ratios are 0.1 for close and 10.0 for volume; after it, both are 1.0.

**Investing.com BLOOBER classification:** `split_adjusted_price_and_volume`, high confidence.

This is a split-only conclusion. The existing ORLEN, KGHM, and mBank controls show that Investing.com remains on the displayed/unadjusted cash-dividend basis while Stooq applies backward price and reciprocal volume scaling around checked cash distributions. Investing.com must therefore be described as **source-native with mixed corporate-action semantics**, not globally raw and not globally total-return adjusted. One BLOOBER event does not prove the split convention for every Investing.com security.

## Canonical contracts required before the rebuild

### 1. Source/native OHLCV

Select exactly one complete bar, never individual fields:

1. validated Bossa `mstall`;
2. validated Bossa session-page supplement;
3. validated Investing.com history;
4. accepted clean Yahoo WSE history;
5. otherwise explicit missing state.

Stooq is excluded from this selection. Degraded historical Yahoo symbols are also excluded unless an explicit row-level whole-bar policy is separately approved. Every selected observation must retain `security_id`, validity-aware vendor identifier, session, source file/hash, source, source precision, acquisition method, and quality flags. Investing.com display-rounded volume must remain visibly rounded; it is unsuitable for exact execution/accounting reconciliation.

### 2. Corporate-action ledger

Create a versioned, authoritative event table before deriving split-adjusted bars. At minimum it must contain immutable security identity, event type, effective/ex-session date, ratio, source, announcement/availability timestamp, revision, and evidence hash. Split events must not be inferred from Stooq ratios or price jumps.

For each selected source series and event, record one of:

- `source_unadjusted_for_event`;
- `source_already_adjusted_for_event`;
- `not_applicable`;
- `unknown`.

`unknown` must fail the derived split-adjusted view for the affected history. A vendor-level global flag is invalid because Bossa is already proven mixed.

### 3. Split-adjusted OHLC and volume

For a 1:N split, pre-event unadjusted OHLC is divided by N and pre-event volume is multiplied by N. Already-adjusted source history is passed through. The transformation must preserve the native observation separately and record event IDs, cumulative factor, transformation version, input manifest, and output hashes. It must be idempotent and reject double application.

### 4. Price-only returns

Compute price-only returns from the validated split-adjusted close. These returns intentionally include the ex-cash-dividend price drop and exclude dividend reinvestment. They are not interchangeable with the accepted Stooq-based Phase A return labels or momentum without an explicit change of research basis.

### 5. ATS total returns

Total returns require authoritative cash dividends and any economically relevant rights, spin-offs, mergers, takeover cash, or similar terms, with point-in-time availability. This layer is future work. It must be derived independently and reconciled to Stooq as a control; Stooq factors must not become the action authority.

## Phase A rebuild gate

| Gate | Status | Evidence or remaining work |
|---|---|---|
| Official TOP60 denominator and PIT identity | PASS | existing accepted 60-member/session grid and validity-aware aliases |
| Expected source observation coverage | PASS | 85,792 expected bars; eight explicit legitimate no-bar rows |
| Whole-bar Bossa-first selection | PASS AS A SPECIFICATION | measured coverage and no Stooq fallback; implementation/publication not performed here |
| Source provenance and rounded-volume visibility | PASS WITH CAVEATS | manual Investing acquisition and display precision remain explicit |
| Uniform native split semantics | FAIL | Bossa is mixed; Investing is not globally characterized |
| Complete authoritative split ledger for the full warm-up/evaluation universe | NOT PROVEN | only three supplied split events were tested |
| Derived split-adjusted OHLC/volume implementation | NOT IMPLEMENTED | required before technical features |
| Independent split golden/adversarial tests | NOT IMPLEMENTED | must cover adjusted, unadjusted, unknown, and double-application cases |
| Price-only Phase A semantics accepted | OWNER DECISION REQUIRED | differs economically from the existing Stooq-adjusted research basis around cash distributions |
| ATS total-return inputs and derivation | NOT PROVEN | cash distributions and other economic actions remain incomplete |
| Replacement Phase A reproducibility and comparison | NOT RUN | requires a pinned derived-data manifest and fresh immutable run |

## Proceed / do not proceed

**Proceed now with:**

- the immutable source/native observation layer;
- the authoritative split-event inventory;
- per-series/event source-treatment classification;
- a versioned split-adjusted OHLC and volume derivation;
- independent controls against Stooq and hand-calculated split fixtures.

**Do not yet:**

- treat Bossa as globally raw through splits;
- treat Investing.com as globally raw or globally adjusted;
- compute technical features directly from source-native OHLCV across split boundaries;
- use Stooq as a silent fallback or infer authoritative actions from its factors;
- call a split-adjusted price-only run a reproduction of the accepted Stooq Phase A;
- replace the accepted Phase A or publish a new canonical Phase B version.

After the complete split inventory and derived-view validation pass, a **new, explicitly named Phase A price-only variant** may be run for comparison. A semantically comparable replacement for economic momentum and forward investor-return labels should wait for the ATS total-return layer, unless the owner explicitly approves price-only returns as a changed research question.

## Verification evidence

- Accepted coverage run: `D:\Stock\data\ATS\raw_price_coverage_audit\runs\gpw-raw-price-coverage-20260824-v6`
- Coverage manifest SHA-256: `6DF5BB230813A3663475DC14F1B4735EE9EB245D48CF7A01032F2D4A73DF1DA1`
- Investing.com BLOOBER attachment SHA-256: `9815E18A16D2F2B4D33AB287DBAA11886EE62C6085665C6883ED144061DBCC06`
- Bossa SHA-256: SUNEX `F681A11B691379E1536B9827A4E2DD0DD34256693AE695D2EE8741A49DAEF7A3`; BLOOBER `2CB5031F06732278A17319FBABE67A30BDD714DD27EE5524DFE5CD41F2749368`; CASPAR `A3DF547044E8DF95BC7D79E73EAB95B3BB2FE28A421C6C7B5B7FFF0C6C505574`
- Stooq SHA-256: SNX `1E9C3BC7AF36DD3C6F5991BD5DB4C9EA73050B1978C80C604E8A6FCEA3BDCE5F`; BLO `236DAB27D2CCB750AE8D17CAB76A380F5ADFC7A0F5FE28F6C74977F00E36DEC4`; CSR `2568FCCFA2DF3161331FD0B3C878246F2F4674FD752AD24798989C429A502BE0`

The BLOOBER attachment is split-control evidence only. It was not copied into a source/reference or canonical dataset and is not part of the nine-security Investing supplement used by the coverage audit.

No source data, canonical dataset, Phase A/B/C implementation, or run artifact was changed by this checkpoint; only reports and planning documentation were updated.

**Phase A replacement rebuild readiness: NOT READY**  
**Bounded source/native plus split-normalization implementation readiness: CONDITIONAL GO**
