from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


START = pd.Timestamp("2019-12-23")
END = pd.Timestamp("2026-08-18")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.reference_root.resolve()
    manifest = pd.read_csv(root / "manifest.csv")
    manifest["effective_date"] = pd.to_datetime(manifest["effective_date"], errors="raise")
    snapshots: list[dict[str, object]] = []
    for role, expected in (("WIG20", 20), ("mWIG40", 40)):
        role_rows = manifest.loc[manifest["index"].eq(role)].sort_values("effective_date")
        prior = role_rows.loc[role_rows["effective_date"].le(START)].tail(1)
        within = role_rows.loc[role_rows["effective_date"].between(START, END)]
        selected = pd.concat([prior, within]).drop_duplicates("effective_date").sort_values("effective_date")
        if selected.empty or pd.Timestamp(selected.iloc[0]["effective_date"]) > START:
            raise ValueError(f"no {role} snapshot effective at the assertion start")
        for row in selected.itertuples(index=False):
            path = root / str(row.file)
            frame = pd.read_csv(path)
            if len(frame) != expected or frame["isin"].nunique() != expected:
                raise ValueError(f"incomplete {role} snapshot: {path}")
            snapshots.append(
                {
                    "role": role,
                    "effective_date": pd.Timestamp(row.effective_date).date().isoformat(),
                    "relative_path": str(row.file).replace("\\", "/"),
                    "source_id": str(row.source_id),
                    "constituents": expected,
                    "sha256": sha256(path),
                }
            )

    evidence_files = []
    for relative in ("manifest.csv", "sources.csv", "README.md", "BUILD_REPORT.md"):
        path = root / relative
        evidence_files.append(
            {"relative_path": relative, "bytes": path.stat().st_size, "sha256": sha256(path)}
        )
    payload = {
        "schema_version": "ats.gpw_membership_completeness.v1",
        "assertion_version": "gpw-top60-completeness-20191223-20260818-v1",
        "inclusive_completeness_interval": {"start": str(START.date()), "end": str(END.date())},
        "roles": {
            "WIG20": "official large-cap component selected independently at each session",
            "mWIG40": "official mid-cap component selected independently at each session",
        },
        "expected_role_counts_per_session": {"WIG20": 20, "mWIG40": 40},
        "snapshot_semantics": {
            "effective_snapshot": "latest complete role snapshot whose effective_date is on or before the session",
            "change_event": "official extraordinary changes are materialized as new complete effective snapshots",
            "publication_date_is_not_effective_date": True,
        },
        "duplicate_and_overlap_rules": {
            "duplicate_key": ["session_date", "role", "isin"],
            "duplicate_key_allowed": False,
            "same_isin_in_both_roles_same_session_allowed": False,
            "conflicting_effective_snapshot_key_allowed": False,
        },
        "fail_closed_rules": [
            "request_before_start",
            "request_after_end",
            "role_count_not_20_or_40",
            "duplicate_or_conflicting_membership_key",
            "source_or_snapshot_hash_mismatch",
            "unasserted_snapshot_used",
        ],
        "authoritative_membership_inputs": {
            "authority": "GPW Benchmark historical portfolio and official announcement archives",
            "files": evidence_files,
        },
        "effective_snapshots": sorted(snapshots, key=lambda item: (item["effective_date"], item["role"])),
        "known_limitations": [
            "The assertion covers only WIG20 plus mWIG40 and only the stated inclusive interval.",
            "It establishes membership completeness, not price coverage, trading state, or corporate-action completeness.",
            "Source URLs and retained originals are registered by the hashed source registry and build report.",
        ],
    }
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
