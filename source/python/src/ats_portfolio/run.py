from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any

import pandas as pd

from ats_contracts.portfolio import (
    ArtifactRecord,
    CorporateActionInput,
    LEDGER_MANIFEST_VERSION,
    LedgerRunManifest,
    PORTFOLIO_CONTRACT_VERSION,
    SecurityEventInput,
    TargetWeightIntent,
)
from ats_data.discovery import manifest_files
from ats_data.publication import validate_manifest as validate_phase_b_manifest
from ats_portfolio.config import PortfolioConfig
from ats_portfolio.engine import DailyPortfolioEngine, EngineResult
from ats_portfolio.hashing import file_hash, manifest_hash, object_hash
from ats_portfolio.market import MARKET_FIELD_TIMING_POLICY, MarketBar
from ats_portfolio.numeric import NUMERIC_POLICY
from ats_portfolio.storage import write_intents, write_ledger


IMPLEMENTATION_ROOTS = (
    "source/python/src/ats_portfolio",
    "source/python/src/ats_contracts/portfolio.py",
    "source/python/src/ats_contracts/__init__.py",
    "source/python/pyproject.toml",
)


def _read_models(path: Path | None, model: type[Any]) -> list[Any]:
    if path is None:
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"input must be a JSON list: {path}")
    return [model.model_validate(row) for row in raw]


def load_inputs(config: PortfolioConfig) -> tuple[list[TargetWeightIntent], list[SecurityEventInput], list[CorporateActionInput]]:
    return (
        _read_models(config.intents_file, TargetWeightIntent),
        _read_models(config.security_events_file, SecurityEventInput),
        _read_models(config.corporate_actions_file, CorporateActionInput),
    )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def implementation_provenance() -> dict[str, Any]:
    repo = _repo_root()
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    files: list[Path] = []
    for relative in IMPLEMENTATION_ROOTS:
        path = repo / relative
        if path.is_dir():
            files.extend(sorted(path.rglob("*.py")))
        else:
            files.append(path)
    hashes = {path.relative_to(repo).as_posix(): file_hash(path) for path in files}
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", *IMPLEMENTATION_ROOTS],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return {"commit": commit, "clean": not bool(status), "status_porcelain": status, "code_file_sha256": hashes}


