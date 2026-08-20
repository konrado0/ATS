# Phase B canonical data

Phase B hardens analytical facts without adding a storage service. Raw files remain evidence; exact Arrow contracts and immutable complete Parquet versions are the canonical analytical store. DuckDB catalogs and Polars frames are derived readers, never second canonical copies.

## Contracts and semantic keys

All canonical rows carry `schema_version=ats.canonical.v1`. PyArrow field order, types, nullability and version are exact and fail closed.

| Table | Semantic key |
|---|---|
| `security_master` | `security_id` |
| `security_aliases` | `security_id, identifier_type, identifier_value, venue_mic, vendor, valid_from` |
| `bars` | `security_id, event_ts, frequency, source, adjustment_version` |
| `universe_membership` | `universe_id, universe_component, raw_identifier, valid_from` |
| `security_events` | `event_id, revision` |
| `corporate_actions` | `action_id, revision` |
| `macro_series` | `series_id, event_ts, source, revision, vintage` |
| `lineage_records` | `dataset_version_id` |
| `dataset_manifests` | `dataset_version_id, table_name, file_path` |
| `ingestion_issues` | `source, source_record_id, issue_code` |

Resolved ticker/ISIN/vendor aliases may not overlap within a namespace. Multiple provisional U.S. candidates may overlap only while marked `provisional_source_scoped`; this retains ambiguity as evidence and does not adjudicate identity. Invalid intervals, duplicate keys, nonpositive prices, negative volume, inconsistent high/low, availability before event, unknown enums and schema/version drift fail publication.

GPW security IDs and mappings are reused from the trusted Phase A archive. The WIG index has a separate stable index identity. U.S. files have UUIDv5 identities scoped to the full raw Stooq source path. Every U.S. identity is explicitly provisional, `issuer_id` stays null, and duplicated ticker/venue files remain separate reconciliation candidates. No ISIN or ticker continuity is invented. Files without accepted bars remain in the master; malformed OHLCV records are retained in `ingestion_issues` rather than silently dropped.

## Timestamp semantics

Daily GPW `event_ts` preserves the Phase A modeled session close (17:00 Europe/Warsaw); `available_ts` preserves its conservative five-minute delay. U.S. daily rows model the session close at 16:00 America/New_York and availability at 16:05, stored as UTC. `session_date` is the local market session date. These are daily session semantics, not claims that the raw vendor supplied an exchange event timestamp.

Intraday contracts use the actual bar-end/event timestamp supplied or defensibly derived from the source and may apply a source-specific availability delay. They are not forced into the daily close model. Membership announcement and availability fields remain null when the trusted evidence lacks them.

## Physical and publication policy

The writer defaults are ZSTD level 3 and 122,880 rows per row group. Data is sorted deterministically and written as one or a few compact files per `(table, market, frequency)`. There are no ticker, security, year or month partitions. The 2 GiB configuration is a review prompt only; splitting must be justified by representative query/rebuild SLO failure or materially degraded maintenance.

Publication is stage → validate → atomic rename → safe discovery-pointer update. The version identity is derived from logical table hashes, source hashes, configuration, parent and reason. An existing version directory is never overwritten. Corrections and new data rebuild a complete version; there are no deltas or compaction. A failed stage cannot move a pointer, so the prior explicit manifest and its DuckDB views remain usable.

Every manifest lists exact Parquet paths, sizes, physical and logical hashes, rows, row groups, semantic keys, schema fingerprints/versions, timestamps, market/frequency, sources, writer settings, lineage, environment and Git provenance. DuckDB views use only this list with `union_by_name=false`. Polars scans set `glob=false` and reject discovery pointers.

Derived caches may be deleted only through a concrete child beneath `phase_b/cache`; canonical version paths and the cache root itself are rejected.

## Reference commands

```powershell
$python = 'C:\Users\konra\anaconda3\envs\ats-stack-research\python.exe'
$env:PYTHONPATH = 'D:\Stock\ATS\source\python\src'
& $python -m ats_research validate --run-dir 'D:\Stock\data\ATS\phase_a\runs\phasea-2a2b3898aba37814'
& $python -m ats_data validate --manifest 'D:\Stock\data\ATS\phase_b\versions\phaseb-dd0bb7a8679ab9c658e9\manifest.json'
& $python -m ats_data reconcile-gpw --config 'D:\Stock\ATS\source\python\configs\phase_b_reference.yaml' --manifest 'D:\Stock\data\ATS\phase_b\versions\phaseb-dd0bb7a8679ab9c658e9\manifest.json'
& $python -m ats_data validate --manifest 'D:\Stock\data\ATS\phase_b\versions\phaseb-1ffe35fd776b58a5df7c\manifest.json'
```

Archive-integrity Phase A validation uses the stored artifact hashes, source snapshot, environment lock and reconstructable commit. `--strict-current-checkout` adds an optional reproduction check against current files; normal source-tree evolution does not make an intact archive corrupt.
