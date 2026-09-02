from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


COMPARATORS = ("C_LINEAR", "C_LIGHTGBM")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return value


def validate_seal(directory: Path) -> dict[str, Any]:
    manifest = read_json(directory / "manifest.json")
    inventory = manifest["files"]
    actual = {path.relative_to(directory).as_posix() for path in directory.rglob("*") if path.is_file()}
    if actual != {"manifest.json", *inventory}:
        raise ValueError(f"independent physical inventory mismatch: {directory}")
    for relative, record in inventory.items():
        path = directory / relative
        if path.stat().st_size != record["bytes"] or digest(path) != record["sha256"]:
            raise ValueError(f"independent hash mismatch: {directory / relative}")
    if canonical_hash(manifest["logical_payload"]) != manifest["logical_hash"]:
        raise ValueError(f"independent logical-manifest mismatch: {directory}")
    return manifest


def ic(scores: pd.Series, labels: pd.Series) -> float:
    frame = pd.DataFrame({"score": scores, "label": labels}).replace([np.inf, -np.inf], np.nan).dropna()
    if len(frame) < 45 or frame["score"].nunique() < 2 or frame["label"].nunique() < 2:
        return math.nan
    return float(frame["score"].rank(method="average").corr(frame["label"].rank(method="average")))


def wide(predictions: pd.DataFrame, outcomes: pd.DataFrame, block_ids: list[str]) -> pd.DataFrame:
    selected = predictions.loc[predictions["block_id"].isin(block_ids)]
    keys = ["block_id", "security_id", "decision_session"]
    scores = selected.pivot(index=keys, columns="cell_id", values="model_score").add_prefix("score__")
    candidates = selected.pivot(index=keys, columns="cell_id", values="candidate").add_prefix("candidate__")
    return scores.join(candidates).reset_index().merge(
        outcomes[["block_id", "security_id", "decision_session", "label__open_to_open__20"]],
        on=keys, how="left", validate="one_to_one",
    ).sort_values(["decision_session", "security_id"], kind="mergesort").reset_index(drop=True)


def session_ics(frame: pd.DataFrame, cells: list[str]) -> pd.DataFrame:
    rows = []
    for session, group in frame.groupby("decision_session", sort=True):
        row = {"decision_session": session}
        for cell in cells:
            row[cell] = ic(group[f"score__{cell}"], group["label__open_to_open__20"])
        rows.append(row)
    return pd.DataFrame(rows)


def select(statistics: dict[str, float], linear: str, tree: str) -> str:
    return linear if abs(statistics[linear] - statistics[tree]) <= 0.002 or statistics[linear] > statistics[tree] else tree


def anchors_for_all(predictions: pd.DataFrame, selected_rich: str, sessions: pd.DatetimeIndex) -> pd.DataFrame:
    position = {pd.Timestamp(value): index for index, value in enumerate(sessions)}
    frame = predictions.loc[
        predictions["cell_id"].eq(selected_rich), ["security_id", "decision_session", "candidate"]
    ].sort_values(["security_id", "decision_session"], kind="mergesort")
    frame["episode_anchor"] = False
    for _, indices in frame.groupby("security_id", sort=False).groups.items():
        prior: int | None = None
        for index in indices:
            if not bool(frame.at[index, "candidate"]):
                continue
            current = position[pd.Timestamp(frame.at[index, "decision_session"])]
            if prior is None or current - prior > 20:
                frame.at[index, "episode_anchor"] = True
            prior = current
    return frame


def weights(values: pd.Series, k: int) -> np.ndarray:
    scores = values.to_numpy(dtype=float)
    if k == 0:
        return np.zeros(len(scores))
    if k >= len(scores):
        return np.ones(len(scores))
    boundary = float(np.partition(scores, len(scores) - k)[len(scores) - k])
    above = scores > boundary
    equal = scores == boundary
    return above.astype(float) + equal.astype(float) * ((k - above.sum()) / equal.sum())


