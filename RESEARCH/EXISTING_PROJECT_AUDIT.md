# Existing Project and Data Audit

## Scope and preservation

The audit read `D:\Stock\data` and existing ATS/research material without writing to it. All generated artifacts are confined to `D:\Stock\ATS\RESEARCH`. No existing Conda environment was changed.

## Source-data inventory

The source tree contains approximately 45,310 text files (about 4.67 GiB), of which approximately 38,942 are non-empty. The observed directory counts are:

| Segment | Files | Approx. size |
|---|---:|---:|
| Daily GPW (`daily/pl`) | 19,603 | 1.40 GB |
| Daily US (`daily/us`) | 15,355 | 2.04 GB |
| Daily world (`daily/world`) | 2,533 | 1.09 GB |
| Daily macro (`daily/macro`) | 826 | 0.01 GB |
| Hourly GPW (`hourly/pl`) | 6,993 | 0.13 GB |

Existing membership, identity mapping, unresolved-member, and corporate-exit research was reused. The TOP60 point-in-time study starts on **2020-11-27**. Five established benign exit classifications are preserved: LOTOS, PGNiG, STS, CIECH, and TIM. They are not silently converted into missing-price failures.

The reproducible TOP60 builder produced:

- 161,289 local price observations from the 2019 warm-up onward.
- 1,880 validity-dated membership rows covering 94 membership securities.
- 89 securities with local price histories.
- 45 unresolved membership rows retained explicitly.
- 83,836 eligible point-in-time research rows after membership/price alignment.

Unresolved identifiers remain records with provenance and status. They are not dropped merely to make a join complete.

## The existing `stocks.parquet` control

`D:\Stock\data\stocks.parquet` contains:

| Property | Value |
|---|---:|
| Rows | 69,635,916 |
| Securities/ticker strings | 27,662 |
| Row groups | 567 |
| Compressed bytes | 1,092,744,797 |
| Columns | `ticker`, `date`, `open`, `high`, `low`, `close`, `volume` |
| Observed date range | 1789-05-01 through 2025-12-31 |

This file is valuable as a performance control: it is compact, already normalized enough for broad OHLCV scans, and represents the full 69.6M-row workload. It is not suitable as the canonical store because a ticker alone is not a stable security identity and its schema lacks:

- venue/MIC, market and frequency;
- event and availability timestamps;
- source/vendor and ingestion version;
- adjustment state and corporate-action lineage;
- currency, optional turnover and session identity;
- validity-dated identifiers and collision handling;
- revision/correction provenance.

The extreme historical minimum date also requires source-specific quality flags rather than global clipping. A canonical system must distinguish a genuine long historical series from a malformed vendor date.

## Data-quality and identity risks

The highest correctness risk is not file format; it is point-in-time identity and availability.

1. Tickers can be reused, renamed, venue-qualified differently, or collide across markets.
2. Index membership is interval data. A current constituent list cannot be backfilled into history.
3. Close-derived signals only become executable on a later eligible bar. `event_ts` and `available_ts` are different concepts.
4. Delistings, mergers and cash takeovers must not be represented as ordinary missing bars.
5. Vendor-adjusted prices require an explicit adjustment version and raw-value lineage.
6. Macro observations need release/availability timestamps; observation dates alone create revision and look-ahead bias.

## Canonical contract gaps to close

The implementation should introduce a stable `security_id` and separate validity-dated alias/listing table before converting all history. Bars should be unique on the semantic key `(security_id, event_ts, frequency, source, adjustment_version)`. Ingestion should fail closed on schema drift, duplicate semantic keys, invalid OHLC relationships, negative volume, or `available_ts > decision_ts` violations.

Raw vendor files remain immutable. Canonical Parquet versions are reproducible transformations with source checksums and code fingerprints. Derived feature matrices and wide research panels are disposable caches, never replacements for the normalized canonical facts.
