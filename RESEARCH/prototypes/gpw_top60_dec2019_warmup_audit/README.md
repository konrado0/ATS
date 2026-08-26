# GPW TOP60 December-2019 warm-up audit

This read-only audit identifies the first complete PIT TOP60 boundary in December 2019 and measures Bossa-first/Investing-then-Yahoo-supplemented source-native price coverage plus a strict 252-WIG-session prehistory for every official member-session through the accepted Phase A comparison endpoint.

Contract:

- complete PIT start: `2019-12-23`;
- endpoint: `2026-08-18`;
- denominator: exactly 60 official WIG20+mWIG40 members per WIG session;
- strict warm-up: the immediately preceding 252 WIG sessions, excluding the member-session;
- source priority: Bossa `mstall`, Bossa session-page supplement, Investing.com, accepted clean Yahoo WSE histories, explicit missing;
- degraded Yahoo PLAY/ORBIS histories: overlap and non-trading evidence only, never selected;
- targeted ORBIS suspension/non-trading classifications: pinned in `targeted_nontrading_events.json`;
- membership completeness boundary: pinned in `membership_completeness_assertion.v1.json` and hash-validated before the grid is accepted;
- Stooq: independent gap/expected-trading reference only, never selected into the source/native panel.

The corrected denominator is independent of source coverage: official member-sessions minus independently established non-trading/suspension sessions define expected trading. Selected-source presence is joined only after that classification.

Run into a new empty output directory:

```powershell
& 'D:\Stock\ATS\RESEARCH\prototypes\environment_repair\invoke_repaired_python.ps1' `
  'D:\Stock\ATS\RESEARCH\prototypes\gpw_top60_dec2019_warmup_audit\audit_dec2019_warmup.py' `
  --data-root 'D:\Stock\data' `
  --bossa-root 'D:\Stock\data\mstall' `
  --bossa-session-root 'D:\Stock\data\mstall\session_supplements\manual_page_copy_2026-08-24' `
  --investing-root 'D:\Stock\data\reference\investing.com' `
  --yahoo-root 'D:\Stock\data\raw\yahoo_finance\gpw\daily\acquisition_2026-08-26' `
  --targeted-events 'D:\Stock\ATS\RESEARCH\prototypes\gpw_top60_dec2019_warmup_audit\targeted_nontrading_events.json' `
  --membership-assertion 'D:\Stock\ATS\RESEARCH\prototypes\gpw_top60_dec2019_warmup_audit\membership_completeness_assertion.v1.json' `
  --endpoint '2026-08-18' `
  --output '<new-empty-output-directory>'
```

The corrected immutable primary output is:

`D:\Stock\data\ATS\top60_dec2019_warmup_audit\runs\top60-dec2019-warmup-20260826-v9-corrected`

The byte-identical reproduction is:

`D:\Stock\data\ATS\top60_dec2019_warmup_audit\runs\top60-dec2019-warmup-20260826-v9-corrected-reproduction`

The accepted v8 audit remains unchanged and retained. v9 corrects its circular expected-trading definition while reconciling to the same empirical 99,721/99,721 result. Runs `v1` through `v7` are retained superseded diagnostic attempts.

Outputs:

- `metrics.json`: contract, totals, membership boundary, warm-up states, and required histories;
- `member_session_audit.csv`: one row per official member/session with source selection and warm-up counts;
- `warmup_missing_detail.csv`: one row per member-session/required-history-session gap;
- `security_summary.csv`: security-level coverage and warm-up summary;
- `additional_histories_needed.csv`: the bounded acquisition list;
- `bossa_identity_map.csv`: Bossa identity selection evidence;
- `manifest.json`: script, input, output, byte-length, and SHA-256 evidence.

The script refuses to overwrite an existing output directory and pins the accepted endpoint. It does not import, call, or mutate Phase A runs.