def population_metrics(
    predictions: pd.DataFrame,
    outcomes: pd.DataFrame,
    block_ids: list[str],
    selected_rich: str,
    anchors: pd.DataFrame,
) -> dict[str, Any]:
    frame = wide(predictions, outcomes, block_ids).merge(
        anchors[["security_id", "decision_session", "episode_anchor"]],
        on=["security_id", "decision_session"], validate="one_to_one",
    )
    cells = [*COMPARATORS, selected_rich]
    rank = session_ics(frame, cells)
    anchor_rows = frame.loc[frame["episode_anchor"] & frame["label__open_to_open__20"].notna()]
    tail_rows = []
    for session, group in frame.groupby("decision_session", sort=True):
        eligible = group.loc[group["label__open_to_open__20"].notna()]
        rich = anchor_rows.loc[anchor_rows["decision_session"].eq(session)]
        if rich.empty:
            continue
        record: dict[str, Any] = {
            "decision_session": session,
            "rich_minus_eligible": float(rich["label__open_to_open__20"].mean() - eligible["label__open_to_open__20"].mean()),
        }
        for comparator in COMPARATORS:
            match = weights(eligible[f"score__{comparator}"], len(rich))
            labels = eligible["label__open_to_open__20"].to_numpy(dtype=float)
            conventional_mean = float(np.average(labels, weights=match))
            conventional_severe = float(np.average((labels <= -0.10).astype(float), weights=match))
            record[f"tail__{comparator}"] = float(rich["label__open_to_open__20"].mean() - conventional_mean)
            record[f"severe__{comparator}"] = float((rich["label__open_to_open__20"] <= -0.10).mean() - conventional_severe)
        tail_rows.append(record)
    tail = pd.DataFrame(tail_rows)
    counts = anchor_rows.groupby("security_id").size().astype(float)
    shares = counts / counts.sum()
    ordered_sessions = pd.DatetimeIndex(sorted(frame["decision_session"].unique()))
    quartiles = [int(anchor_rows["decision_session"].isin(chunk).sum()) for chunk in np.array_split(ordered_sessions.to_numpy(), 4)]
    by_block = {}
    for block_id, group in frame.groupby("block_id", sort=True):
        candidates = group.groupby("decision_session")[f"candidate__{selected_rich}"].sum()
        by_block[block_id] = {
            "candidate_row_fraction": float(group[f"candidate__{selected_rich}"].mean()),
            "opportunity_session_fraction": float(candidates.gt(0).mean()),
            "idle_session_fraction": float(candidates.eq(0).mean()),
            "session_candidate_count_p95": float(np.quantile(candidates, 0.95, method="linear")),
        }
    return {
        "scored_rows": len(frame),
        "outcome_evaluable_rows": int(frame["label__open_to_open__20"].notna().sum()),
        "mean_ic": {cell: float(rank[cell].mean()) for cell in cells},
        "mean_delta_ic": {comparator: float((rank[selected_rich] - rank[comparator]).mean()) for comparator in COMPARATORS},
        "raw_candidate_rows": int(frame[f"candidate__{selected_rich}"].sum()),
        "episode_anchors": len(anchor_rows),
        "rich_minus_eligible": float(tail["rich_minus_eligible"].mean()),
        "rich_minus_conventional": {comparator: float(tail[f"tail__{comparator}"].mean()) for comparator in COMPARATORS},
        "severe_difference": {comparator: float(tail[f"severe__{comparator}"].mean()) for comparator in COMPARATORS},
        "frequency_by_block": by_block,
        "concentration": {
            "largest_security_episode_share": float(shares.max()),
            "top5_security_episode_share": float(shares.nlargest(5).sum()),
            "security_episode_hhi": float((shares ** 2).sum()),
            "largest_chronological_quartile_share": max(quartiles) / len(anchor_rows),
        },
    }


def classify(row: dict[str, Any]) -> str:
    value = row.get("value")
    threshold = row.get("threshold")
    if value is None:
        return "NOT PROVEN"
    operator = row["operator"]
    if operator == "is":
        passed = value is threshold or value == threshold
    elif operator == ">=":
        passed = value >= threshold
    elif operator == ">":
        passed = value > threshold
    elif operator == "<=":
        passed = value <= threshold
    elif operator == "<":
        passed = value < threshold
    else:
        raise ValueError(f"unknown gate operator: {operator}")
    return "PASS" if passed else "FAIL"


def verdict(gates: list[dict[str, Any]]) -> str:
    validity = {"validity", "execution_integrity", "reproducibility", "comparability", "leakage"}
    if any(row["category"] in validity and row["status"] != "PASS" for row in gates):
        return "NOT PROVEN"
    if any(row["status"] == "NOT PROVEN" for row in gates):
        return "NOT PROVEN"
    return "CONTINUE" if all(row["status"] == "PASS" for row in gates) else "STOP"


def close(left: Any, right: Any) -> bool:
    return bool(np.isclose(float(left), float(right), rtol=0.0, atol=1e-12, equal_nan=True))


