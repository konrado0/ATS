from __future__ import annotations

import importlib.metadata
import io
import json
import platform
import shutil
import subprocess
import sys
import zipfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ats_research import __version__
from ats_research.artifacts import ArtifactWriter
from ats_research.bars import load_bar_data
from ats_research.config import PhaseAConfig, dump_config, load_config
from ats_research.diagnostics import compute_diagnostics
from ats_research.features.definitions import feature_specs
from ats_research.hashing import content_hash, hash_files, logical_manifest_hash
from ats_research.identity import build_identity_tables
from ats_research.labels.forward_returns import label_definitions
from ats_research.panel import build_panel
from ats_research.universe import load_exit_events, membership_intervals, session_membership


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return value.as_posix()
    return value


def _run_git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo_root, capture_output=True, text=True, check=False)


def _git_state(repo_root: Path, code_paths: list[Path]) -> dict[str, Any]:
    commit_result = _run_git(repo_root, "rev-parse", "HEAD")
    status_result = _run_git(repo_root, "status", "--porcelain=v1", "--untracked-files=normal")
    tracked_result = _run_git(repo_root, "ls-files", "source/python")
    commit = commit_result.stdout.strip() if commit_result.returncode == 0 else "unavailable"
    status = [line for line in status_result.stdout.splitlines() if line]
    tracked = {line.replace("\\", "/") for line in tracked_result.stdout.splitlines() if line}
    required = {path.relative_to(repo_root).as_posix() for path in code_paths}
    return {
        "commit": commit,
        "dirty": bool(status),
        "status_porcelain": status,
        "implementation_files_tracked": required.issubset(tracked),
        "untracked_implementation_files": sorted(required - tracked),
    }


def _package_versions() -> dict[str, str]:
    names = ["ats-research", "numpy", "pandas", "polars", "pyarrow", "pydantic", "PyYAML", "duckdb"]
    versions: dict[str, str] = {}
    for name in names:
        if name == "ats-research":
            versions[name] = __version__
            continue
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "not-installed"
    versions["python"] = platform.python_version()
    versions["platform"] = platform.platform()
    return versions


def _environment_lock() -> dict[str, Any]:
    distributions: dict[str, str] = {}
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name")
        if name:
            distributions[name.lower().replace("_", "-")] = distribution.version
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "packages": dict(sorted(distributions.items())),
        "project_version": __version__,
    }


def _project_paths() -> tuple[Path, Path]:
    project_root = Path(__file__).resolve().parents[2]
    repo_root = Path(__file__).resolve().parents[4]
    return project_root, repo_root


def _code_paths(project_root: Path) -> list[Path]:
    allowed_suffixes = {".py", ".toml", ".md", ".yaml", ".yml"}
    return sorted(
        path for path in project_root.rglob("*")
        if path.is_file() and path.suffix.lower() in allowed_suffixes
        and "__pycache__" not in path.parts and ".pytest_cache" not in path.parts
    )


