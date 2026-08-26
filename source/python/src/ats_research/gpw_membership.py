from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd


ASSERTION_SCHEMA = "ats.gpw_membership_completeness.v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_membership_assertion(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != ASSERTION_SCHEMA:
        raise ValueError("unsupported GPW membership completeness assertion schema")
    return payload


def validate_membership_assertion(
    assertion_path: Path,
    reference_root: Path,
    official_grid: pd.DataFrame,
) -> dict[str, Any]:
    """Validate the pinned evidence and fail-closed completeness boundary."""
    assertion = load_membership_assertion(assertion_path)
    boundary = assertion["inclusive_completeness_interval"]
    asserted_start = pd.Timestamp(boundary["start"])
    asserted_end = pd.Timestamp(boundary["end"])

    if official_grid.empty:
        raise ValueError("official membership grid is empty")
    required = {"session_date", "source_index", "isin", "effective_from"}
    missing = required - set(official_grid.columns)
    if missing:
        raise ValueError(f"membership grid missing columns: {sorted(missing)}")

    grid = official_grid.copy()
    grid["session_date"] = pd.to_datetime(grid["session_date"], errors="raise")
    grid["effective_from"] = pd.to_datetime(grid["effective_from"], errors="raise")
    actual_start = grid["session_date"].min()
    actual_end = grid["session_date"].max()
    if actual_start < asserted_start:
        raise ValueError("membership request begins before asserted completeness boundary")
    if actual_end > asserted_end:
        raise ValueError("membership request ends after asserted completeness endpoint")

    expected_counts = assertion["expected_role_counts_per_session"]
    role_counts = (
        grid.groupby(["session_date", "source_index"], sort=True)
        .size()
        .unstack(fill_value=0)
    )
    for role, expected in expected_counts.items():
        if role not in role_counts or not role_counts[role].eq(int(expected)).all():
            raise ValueError(f"membership role count failure for {role}")
    unexpected_roles = set(role_counts.columns) - set(expected_counts)
    if unexpected_roles:
        raise ValueError(f"unexpected membership roles: {sorted(unexpected_roles)}")

    semantic_keys = ["session_date", "source_index", "isin"]
    if grid.duplicated(semantic_keys).any():
        raise ValueError("duplicate membership semantic keys")
    overlap = grid.groupby(["session_date", "isin"], sort=True)["source_index"].nunique()
    if overlap.gt(1).any():
        raise ValueError("identity overlaps WIG20 and mWIG40 on the same session")
    total_expected = sum(int(value) for value in expected_counts.values())
    per_session = grid.groupby("session_date").agg(rows=("isin", "size"), identities=("isin", "nunique"))
    if not per_session["rows"].eq(total_expected).all() or not per_session["identities"].eq(total_expected).all():
        raise ValueError("TOP60 membership denominator failure")

    evidence = assertion["authoritative_membership_inputs"]
    for item in evidence["files"]:
        source = reference_root / item["relative_path"]
        if not source.is_file() or sha256(source) != item["sha256"]:
            raise ValueError(f"membership evidence hash mismatch: {source}")

    snapshots = assertion["effective_snapshots"]
    seen_snapshot_keys: set[tuple[str, str]] = set()
    for item in snapshots:
        key = (str(item["role"]), str(item["effective_date"]))
        if key in seen_snapshot_keys:
            raise ValueError(f"duplicate assertion snapshot key: {key}")
        seen_snapshot_keys.add(key)
        source = reference_root / item["relative_path"]
        if not source.is_file() or sha256(source) != item["sha256"]:
            raise ValueError(f"membership snapshot hash mismatch: {source}")
        snapshot = pd.read_csv(source)
        expected = int(expected_counts[item["role"]])
        if len(snapshot) != expected or snapshot["isin"].nunique() != expected:
            raise ValueError(f"invalid complete membership snapshot: {source}")

    used = grid[["source_index", "effective_from"]].drop_duplicates()
    asserted = {(str(item["role"]), pd.Timestamp(item["effective_date"])) for item in snapshots}
    used_keys = {(str(row.source_index), pd.Timestamp(row.effective_from)) for row in used.itertuples(index=False)}
    if not used_keys.issubset(asserted):
        raise ValueError("official grid uses an unasserted effective snapshot")

    return {
        "schema_version": assertion["schema_version"],
        "asserted_start": str(asserted_start.date()),
        "asserted_end": str(asserted_end.date()),
        "validated_sessions": int(grid["session_date"].nunique()),
        "validated_member_sessions": len(grid),
        "validated_unique_identities": int(grid["isin"].nunique()),
        "assertion_sha256": sha256(assertion_path),
    }