def evaluate(prediction_dir: Path, evaluation_root: Path) -> dict[str, Any]:
    manifests = {"prediction": validate_seal(prediction_dir)}
    for stage in ("stage2a", "stage2b", "stage2c", "final"):
        manifests[stage] = validate_seal(evaluation_root / stage)
    predictions = pd.read_parquet(prediction_dir / "predictions.parquet")
    masks = pd.read_parquet(prediction_dir / "common_score_masks.parquet")
    selection_outcomes = pd.read_parquet(evaluation_root / "stage2a" / "outcomes.parquet")
    selection_frame = wide(predictions, selection_outcomes, ["MODEL_SELECTION_2023_H1", "MODEL_SELECTION_2023_H2"])
    selection_ic = session_ics(selection_frame, list(("C_LINEAR", "C_LIGHTGBM", "RICH_LINEAR", "RICH_LIGHTGBM")))
    selection_statistics = {cell: float(selection_ic[cell].mean()) for cell in ("C_LINEAR", "C_LIGHTGBM", "RICH_LINEAR", "RICH_LIGHTGBM")}
    selected_conventional = select(selection_statistics, "C_LINEAR", "C_LIGHTGBM")
    selected_rich = select(selection_statistics, "RICH_LINEAR", "RICH_LIGHTGBM")
    primary_selection = read_json(evaluation_root / "stage2a" / "selection.json")
    selection_match = (
        selected_conventional == primary_selection["conventional"]["selected"]
        and selected_rich == primary_selection["rich"]["selected"]
        and all(close(selection_statistics[cell], primary_selection["cell_statistics"][cell]) for cell in selection_statistics)
    )
    calendar = pd.DatetimeIndex(sorted(masks["decision_session"].unique()))
    anchors = anchors_for_all(predictions, selected_rich, calendar)
    populations = {
        "stage2b": (["DEVELOPMENT_2024_H1", "DEVELOPMENT_2024_H2"], pd.read_parquet(evaluation_root / "stage2b" / "outcomes.parquet")),
        "stage2c": (["LOCKED_2025_H1", "LOCKED_2025_H2", "LOCKED_2026_H1"], pd.read_parquet(evaluation_root / "stage2c" / "outcomes.parquet")),
    }
    recomputed = {}
    metric_matches = {}
    for stage, (blocks, outcomes) in populations.items():
        values = population_metrics(predictions, outcomes, blocks, selected_rich, anchors)
        recomputed[stage] = values
        primary = read_json(evaluation_root / stage / "metrics.json")
        checks = [
            values["scored_rows"] == primary["scored_rows"],
            values["outcome_evaluable_rows"] == primary["outcome_evaluable_rows"],
            values["raw_candidate_rows"] == primary["raw_candidate_rows"],
            values["episode_anchors"] == primary["outcome_evaluable_episode_anchors"],
            close(values["rich_minus_eligible"], primary["rich_minus_eligible_mean_return"]),
        ]
        for comparator in COMPARATORS:
            checks.extend([
                close(values["mean_delta_ic"][comparator], primary["mean_delta_ic"][comparator]),
                close(values["rich_minus_conventional"][comparator], primary["rich_minus_conventional_mean_return"][comparator]),
                close(values["severe_difference"][comparator], primary["severe_rate_difference"][comparator]),
            ])
        for name, value in values["concentration"].items():
            checks.append(close(value, primary["concentration"][name]))
        for block, frequency in values["frequency_by_block"].items():
            for name, value in frequency.items():
                checks.append(close(value, primary["frequency_by_block"][block][name]))
        metric_matches[stage] = all(checks)
    final_gates = read_json(evaluation_root / "final" / "gate_matrix.json")["gates"]
    gate_classification_match = all(classify(row) == row["status"] for row in final_gates)
    independent_verdict = verdict(final_gates)
    primary_verdict = read_json(evaluation_root / "final" / "verdict.json")["frozen_phase_d_research_verdict"]
    result = {
        "schema_version": "ats.phase_d2.independent_evaluation.v1",
        "status": "PASS" if selection_match and all(metric_matches.values()) and gate_classification_match and independent_verdict == primary_verdict else "FAIL",
        "sealed_input_logical_hashes": {name: value["logical_hash"] for name, value in manifests.items()},
        "population_denominators": {
            stage: {"scored_rows": value["scored_rows"], "outcome_evaluable_rows": value["outcome_evaluable_rows"]}
            for stage, value in recomputed.items()
        },
        "selection": {
            "statistics": selection_statistics,
            "selected_conventional": selected_conventional,
            "selected_rich": selected_rich,
            "matches_primary": selection_match,
        },
        "decisive_metric_matches": metric_matches,
        "gate_classification_match": gate_classification_match,
        "independent_verdict": independent_verdict,
        "primary_verdict": primary_verdict,
        "imports_primary_metric_functions": False,
    }
    result["logical_hash"] = canonical_hash(result)
    return result


def publish(result: dict[str, Any], output_dir: Path) -> None:
    if output_dir.exists():
        raise FileExistsError(f"independent publication already exists: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = output_dir.parent / f".stage-{output_dir.name}-{uuid.uuid4().hex}"
    stage.mkdir()
    try:
        evidence = stage / "independent_evaluation.json"
        evidence.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        manifest = {
            "schema_version": "ats.phase_d2.independent_manifest.v1",
            "run_id": output_dir.name,
            "logical_hash": result["logical_hash"],
            "files": {"independent_evaluation.json": {"bytes": evidence.stat().st_size, "sha256": digest(evidence)}},
        }
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(stage, output_dir)
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prediction-dir", type=Path, required=True)
    parser.add_argument("--evaluation-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.prediction_dir, args.evaluation_root)
    publish(result, args.output_dir)
    print(json.dumps({"status": result["status"], "logical_hash": result["logical_hash"], "output_dir": str(args.output_dir)}, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

