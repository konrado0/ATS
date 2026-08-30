from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def object_hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def rank_quantile(frame: pd.DataFrame, feature: str, eligible: pd.Series) -> pd.Series:
    values = frame[feature].where(eligible)
    ranks = values.groupby(frame["session_date"]).rank(method="average")
    counts = values.groupby(frame["session_date"]).transform("count")
    return np.ceil((ranks / counts) * 5).clip(1, 5).astype("Int64")


def session_rank_ic(frame: pd.DataFrame, feature: str, label: str) -> pd.Series:
    return frame.groupby("session_date", sort=True).apply(
        lambda group: group[feature].corr(group[label], method="spearman"),
        include_groups=False,
    )


def q5_minus_q1(frame: pd.DataFrame, label: str) -> float:
    means = frame.groupby(["session_date", "quantile"], observed=True)[label].mean().unstack()
    return float((means.get(5) - means.get(1)).mean())


def validate_inputs(config: dict[str, object]) -> tuple[Path, Path, Path]:
    candidate_root = Path(str(config["candidate_run"]))
    phase_a_root = Path(str(config["phase_a_v2_run"]))
    manifest = candidate_root / "manifest.json"
    candidate = candidate_root / "candidate_panel.parquet"
    adapted = phase_a_root / "adapted_new_panel.parquet"
    expected = {
        manifest: str(config["candidate_manifest_sha256"]),
        candidate: str(config["candidate_panel_physical_sha256"]),
        adapted: str(config["adapted_panel_physical_sha256"]),
    }
    failures = {str(path): (wanted, sha256_file(path)) for path, wanted in expected.items() if not path.is_file() or sha256_file(path) != wanted}
    if failures:
        raise RuntimeError(f"pinned Dino inputs failed validation: {failures}")
    return manifest, candidate, adapted


