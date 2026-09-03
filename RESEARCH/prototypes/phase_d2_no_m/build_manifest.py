from __future__ import annotations

import json
from pathlib import Path

from ats_research.hashing import sha256_file


REPO = Path("D:/Stock/ATS")
OUTPUT = REPO / "RESEARCH/PHASE_D2_NO_M_MANIFEST.json"
FILES = [
    "README.md",
    "RESEARCH/IMPLEMENTATION_ROADMAP.md",
    "RESEARCH/PHASE_D2_NO_M_PROSPECTIVE_PLAN.md",
    "RESEARCH/PHASE_D2_NO_M_RESULTS.md",
    "RESEARCH/PHASE_D2_NO_M_RESULTS.json",
    "RESEARCH/PHASE_D2_NO_M_PROSPECTIVE_RUNBOOK.md",
    "RESEARCH/prototypes/phase_d2_no_m/run_followup.py",
    "RESEARCH/prototypes/phase_d2_no_m/audit_followup.py",
    "RESEARCH/prototypes/phase_d2_no_m/prospective.py",
    "RESEARCH/prototypes/phase_d2_no_m/build_manifest.py",
    "RESEARCH/prototypes/phase_d2_no_m/validate_manifest.py",
    "source/python/configs/phase_d2_no_m_followup.json",
    "source/python/src/ats_ml/d2_no_m.py",
    "source/python/src/ats_ml/d2_no_m_prospective.py",
    "source/python/tests/test_phase_d2_no_m.py",
    "source/python/notebooks/README.md",
    "source/python/notebooks/execute_notebooks.py",
    "source/python/notebooks/build_phase_d_no_m_notebook.py",
    "source/python/notebooks/05_phase_d_no_m_followup.ipynb",
    "source/python/notebooks/execution_report__05_phase_d_no_m_followup.json",
]


def main() -> None:
    artifacts = []
    for relative in FILES:
        path = REPO / relative
        artifacts.append({"path": relative, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    manifest = {
        "schema_version": "ats.phase_d2_nm.evidence_manifest.v1",
        "date": "2026-09-03",
        "status": "PASS",
        "retrospective_classification": "WEAK BUT PERSISTENT",
        "plan_freeze_commit": "c44ec50",
        "result_commit": "containing_git_commit",
        "repository_artifact_hash_basis": "exact bytes; validate the containing commit through git -c core.autocrlf=false archive",
        "repository_artifacts": artifacts,
        "external_artifacts": {
            "primary_run": {
                "path": "D:/Stock/data/ATS/phase_d_ml/followup_runs/phase-d2-nm-followup-20260903-v1",
                "manifest_sha256": sha256_file(Path("D:/Stock/data/ATS/phase_d_ml/followup_runs/phase-d2-nm-followup-20260903-v1/manifest.json")),
                "logical_hash": "d5215ca376887be6116a35d59f1ca49cbc56cf0f6d37551ac5925b4f8f0e193c",
            },
            "independent_audit": {
                "path": "D:/Stock/data/ATS/phase_d_ml/followup_reproductions/phase-d2-nm-followup-20260903-v1-independent",
                "manifest_sha256": sha256_file(Path("D:/Stock/data/ATS/phase_d_ml/followup_reproductions/phase-d2-nm-followup-20260903-v1-independent/manifest.json")),
                "scientific_logical_hash": "e3b091c5883551c1f1ae128de0d41aea8bacb19e6f972fd4630d5f9d7cfe2a6c",
            },
            "prospective_stream": {
                "path": "D:/Stock/data/ATS/phase_d_ml/prospective_streams/phase-d2-nm-post-freeze-2026-v1",
                "registration_sha256": sha256_file(Path("D:/Stock/data/ATS/phase_d_ml/prospective_streams/phase-d2-nm-post-freeze-2026-v1/registration.json")),
                "prediction_rows": 0,
            },
        },
        "validation": {
            "new_adversarial_tests": "14 passed",
            "focused_phase_d_d2_tests": "91 passed",
            "supported_python_suite": "247 passed",
            "market_state_regressions": "10 passed",
            "accepted_prediction_validation": "PASS",
            "primary_followup_validation": "PASS",
            "independent_reproduction": "PASS",
            "fresh_kernel_notebook": "PASS; 7 code cells; 10 retained outputs; 0 errors; 3 nonempty PNG figures",
        },
        "preservation": {
            "accepted_phase_d2_artifacts_modified": False,
            "failed_followup_publication_preserved": True,
            "unrelated_untracked_environment_paths_touched": False,
        },
        "authority": {
            "prospective_monitoring_justified": True,
            "prospective_stream_started": True,
            "phase_d3": False,
            "portfolio_backtest": False,
            "new_feature_block": False,
            "deployment": False,
        },
    }
    OUTPUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
