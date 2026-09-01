from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "source/python/src"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from ats_ml.contracts_v3 import load_frozen_d0_v3_contract  # noqa: E402


CONFIG = ROOT / "source/python/configs/phase_d0_reference_v3.json"
REGISTRY = ROOT / "source/python/configs/phase_d0_feature_registry.json"
PLAN = ROOT / "RESEARCH/PHASE_D0_EXPERIMENT_PLAN_v3.md"
AUDIT = ROOT / "RESEARCH/PHASE_D0_REQUIREMENT_AUDIT_v3.json"
MANIFEST = ROOT / "RESEARCH/PHASE_D0_MANIFEST_v3.json"
PARENT_HASHES = {
    "RESEARCH/PHASE_D0_EXPERIMENT_PLAN.md": "10645dd41f1aea1f74c9f137a2f0dfd34e0a0f41f6355854c0cf9ed4b9ba0baa",
    "RESEARCH/PHASE_D0_REQUIREMENT_AUDIT.json": "f34202158f8b19cd903fd7dd00717ea529e9146fe2a94e790694892ec63559ed",
    "RESEARCH/PHASE_D0_MANIFEST.json": "7fe34d679511eb4d75b269f5a908c6ac5e624d624aa067645286576f0f9e918c",
    "RESEARCH/PHASE_D1_READINESS_v2.md": "197a285acbea97c6bedf8435ca8264f69c7f781f1d4368dc8cabb6b7c286766a",
    "RESEARCH/PHASE_D1_REQUIREMENT_AUDIT_v2.json": "657ef92d6b092968813594e9b43a61fd9135a75aff92f9da3172e77a0f2f18fa",
    "RESEARCH/PHASE_D1_MANIFEST_v2.json": "0fcbc705c013e1dffd7f1b19184b9d7b72e4156f450fc7a152f2a47b6aa5d8aa",
    "source/python/configs/phase_d0_reference.json": "ef5a7f0fa76a104ff86cae7c2ad520867a0720e1c6e508558ef31316e7e153ae",
    "source/python/configs/phase_d0_feature_registry.json": "733bacb9c1132d98eacb4a190cfb3cd96b0163207af46f3745002206b3705ef6",
    "source/python/configs/phase_d1_structural_resolution.json": "6801c396932a7200960dfedd72b9454088e8f7875c9af9ef402ef212005a599b",
}


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    checks: list[dict[str, Any]] = []

    def check(name: str, condition: bool, detail: Any) -> None:
        checks.append({"check": name, "status": "PASS" if condition else "FAIL", "detail": detail})

    required = (CONFIG, REGISTRY, PLAN, AUDIT, MANIFEST)
    check("v3_files_exist", all(path.is_file() for path in required), [str(path) for path in required])
    if not all(path.is_file() for path in required):
        print(json.dumps({"schema_version": "ats.phase_d0.validation.v3", "status": "FAIL", "checks": checks}, indent=2))
        return 1
    config, registry, audit, manifest = map(_read, (CONFIG, REGISTRY, AUDIT, MANIFEST))
    check("schemas", config.get("schema_version") == "ats.phase_d0.reference.v3" and audit.get("schema_version") == "ats.phase_d0.requirement_audit.v3" and manifest.get("schema_version") == "ats.phase_d0.manifest.v3", [config.get("schema_version"), audit.get("schema_version"), manifest.get("schema_version")])
    check("contract_version", {config.get("contract_version"), audit.get("contract_version"), manifest.get("contract_version")} == {"phase-d0-20260901-v3"}, "phase-d0-20260901-v3")
    parents = config["parents"]
    check("parents", parents.get("phase_d0_contract_version") == "phase-d0-20260831-v2" and parents.get("phase_d1_checkpoint") == "724971466dacfba05ff0fa7e92cd68c4628008c7", parents)
    parent_actual = {path: _sha(ROOT / path) for path in PARENT_HASHES}
    check("accepted_parent_bytes_unchanged", parent_actual == PARENT_HASHES, {path: parent_actual[path] for path in parent_actual if parent_actual[path] != PARENT_HASHES[path]})
    names = [item["canonical_name"] for item in registry["features"]]
    blocks = Counter(item["block"] for item in registry["features"])
    check("unchanged_30_feature_registry", len(names) == len(set(names)) == 30 and dict(blocks) == {"C": 6, "P": 8, "X": 4, "M": 12} and _sha(REGISTRY) == PARENT_HASHES["source/python/configs/phase_d0_feature_registry.json"], dict(blocks))
    unchanged = config["unchanged_parent_contract"]
    check("eight_p_survivors", len(unchanged["p_survivors"]) == 8 and set(unchanged["p_survivors"]) == {name for name, block in zip(names, [item["block"] for item in registry["features"]], strict=True) if block == "P"}, unchanged["p_survivors"])
    outer = config["outer_walk_forward"]
    check("outer_contract", outer["refit_months"] == [1, 7] and outer["window_months"] == 36 and outer["hard_coded_horizon_row_subtraction_forbidden"] is True and outer["feature_warmup_rows_forbidden_from_model_fit"] is True, outer)
    inner = config["inner_prequential_calibration"]
    check("inner_contract", inner["initial_fit_months"] == 18 and inner["score_block_count"] == 3 and inner["fit_history_months_by_score_block"] == [18, 24, 30] and inner["score_block_labels_consulted"] is False and inner["final_refit_may_recalculate_threshold"] is False, inner)
    blocks_config = config["evidence_blocks"]
    check("evidence_blocks", [item["calendar_half"] for item in blocks_config] == ["2023H1", "2023H2", "2024H1", "2024H2", "2025H1", "2025H2", "2026H1", "2026H2"] and sum(not item["complete"] for item in blocks_config) == 1, blocks_config)
    mapping = config["evidence_mapping"]
    check("gate_mapping", mapping["complete_decisive_years"] == [2024, 2025] and mapping["positive_year_fraction_denominator"] == 2 and mapping["partial_monitoring_excluded_from_every_decisive_gate"] is True, mapping)
    composed = load_frozen_d0_v3_contract(require_publication=False).config
    composed_gates = {name: composed[name] for name in ("comparison", "evaluation", "decision_gate")}
    rendered_gates = json.dumps(composed_gates, sort_keys=True).lower()
    obsolete = ("model_selection_2022", "dev_2023", "dev_2024", "locked_2025_2026", "locked historical test")
    expected_mappings = {
        "model_family_selection": ["MODEL_SELECTION_2023_H1", "MODEL_SELECTION_2023_H2"],
        "development_confirmation_pooled": ["DEVELOPMENT_2024_H1", "DEVELOPMENT_2024_H2"],
        "development_stability_blocks": ["DEVELOPMENT_2024_H1", "DEVELOPMENT_2024_H2"],
        "locked_evidence_pooled": ["LOCKED_2025_H1", "LOCKED_2025_H2", "LOCKED_2026_H1"],
        "locked_stability_blocks": ["LOCKED_2025_H1", "LOCKED_2025_H2", "LOCKED_2026_H1"],
    }
    check("composed_gate_half_year_mappings", all(composed_gates[name]["evidence_population_mappings"] == expected_mappings for name in composed_gates), {name: composed_gates[name].get("evidence_population_mappings") for name in composed_gates})
    check("no_obsolete_v2_evidence_references_in_composed_gates", not any(value in rendered_gates for value in obsolete), [value for value in obsolete if value in rendered_gates])
    minimums = config["minimums"]
    check("minimums", minimums["qualifying_session_minimum_rows"] == 45 and minimums["final_outer_fit"]["absolute_qualifying_sessions_floor"] == 230 and minimums["final_outer_fit"]["absolute_model_rows_floor"] == 10000 and minimums["inner_fit"]["absolute_rows_floor"] == 5400 and minimums["inner_score_block"]["required_block_count"] == 3, minimums)
    authorization = config["authorization"]
    check("no_predictive_authorization", all(authorization[key] is False for key in ("real_label_values", "real_model_fit", "real_prediction_or_score", "real_predictive_metrics_or_outcomes", "phase_d2")), authorization)
    statuses = [item["status"] for item in audit["requirements"]]
    expected_counts = {key: value for key, value in audit["summary_counts"].items() if value}
    check("requirement_audit", audit.get("overall_status") == "PASS" and "FAIL" not in statuses and dict(Counter(statuses)) == expected_counts, dict(Counter(statuses)))
    plan_text = PLAN.read_text(encoding="utf-8")
    plan_lower = plan_text.lower()
    markers = ("final major experimental-design amendment", "trailing 36 calendar", "exact `label_endpoint_ts < b.decision_ts`", "three consecutive six-month", "2026 h2 through 2026-08-18", "phase d2", "not proven")
    check("plan_markers", all(marker in plan_lower for marker in markers), [marker for marker in markers if marker not in plan_lower])
    manifest_entries = manifest.get("artifacts", []) + manifest.get("code", [])
    errors = []
    for entry in manifest_entries:
        path = ROOT / entry["path"]
        if not path.is_file() or _sha(path) != entry["sha256"] or path.stat().st_size != entry["bytes"]:
            errors.append(entry["path"])
    check("manifest_hashes_and_sizes", not errors, errors)
    payload = json.dumps(config, sort_keys=True).lower() + json.dumps(manifest, sort_keys=True).lower()
    check("no_mutable_latest", '"latest"' not in payload and "/latest" not in payload and "\\latest" not in payload, "explicit paths only")
    status = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"
    print(json.dumps({"schema_version": "ats.phase_d0.validation.v3", "status": status, "checks": checks}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