def environment_lock() -> dict[str, str]:
    packages = ["numpy", "pandas", "polars", "pyarrow", "pydantic", "PyYAML", "duckdb", "pytest", "hypothesis"]
    lock = {"python": sys.version, "platform": platform.platform()}
    for package in packages:
        try:
            lock[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            lock[package] = "not-installed"
    return dict(sorted(lock.items()))


def _load_market(config: PortfolioConfig) -> tuple[list[MarketBar], set[str], str]:
    manifest = validate_phase_b_manifest(config.phase_b_manifest)
    pieces = [pd.read_parquet(path) for path in manifest_files(config.phase_b_manifest, "bars")]
    frame = pd.concat(pieces, ignore_index=True)
    if config.start_session:
        frame = frame.loc[pd.to_datetime(frame["session_date"]).dt.date >= config.start_session]
    if config.end_session:
        frame = frame.loc[pd.to_datetime(frame["session_date"]).dt.date <= config.end_session]
    frame = frame.sort_values(["session_date", "security_id", "source", "adjustment_version"], kind="mergesort")
    bars = [
        MarketBar(
            security_id=str(row.security_id),
            session_date=pd.Timestamp(row.session_date).date(),
            event_ts=pd.Timestamp(row.event_ts).to_pydatetime(),
            available_ts=pd.Timestamp(row.available_ts).to_pydatetime(),
            open=row.open if pd.notna(row.open) else None,
            close=row.close if pd.notna(row.close) else None,
            currency=str(row.currency),
            market=str(row.market),
            source=str(row.source),
            source_record_id=str(row.source_record_id),
            adjustment_state=str(row.adjustment_state),
            adjustment_version=str(row.adjustment_version),
        )
        for row in frame.itertuples(index=False)
    ]
    security_parts = [pd.read_parquet(path, columns=["security_id"]) for path in manifest_files(config.phase_b_manifest, "security_master")]
    known = set(pd.concat(security_parts, ignore_index=True)["security_id"].astype(str))
    return bars, known, manifest.dataset_version_id


def _input_hashes(config: PortfolioConfig) -> tuple[dict[str, str], dict[str, str]]:
    inputs = {"intents": file_hash(config.intents_file)}
    events: dict[str, str] = {}
    if config.security_events_file:
        events["security_events"] = file_hash(config.security_events_file)
    if config.corporate_actions_file:
        events["corporate_actions"] = file_hash(config.corporate_actions_file)
    return inputs, events


def run_identity(config: PortfolioConfig, config_path: Path, phase_b_id: str) -> tuple[str, dict[str, Any]]:
    inputs, events = _input_hashes(config)
    implementation = implementation_provenance()
    lock = environment_lock()
    payload = {
        "config": config.identity_dict(),
        "config_sha256": file_hash(config_path),
        "phase_b_manifest_id": phase_b_id,
        "phase_b_manifest_sha256": file_hash(config.phase_b_manifest),
        "input_hashes": inputs,
        "event_hashes": events,
        "contract_versions": {"portfolio": PORTFOLIO_CONTRACT_VERSION, "manifest": LEDGER_MANIFEST_VERSION},
        "implementation_provenance": implementation,
        "environment_lock_hash": object_hash(lock),
        "numeric_policy": NUMERIC_POLICY,
        "market_field_timing_policy": MARKET_FIELD_TIMING_POLICY,
        "calendar": config.calendar,
        "cost_model": {"commission_bps": str(config.commission_bps), "slippage_bps": str(config.slippage_bps)},
        "seed": config.seed,
    }
    return f"phasec-{object_hash(payload)[:20]}", payload


def _copy_inputs(stage: Path, config: PortfolioConfig, config_path: Path) -> None:
    shutil.copyfile(config_path, stage / "config.yaml")
    inputs = stage / "inputs"
    inputs.mkdir(parents=True)
    shutil.copyfile(config.phase_b_manifest, inputs / "phase_b_manifest.json")
    shutil.copyfile(config.intents_file, inputs / "intents.json")
    if config.security_events_file:
        shutil.copyfile(config.security_events_file, inputs / "security_events.json")
    if config.corporate_actions_file:
        shutil.copyfile(config.corporate_actions_file, inputs / "corporate_actions.json")


def _artifact_records(stage: Path, logical_hashes: dict[str, str]) -> tuple[ArtifactRecord, ...]:
    records: list[ArtifactRecord] = []
    for path in sorted(item for item in stage.rglob("*") if item.is_file() and item.name != "manifest.json"):
        relative = path.relative_to(stage).as_posix()
        rows = 0
        if relative.startswith("ledgers/") and path.suffix == ".csv":
            with path.open("r", encoding="utf-8") as handle:
                rows = max(0, sum(1 for _line in handle) - 1)
        records.append(
            ArtifactRecord(
                path=relative,
                bytes=path.stat().st_size,
                physical_sha256=file_hash(path),
                logical_sha256=logical_hashes.get(relative, file_hash(path)),
                rows=rows,
                schema_version=PORTFOLIO_CONTRACT_VERSION if relative.startswith("ledgers/") else "bytes.v1",
            )
        )
    return tuple(records)


def _write_manifest(stage: Path, config: PortfolioConfig, run_id: str, phase_b_id: str, payload: dict[str, Any], logical_hashes: dict[str, str]) -> LedgerRunManifest:
    value: dict[str, Any] = {
        "manifest_schema_version": LEDGER_MANIFEST_VERSION,
        "run_id": run_id,
        "status": "completed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "phase_b_manifest_id": phase_b_id,
        "phase_b_manifest_path": config.phase_b_manifest.resolve().as_posix(),
        "phase_b_manifest_sha256": payload["phase_b_manifest_sha256"],
        "config_sha256": payload["config_sha256"],
        "input_hashes": payload["input_hashes"],
        "event_hashes": payload["event_hashes"],
        "contract_versions": payload["contract_versions"],
        "implementation_provenance": payload["implementation_provenance"],
        "environment_lock_hash": payload["environment_lock_hash"],
        "numeric_policy": payload["numeric_policy"],
        "market_field_timing_policy": payload["market_field_timing_policy"],
        "calendar": payload["calendar"],
        "cost_model": payload["cost_model"],
        "seed": payload["seed"],
        "artifacts": [record.model_dump(mode="json") for record in _artifact_records(stage, logical_hashes)],
        "logical_hashes": logical_hashes,
        "manifest_hash": "",
    }
    value["manifest_hash"] = manifest_hash(value)
    path = stage / "manifest.json"
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return LedgerRunManifest.model_validate(value)


def publish_run(config: PortfolioConfig, config_path: Path, output_root: Path | None = None) -> Path:
    bars, known, phase_b_id = _load_market(config)
    intents, security_events, corporate_actions = load_inputs(config)
    run_id, payload = run_identity(config, config_path, phase_b_id)
    root = (output_root or (config.phase_root / "runs")).resolve()
    destination = root / run_id
    if destination.exists():
        raise FileExistsError(f"immutable run already exists: {destination}")
    staging_root = config.phase_root / "staging"
    staging_root.mkdir(parents=True, exist_ok=True)
    stage = staging_root / f"{run_id}-{uuid.uuid4().hex[:8]}"
    stage.mkdir(parents=False, exist_ok=False)
    _copy_inputs(stage, config, config_path)
    lock = environment_lock()
    (stage / "environment_lock.json").write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    engine = DailyPortfolioEngine(
        config=config,
        run_id=run_id,
        bars=bars,
        intents=intents,
        known_security_ids=known,
        data_manifest_id=phase_b_id,
        data_manifest_path=config.phase_b_manifest.resolve().as_posix(),
        data_manifest_sha256=file_hash(config.phase_b_manifest),
        security_events=security_events,
        corporate_actions=corporate_actions,
    )
    result = engine.run()
    ledgers = stage / "ledgers"
    logical_hashes: dict[str, str] = {}
    logical_hashes["ledgers/intents.csv"] = write_intents(ledgers / "intents.csv", intents)
    for name, rows in result.ledgers().items():
        relative = f"ledgers/{name}.csv"
        logical_hashes[relative] = write_ledger(ledgers / f"{name}.csv", name, rows)
    ending = result.portfolio_snapshots[-1]
    metrics = {
        "warning": "Accounting reconciliation checksum only; not alpha or investment evidence.",
        "sessions": len(result.portfolio_snapshots),
        "orders": len(result.orders),
        "fills": len(result.fills),
        "ending_cash": str(ending.cash),
        "ending_equity_checksum": str(ending.equity) if ending.equity is not None else None,
        "ending_valuation_status": ending.valuation_status,
    }
    (stage / "metrics.json").write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    from ats_portfolio.validation import validate_run

    _write_manifest(stage, config, run_id, phase_b_id, payload, logical_hashes)
    first_report = validate_run(stage, require_directory_identity=False)
    first_report["artifact_count"] += 1  # account for the report itself in the final artifact set
    (stage / "validation_report.json").write_text(json.dumps(first_report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_manifest(stage, config, run_id, phase_b_id, payload, logical_hashes)
    validate_run(stage, require_directory_identity=False)
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.replace(stage, destination)
    validate_run(destination)
    return destination