def build_supplement(config: dict[str, object]) -> dict[str, pd.DataFrame | dict[str, object]]:
    manifest_path, candidate_path, adapted_path = validate_inputs(config)
    candidate = pd.read_parquet(candidate_path)
    candidate["session_date"] = pd.to_datetime(candidate["session_date"])
    adapted = pd.read_parquet(adapted_path)
    adapted["session_date"] = pd.to_datetime(adapted["session_date"])

    isin = str(config["dino_isin"])
    pre = pd.Timestamp(str(config["confirmed_last_pre_event_session"]))
    post = pd.Timestamp(str(config["confirmed_first_post_event_session"]))
    ratio = float(config["split_ratio"])
    dino = candidate.loc[candidate["isin"].eq(isin) & candidate["session_date"].isin([pre, post])].set_index("session_date")
    if set(dino.index) != {pre, post}:
        raise RuntimeError("Dino pre/post event bars are not both present")
    transition_rows: list[dict[str, object]] = []
    for field in ("open", "high", "low", "close"):
        native_return = float(dino.loc[post, f"native_{field}"] / dino.loc[pre, f"native_{field}"] - 1.0)
        adjusted_return = float(dino.loc[post, f"split_adjusted_{field}"] / dino.loc[pre, f"split_adjusted_{field}"] - 1.0)
        action_return = float(ratio * dino.loc[post, f"native_{field}"] / dino.loc[pre, f"native_{field}"] - 1.0)
        transition_rows.append(
            {
                "field": field,
                "last_pre_event_session": pre.date().isoformat(),
                "first_post_event_session": post.date().isoformat(),
                "native_pre": dino.loc[pre, f"native_{field}"],
                "native_post": dino.loc[post, f"native_{field}"],
                "native_return": native_return,
                "split_adjusted_pre": dino.loc[pre, f"split_adjusted_{field}"],
                "split_adjusted_post": dino.loc[post, f"split_adjusted_{field}"],
                "split_adjusted_return": adjusted_return,
                "native_plus_quantity_action_return": action_return,
                "action_reconciliation_difference": action_return - adjusted_return,
                "mechanical_drop_absent": adjusted_return > float(config["materiality"]["mechanical_return_floor"]),
            }
        )
    transition = pd.DataFrame(transition_rows)

    start, end = [pd.Timestamp(value) for value in config["common_period"]]
    feature = str(config["feature"])
    label = str(config["label"])
    eligible_col = f"eligible__{feature}"
    work = adapted.loc[adapted["session_date"].between(start, end)].copy()
    valid = work[eligible_col].fillna(False) & work[label].notna()
    work = work.loc[valid, ["session_date", "security_id", "isin", feature, label]].copy()
    work["quantile"] = rank_quantile(work, feature, pd.Series(True, index=work.index))

    calendar = pd.DatetimeIndex(sorted(candidate["session_date"].unique()))
    positions = {session: index for index, session in enumerate(calendar)}
    event_index = positions[post]
    horizon = int(config["horizon_sessions"])
    work["label_end_session"] = work["session_date"].map(
        lambda session: calendar[positions[session] + horizon] if session in positions and positions[session] + horizon < len(calendar) else pd.NaT
    )
    event_mask = work["isin"].eq(isin) & work["session_date"].lt(post) & work["label_end_session"].ge(post)
    event_observations = work.loc[event_mask].sort_values("session_date").copy()

    base_ic_sessions = session_rank_ic(work, feature, label)
    excluded = work.loc[~event_mask].copy()
    excluded_ic_sessions = session_rank_ic(excluded, feature, label)
    base_ic = float(base_ic_sessions.mean())
    excluded_ic = float(excluded_ic_sessions.mean())
    base_spread = q5_minus_q1(work, label)
    excluded_spread = q5_minus_q1(excluded, label)
    ic_shift = excluded_ic - base_ic
    spread_shift = excluded_spread - base_spread
    materiality = config["materiality"]
    sign_reversal = (base_ic > 0) != (excluded_ic > 0) or (base_spread > 0) != (excluded_spread > 0)
    materially_undermined = bool(
        (materiality["sign_reversal_is_material"] and sign_reversal)
        or abs(ic_shift) >= float(materiality["rank_ic_absolute_shift"])
        or abs(spread_shift) >= float(materiality["q5_minus_q1_absolute_shift"])
    )
    transition_pass = bool(transition["mechanical_drop_absent"].all() and transition["action_reconciliation_difference"].abs().max() < 1e-12)
    gate = "PASS" if transition_pass and not materially_undermined else "FAIL"
    sensitivity = pd.DataFrame(
        [
            {"measure": "mean_session_rank_ic", "baseline": base_ic, "excluding_event_straddling_dino": excluded_ic, "shift": ic_shift},
            {"measure": "mean_session_q5_minus_q1", "baseline": base_spread, "excluding_event_straddling_dino": excluded_spread, "shift": spread_shift},
        ]
    )
    summary = {
        "schema_version": "ats.phase_a_v2_dino_correction.summary.v1",
        "dino_correction": gate,
        "incorrect_historical_window": config["incorrect_historical_window"],
        "corrected_event_window": [pre.date().isoformat(), post.date().isoformat()],
        "event_straddling_observations": int(event_mask.sum()),
        "event_straddling_decision_start": event_observations["session_date"].min().date().isoformat() if len(event_observations) else None,
        "event_straddling_decision_end": event_observations["session_date"].max().date().isoformat() if len(event_observations) else None,
        "normalized_transition_pass": transition_pass,
        "sign_reversal": sign_reversal,
        "materially_undermined": materially_undermined,
        "candidate_manifest_path": manifest_path.resolve().as_posix(),
        "candidate_manifest_sha256": sha256_file(manifest_path),
        "phase_a_v2_identity": config["phase_a_v2_logical_payload_hash"],
        "interpretation": "The corrected diagnostic preserves or undermines the max-high result under frozen materiality thresholds; it does not rewrite the accepted Phase A v2 run.",
    }
    return {"transition": transition, "sensitivity": sensitivity, "event_observations": event_observations, "summary": summary}


def write_run(config_path: Path, output_root: Path) -> Path:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    destination = output_root.resolve() / str(config["run_id"])
    if destination.exists():
        raise FileExistsError(f"immutable Dino supplement already exists: {destination}")
    staging = output_root.resolve().parent / "staging" / f"{config['run_id']}-{uuid.uuid4().hex[:8]}"
    staging.mkdir(parents=True, exist_ok=False)
    try:
        result = build_supplement(config)
        shutil.copyfile(config_path, staging / "config.json")
        tables = staging / "tables"
        tables.mkdir()
        for name in ("transition", "sensitivity", "event_observations"):
            result[name].to_csv(tables / f"{name}.csv", index=False, float_format="%.17g", lineterminator="\n")
        (staging / "summary.json").write_text(json.dumps(result["summary"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
        files = {}
        for path in sorted(item for item in staging.rglob("*") if item.is_file()):
            relative = path.relative_to(staging).as_posix()
            files[relative] = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
        logical_payload = {
            "run_id": config["run_id"],
            "config_sha256": sha256_file(config_path),
            "summary": result["summary"],
            "file_hashes": {key: value["sha256"] for key, value in files.items()},
        }
        manifest = {
            "schema_version": "ats.phase_a_v2_dino_correction.manifest.v1",
            "run_id": config["run_id"],
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "config_sha256": sha256_file(config_path),
            "files": files,
            "logical_payload_hash": object_hash(logical_payload),
        }
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, destination)
        return destination
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "dino_config.json")
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    print(write_run(args.config, args.output_root))


if __name__ == "__main__":
    main()
