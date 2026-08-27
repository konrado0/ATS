from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd


START = pd.Timestamp("2019-12-23")
COMMON = pd.Timestamp("2020-11-27")
END = pd.Timestamp("2026-08-18")
HORIZONS = (3, 5, 10, 20)
ANCHORS = ("close_to_close", "open_to_open")
FEATURES = (
    "momentum_12_1",
    "return_5",
    "realized_volatility_20",
    "relative_volume_20",
    "proximity_to_max_high_252",
    "proximity_to_max_close_252",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, frame: pd.DataFrame, sort: list[str]) -> None:
    frame.sort_values(sort, kind="mergesort").to_csv(path, index=False, lineterminator="\n", float_format="%.17g")


def scope_mask(frame: pd.DataFrame, scope: str) -> pd.Series:
    if scope == "added":
        return frame.session_date.between(START, COMMON - pd.Timedelta(days=1))
    if scope == "common":
        return frame.session_date.between(COMMON, END)
    return frame.session_date.between(START, END)


def safe_spearman(group: pd.DataFrame, feature: str, label: str) -> float:
    valid = group[[feature, label]].dropna()
    if len(valid) < 3:
        return np.nan
    return float(valid[feature].rank(method="average").corr(valid[label].rank(method="average")))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary-run", type=Path, required=True)
    parser.add_argument("--candidate-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--analysis-plan", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    allowed = Path(r"D:\Stock\data\ATS\phase_a_v2_research\runs").resolve()
    if not output.is_relative_to(allowed) or output.exists():
        raise ValueError("supplement output must be a new directory beneath the dedicated runs root")
    tables = output / "tables"
    tables.mkdir(parents=True)

    primary_manifest_path = args.primary_run / "manifest.json"
    primary_manifest = json.loads(primary_manifest_path.read_text(encoding="utf-8"))
    candidate = pd.read_parquet(args.candidate_run / "candidate_panel.parquet")
    candidate["session_date"] = pd.to_datetime(candidate.session_date)
    official = candidate.loc[candidate.official_membership & candidate.session_date.between(START, END)].copy()
    missing_rows = []
    denominator_rows = []
    for scope in ["added", "common", "expanded"]:
        scoped = official.loc[scope_mask(official, scope)]
        for session, group in scoped.groupby("session_date", sort=True):
            denominator_rows.append({"scope": scope, "session_date": session, "official_expected": 60, "official_rows": len(group), "price_usable_count": int(group.price_usable_for_features.sum()), "explicit_missing_count": int(group.missing_state.fillna("").ne("").sum()), "documented_nontrading_count": int(group.expected_trading.eq(False).sum())})
        fields = {
            "missing_state": scoped.missing_state.fillna("").replace("", "none"),
            "coverage_result": scoped.coverage_result.fillna("missing"),
            "nontrading_reason": scoped.nontrading_reason.fillna("").replace("", "none"),
            "volume_ineligibility_reason": scoped.volume_ineligibility_reason.fillna("").replace("", "none"),
        }
        for field, values in fields.items():
            counts = values.value_counts(dropna=False)
            for state, count in counts.items():
                missing_rows.append({"scope": scope, "field": field, "state": state, "rows": int(count), "official_rows": len(scoped), "share": count / len(scoped)})
    denominator = pd.DataFrame(denominator_rows)
    missing = pd.DataFrame(missing_rows)
    write_csv(tables / "denominator_by_session.csv", denominator, ["scope", "session_date"])
    write_csv(tables / "missing_state_summary.csv", missing, ["scope", "field", "state"])

    panel = pd.read_parquet(args.primary_run / "adapted_new_panel.parquet")
    panel["session_date"] = pd.to_datetime(panel.session_date)
    calendar = pd.DatetimeIndex(sorted(candidate.session_date.unique()))
    position = {date: i for i, date in enumerate(calendar)}
    label_rows = []
    feature_rows = []
    for scope in ["added", "common", "expanded"]:
        scoped = panel.loc[scope_mask(panel, scope)]
        for feature in FEATURES:
            eligible = scoped[f"eligible__{feature}"].fillna(False)
            price = scoped.price_usable.fillna(False)
            for state, mask in {
                "eligible": eligible,
                "price_unusable_prior_session": ~price,
                "insufficient_exact_lookback_or_volume": price & ~eligible,
            }.items():
                feature_rows.append({"scope": scope, "feature": feature, "state": state, "rows": int(mask.sum()), "official_rows": len(scoped), "share": mask.mean()})
        for anchor in ANCHORS:
            for horizon in HORIZONS:
                start_col = f"label_start__{anchor}__{horizon}"
                end_col = f"label_end__{anchor}__{horizon}"
                label_col = f"label__{anchor}__{horizon}"
                end_dates = scoped.session_date.map(lambda date: calendar[position[date] + horizon] if position[date] + horizon < len(calendar) else pd.NaT)
                states = np.select(
                    [scoped[start_col].isna(), end_dates.isna() | end_dates.gt(END), scoped[end_col].isna(), scoped[label_col].notna()],
                    ["missing_start_exact_session", "right_censored", "missing_end_exact_session", "eligible"],
                    default="invalid_state",
                )
                counts = pd.Series(states).value_counts()
                for state, count in counts.items():
                    label_rows.append({"scope": scope, "anchor": anchor, "horizon_sessions": horizon, "state": state, "rows": int(count), "official_rows": len(scoped), "share": count / len(scoped)})
    write_csv(tables / "feature_missing_state_summary.csv", pd.DataFrame(feature_rows), ["scope", "feature", "state"])
    write_csv(tables / "label_missing_state_summary.csv", pd.DataFrame(label_rows), ["scope", "anchor", "horizon_sessions", "state"])

    regime_by_date = panel.groupby("session_date", as_index=False).wig_trend_200.first()
    regime_by_date["wig_trend_regime"] = np.where(regime_by_date.wig_trend_200.ge(0), "above_200_session_mean", "below_200_session_mean")
    regime_rows = []
    common = panel.loc[panel.session_date.between(COMMON, END)]
    for feature in FEATURES:
        for anchor in ANCHORS:
            for horizon in HORIZONS:
                label = f"label__{anchor}__{horizon}"
                valid = common[f"eligible__{feature}"].fillna(False) & common[label].notna()
                daily = common.loc[valid].groupby("session_date", sort=True).apply(lambda group: safe_spearman(group, feature, label), include_groups=False).rename("rank_ic").reset_index()
                daily = daily.merge(regime_by_date[["session_date", "wig_trend_regime"]], on="session_date", validate="one_to_one")
                for regime, group in daily.groupby("wig_trend_regime", sort=True):
                    regime_rows.append({"feature": feature, "anchor": anchor, "horizon_sessions": horizon, "wig_trend_regime": regime, "sessions": group.rank_ic.notna().sum(), "mean_rank_ic": group.rank_ic.mean(), "median_rank_ic": group.rank_ic.median(), "positive_session_share": group.rank_ic.gt(0).mean()})
    write_csv(tables / "wig_trend_regime_rank_ic.csv", pd.DataFrame(regime_rows), ["feature", "anchor", "horizon_sessions", "wig_trend_regime"])

    mapping = pd.DataFrame([
        {"definition": "proximity_to_max_high_252", "formula": "prior close / trailing exact 252-session maximum high", "historical_report": "RESEARCH/POST_PHASE_A_DIAGNOSTIC_REPORT.md", "executable_code": "RESEARCH/prototypes/post_phase_a_diagnostics/run_diagnostics.py:813", "historical_classification": "exploratory/promising"},
        {"definition": "proximity_to_max_close_252", "formula": "prior close / trailing exact 252-session maximum close", "historical_report": "RESEARCH/PHASE_A_DECISION_ORIENTED_REPORT.md", "executable_code": "RESEARCH/prototypes/decision_oriented_phase_a/analyze_decisions.py:412", "historical_classification": "PROMISING"},
    ])
    write_csv(tables / "proximity_semantic_mapping.csv", mapping, ["definition"])
    shutil.copy2(args.analysis_plan, output / "analysis_plan.md")
    shutil.copy2(args.config, output / "config.json")
    shutil.copy2(Path(__file__), output / "source_snapshot.py")
    files = sorted(path for path in output.rglob("*") if path.is_file() and path.name != "manifest.json")
    logical = {path.relative_to(output).as_posix(): sha256_file(path) for path in files}
    manifest = {
        "schema_version": "ats.phase_a_v2_research.audit_supplement.v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "run_id": output.name,
        "immutable_output": str(output),
        "primary_run": str(args.primary_run.resolve()),
        "primary_manifest_sha256": sha256_file(primary_manifest_path),
        "primary_logical_payload_hash": primary_manifest["logical_payload_hash"],
        "candidate_manifest_sha256": sha256_file(args.candidate_run / "manifest.json"),
        "files": {path.relative_to(output).as_posix(): {"bytes": path.stat().st_size, "sha256": sha256_file(path)} for path in files},
        "logical_payload_hash": hashlib.sha256(json.dumps(logical, sort_keys=True).encode()).hexdigest(),
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "logical_payload_hash": manifest["logical_payload_hash"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