def _source_snapshot(project_root: Path, code_paths: list[Path]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(code_paths, key=lambda item: item.relative_to(project_root).as_posix()):
            info = zipfile.ZipInfo(path.relative_to(project_root).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    return buffer.getvalue()


def _ensure_roots(config: PhaseAConfig) -> None:
    for child in ("datasets", "cache", "runs", "databases"):
        path = (config.phase_root / child).resolve()
        if not path.is_relative_to(config.output_root.resolve()):
            raise ValueError(f"generated path escapes output root: {path}")
        path.mkdir(parents=True, exist_ok=True)


def _progress(message: str) -> None:
    print(f"[ats-research] {message}", file=sys.stderr, flush=True)


def _source_inventory(config: PhaseAConfig, intervals: pd.DataFrame, bar_files: tuple[Path, ...]) -> dict[str, str]:
    reference = config.source_data_root / "reference" / "gpw_indices"
    fixed = [
        reference / "manifest.csv", reference / "stooq_symbol_map.csv", reference / "validation_issues.csv",
        config.source_data_root / "analysis" / "top60_exit_event_audit.csv",
    ]
    snapshot_files = [config.source_data_root / value for value in intervals["source_path"].drop_duplicates()]
    return hash_files([*fixed, *snapshot_files, *bar_files], config.source_data_root)


def execute_run(config: PhaseAConfig, destination_override: Path | None = None) -> Path:
    _ensure_roots(config)
    project_root, repo_root = _project_paths()
    code_paths = _code_paths(project_root)
    code_hashes = hash_files(code_paths, project_root)
    git_state = _git_state(repo_root, code_paths)
    environment_lock = _environment_lock()
    environment_lock_hash = content_hash(environment_lock)

    _progress("loading official membership and identity evidence")
    reference_root = config.source_data_root / "reference" / "gpw_indices"
    intervals = membership_intervals(reference_root, pd.Timestamp(config.start_date), pd.Timestamp(config.end_date))
    identities = build_identity_tables(intervals, reference_root / "stooq_symbol_map.csv", config.venue_mic)
    exits = load_exit_events(config.source_data_root / "analysis" / "top60_exit_event_audit.csv")
    _progress("loading and validating local GPW bars")
    bar_data = load_bar_data(config, identities.vendor_resolution)
    decision_sessions = bar_data.sessions.loc[
        bar_data.sessions.between(pd.Timestamp(config.start_date), pd.Timestamp(config.end_date))
    ]
    official = session_membership(intervals, decision_sessions, identities.vendor_resolution, exits)
    _progress("computing registered features, reference agreement, and labels")
    panel, features, _pandas_reference = build_panel(config, official, bar_data)
    _progress("computing feature-specific diagnostics and dependence-aware inference")
    diagnostics = compute_diagnostics(
        panel, config.label_horizons, config.quantiles, config.seed,
        config.bootstrap_samples, config.bootstrap_block_sessions, config.confidence_level,
    )

    _progress("hashing source inputs and final run identity")
    source_hashes = _source_inventory(config, intervals, bar_data.input_files)
    config_hash = content_hash(config.portable_dict())
    logical_dataset_version = f"{config.logical_dataset_name}-{content_hash(source_hashes)[:16]}"
    computed_universe_version = f"{config.universe_version}-{content_hash({k: v for k, v in source_hashes.items() if 'gpw_indices' in k})[:12]}"
    run_identity = {
        "config_hash": config_hash, "source_hashes": source_hashes, "code_hashes": code_hashes,
        "logical_dataset_version": logical_dataset_version, "universe_version": computed_universe_version,
        "environment_lock_hash": environment_lock_hash, "git_commit": git_state["commit"],
        "git_state_hash": content_hash(git_state),
    }
    run_id = f"phasea-{content_hash(run_identity)[:16]}"
    run_dir = destination_override.resolve() if destination_override else (config.phase_root / "runs" / run_id).resolve()
    if not run_dir.is_relative_to(config.output_root.resolve()):
        raise ValueError(f"run directory must stay under {config.output_root}: {run_dir}")
    if run_dir.exists():
        raise FileExistsError(f"run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True)
    _progress(f"writing authoritative run {run_id}")
    writer = ArtifactWriter(run_dir, config)
    writer.text("config.yaml", dump_config(config), "yaml")
    writer.bytes("artifacts/source_snapshot.zip", _source_snapshot(project_root, code_paths), "zip")
    writer.json("artifacts/environment_lock.json", environment_lock)

    writer.parquet("artifacts/security_master.parquet", identities.security_master, ["security_id"])
    writer.parquet("artifacts/security_aliases.parquet", identities.aliases, ["security_id", "identifier_type", "valid_from", "identifier_value"])
    writer.parquet("artifacts/vendor_resolution.parquet", identities.vendor_resolution, ["isin"])
    writer.parquet("artifacts/membership_intervals.parquet", intervals, ["effective_from", "universe_component", "isin"])
    writer.parquet("artifacts/validated_daily_bars.parquet", bar_data.bars, ["security_id", "event_ts"])
    writer.parquet("artifacts/wig_daily.parquet", bar_data.wig, ["session_date"])
    writer.parquet("artifacts/feature_values.parquet", features, ["security_id", "session_date"])
    writer.parquet("artifacts/research_panel.parquet", diagnostics.cross_section, ["session_date", "security_id"])
    writer.csv("artifacts/coverage.csv", diagnostics.coverage, ["session_date"])
    writer.csv("artifacts/feature_coverage.csv", diagnostics.feature_coverage, ["session_date", "feature"])
    writer.parquet("artifacts/rank_ic.parquet", diagnostics.rank_ic, ["session_date", "feature", "horizon_sessions"])
    writer.parquet("artifacts/quantile_returns.parquet", diagnostics.quantile_returns, ["session_date", "feature", "horizon_sessions", "quantile"])
    writer.csv("artifacts/monotonicity.csv", diagnostics.monotonicity, ["feature", "horizon_sessions", "quantile"])
    writer.csv("artifacts/turnover.csv", diagnostics.turnover, ["session_date", "feature"])
    writer.csv("artifacts/missing_by_session.csv", diagnostics.missing_by_session, ["session_date", "price_eligibility_state", "price_exclusion_reason"])
    writer.csv("artifacts/missing_overall.csv", diagnostics.missing_overall, ["price_eligibility_state", "price_exclusion_reason"])
    writer.csv("artifacts/feature_missing_summary.csv", diagnostics.feature_missing_summary, ["feature", "feature_eligibility_state"])
    writer.csv("artifacts/annual_rank_ic.csv", diagnostics.annual_stability, ["feature", "horizon_sessions", "year"])
    writer.csv("artifacts/regime_rank_ic.csv", diagnostics.regime_stability, ["feature", "horizon_sessions", "wig_trend_regime"])
    writer.csv("artifacts/rank_ic_uncertainty.csv", diagnostics.uncertainty, ["feature", "horizon_sessions"])
    writer.csv("artifacts/non_overlapping_rank_ic.csv", diagnostics.non_overlapping_ic, ["feature", "horizon_sessions", "offset"])
    writer.csv("artifacts/coverage_sensitivity.csv", diagnostics.coverage_sensitivity, ["feature", "horizon_sessions", "price_usable_member_count", "unresolved_exit_member_count"])
    writer.csv("artifacts/exit_period_sensitivity.csv", diagnostics.exit_period_sensitivity, ["exit_isin", "feature", "horizon_sessions", "period"])
    writer.csv("artifacts/exit_exposure_by_session.csv", diagnostics.exit_exposure_by_session, ["session_date"])
    writer.json("artifacts/feature_registry.json", [asdict(spec) | {"column": spec.column} for spec in feature_specs()])
    definitions = [definition.to_dict() for definition in label_definitions(config.label_horizons)]
    writer.json("artifacts/label_definitions.json", definitions)

    unresolved = identities.vendor_resolution.loc[
        ~identities.vendor_resolution["vendor_resolution_status"].isin(["exact", "mapped_renamed", "mapped_successor"]),
        ["isin", "vendor_resolution_status", "mapping_provenance"],
    ].to_dict("records")
    coverage = diagnostics.coverage
    feature_coverage_summary = diagnostics.feature_coverage.groupby("feature")["feature_usable_member_count"].agg(["min", "mean", "max"]).reset_index().to_dict("records")
    price_exclusions = diagnostics.cross_section.loc[
        ~diagnostics.cross_section["is_price_usable_member"], "price_exclusion_reason"
    ].value_counts(dropna=False).to_dict()
    metrics = _json_safe(
        {
            "run_id": run_id,
            "research_disclaimer": "Dependence-aware, temporal, regime, and missingness diagnostics remain hypothesis-generation outputs, not a strategy, backtest, or evidence of deployable alpha.",
            "sessions": len(coverage), "panel_rows": len(diagnostics.cross_section),
            "official_member_count_min": int(coverage["official_member_count"].min()),
            "official_member_count_max": int(coverage["official_member_count"].max()),
            "price_usable_member_count_min": int(coverage["price_usable_member_count"].min()),
            "price_usable_member_count_mean": float(coverage["price_usable_member_count"].mean()),
            "price_usable_member_count_max": int(coverage["price_usable_member_count"].max()),
            "price_coverage_ratio_min": float(coverage["price_coverage_ratio"].min()),
            "price_coverage_ratio_mean": float(coverage["price_coverage_ratio"].mean()),
            "complete_matrix_coverage_ratio_mean": float(coverage["complete_matrix_coverage_ratio"].mean()),
            "feature_coverage_summary": feature_coverage_summary,
            "sessions_below_full_price_coverage": int(coverage["price_coverage_ratio"].lt(1).sum()),
            "unresolved_vendor_identities": unresolved, "missing_source_files": list(bar_data.missing_files),
            "price_exclusion_member_sessions": price_exclusions,
            "rank_ic_summary": diagnostics.rank_ic.groupby(["feature", "horizon_sessions"])["rank_ic"].agg(["count", "mean", "median"]).reset_index().to_dict("records"),
            "uncertainty_summary": diagnostics.uncertainty.to_dict("records"),
        }
    )
    writer.json("metrics.json", metrics)

    row_counts = {
        "membership_intervals": len(intervals), "security_master": len(identities.security_master),
        "security_aliases": len(identities.aliases), "validated_daily_bars": len(bar_data.bars),
        "wig_daily": len(bar_data.wig), "feature_values": len(features),
        "research_panel": len(diagnostics.cross_section), "rank_ic": len(diagnostics.rank_ic),
        "quantile_returns": len(diagnostics.quantile_returns), "uncertainty": len(diagnostics.uncertainty),
    }
    manifest: dict[str, Any] = {
        "run_id": run_id, "creation_timestamp": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_state["commit"], "git_state": git_state,
        "configuration_hash": config_hash, "source_file_hashes": source_hashes, "code_file_hashes": code_hashes,
        "source_snapshot": "artifacts/source_snapshot.zip",
        "logical_dataset_version": logical_dataset_version, "universe_version": computed_universe_version,
        "schema_version": config.schema_version,
        "feature_definitions": [asdict(spec) | {"column": spec.column} for spec in feature_specs()],
        "cross_sectional_features": [spec.name for spec in feature_specs() if spec.name != "wig_trend_200"],
        "regime_variables": ["wig_trend_200"], "label_definitions": definitions,
        "timestamp_semantics": {
            "event_ts": f"official session date at {config.event_time} {config.timezone}; source bar close event",
            "available_ts": f"bar conservatively available at {config.available_time} {config.timezone}",
            "decision_ts": f"next WIG session at {config.decision_time} {config.timezone}, before the open",
            "constraint": "every feature input available_ts <= decision_ts",
            "execution_caveat": "labels are close-to-close diagnostic outcomes and are not executable portfolio returns",
        },
        "eligibility_semantics": {
            "price_member": "official identity, vendor mapping, source file, tradeability, and exact prior-session price",
            "feature_specific": "price/member eligible and the named feature is non-null",
            "feature_label": "feature-specific eligible and the exact forward label is non-null",
            "complete_matrix": "price/member eligible and every registered feature including regime input is non-null",
        },
        "package_environment_versions": _package_versions(), "environment_lock_hash": environment_lock_hash,
        "environment_lock_artifact": "artifacts/environment_lock.json", "seed": config.seed,
        "inference_settings": {
            "bootstrap_samples": config.bootstrap_samples, "bootstrap_block_sessions": config.bootstrap_block_sessions,
            "confidence_level": config.confidence_level, "hac_lag": "label horizon sessions",
            "multiple_testing": "Benjamini-Hochberg over feature-horizon HAC-normal p-values",
        },
        "writer_settings": {
            "compression": config.compression, "compression_level": config.compression_level,
            "row_group_size": config.row_group_size, "parquet_version": "2.6",
        },
        "input_output_row_counts": row_counts,
        "coverage_summary": {
            "official_min": int(coverage["official_member_count"].min()),
            "official_max": int(coverage["official_member_count"].max()),
            "price_usable_min": int(coverage["price_usable_member_count"].min()),
            "price_usable_mean": float(coverage["price_usable_member_count"].mean()),
            "price_usable_max": int(coverage["price_usable_member_count"].max()),
            "price_ratio_mean": float(coverage["price_coverage_ratio"].mean()),
            "complete_matrix_ratio_mean": float(coverage["complete_matrix_coverage_ratio"].mean()),
        },
        "output_artifact_hashes": {path: record.to_dict() for path, record in sorted(writer.records.items())},
    }
    manifest = _json_safe(manifest)
    manifest["manifest_logical_hash"] = logical_manifest_hash(manifest)
    writer.json("manifest.json", manifest, track=False)
    _progress(f"completed {run_dir}")
    return run_dir


def reproduce_run(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    config = load_config(run_dir / "config.yaml")
    original_manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    target = (config.phase_root / "cache" / "reproductions" / original_manifest["run_id"]).resolve()
    allowed = (config.phase_root / "cache" / "reproductions").resolve()
    if not target.is_relative_to(allowed):
        raise ValueError("reproduction target escaped cache root")
    if target.exists():
        shutil.rmtree(target)
    reproduced = execute_run(config, destination_override=target)
    new_manifest = json.loads((reproduced / "manifest.json").read_text(encoding="utf-8"))
    old_logical = {key: value["logical_hash"] for key, value in original_manifest["output_artifact_hashes"].items()}
    new_logical = {key: value["logical_hash"] for key, value in new_manifest["output_artifact_hashes"].items()}
    old_metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    new_metrics = json.loads((reproduced / "metrics.json").read_text(encoding="utf-8"))
    report = {
        "run_id_matches": original_manifest["run_id"] == new_manifest["run_id"],
        "configuration_hash_matches": original_manifest["configuration_hash"] == new_manifest["configuration_hash"],
        "environment_lock_hash_matches": original_manifest["environment_lock_hash"] == new_manifest["environment_lock_hash"],
        "logical_artifact_hashes_match": old_logical == new_logical, "metrics_match": old_metrics == new_metrics,
        "original_manifest_logical_hash": original_manifest["manifest_logical_hash"],
        "reproduced_manifest_logical_hash": new_manifest["manifest_logical_hash"],
        "reproduction_directory": reproduced.as_posix(),
    }
    required = ["run_id_matches", "configuration_hash_matches", "environment_lock_hash_matches", "logical_artifact_hashes_match", "metrics_match"]
    report["passed"] = all(report[key] for key in required)
    report_path = config.phase_root / "cache" / "reproduction_reports" / f"{original_manifest['run_id']}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not report["passed"]:
        raise RuntimeError(f"reproduction mismatch: {report}")
    return report
