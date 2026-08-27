from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary", type=Path, required=True)
    parser.add_argument("--reproduction", type=Path, required=True)
    parser.add_argument("--supplement", type=Path, required=True)
    parser.add_argument("--supplement-reproduction", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--reproduction-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    allowed = Path(r"D:\Stock\data\ATS\phase_a_v2_research\decision_records").resolve()
    if not output.is_relative_to(allowed) or output.exists():
        raise ValueError("decision record must be a new directory beneath the decision-record root")

    manifests = {}
    for name, root in {
        "primary": args.primary,
        "reproduction": args.reproduction,
        "supplement": args.supplement,
        "supplement_reproduction": args.supplement_reproduction,
    }.items():
        path = root / "manifest.json"
        manifests[name] = json.loads(path.read_text(encoding="utf-8"))
    if manifests["primary"]["logical_payload_hash"] != manifests["reproduction"]["logical_payload_hash"]:
        raise RuntimeError("main analysis reproduction mismatch")
    if manifests["supplement"]["logical_payload_hash"] != manifests["supplement_reproduction"]["logical_payload_hash"]:
        raise RuntimeError("supplement reproduction mismatch")

    output.mkdir(parents=True)
    shutil.copy2(args.report, output / "PHASE_A_V2_RESEARCH_DECISION.md")
    shutil.copy2(args.audit, output / "final_completion_audit.csv")
    shutil.copy2(args.reproduction_audit, output / "reproduction_audit.json")
    shutil.copy2(Path(__file__), output / "source_snapshot.py")
    files = sorted(path for path in output.iterdir() if path.is_file())
    manifest = {
        "schema_version": "ats.phase_a_v2_research.decision_record.v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "recommendation": "CONTINUE TO A BOUNDED STRATEGY TEST",
        "immutable_output": str(output),
        "main_logical_payload_hash": manifests["primary"]["logical_payload_hash"],
        "supplement_logical_payload_hash": manifests["supplement"]["logical_payload_hash"],
        "source_manifest_sha256": {
            "primary": sha256_file(args.primary / "manifest.json"),
            "reproduction": sha256_file(args.reproduction / "manifest.json"),
            "supplement": sha256_file(args.supplement / "manifest.json"),
            "supplement_reproduction": sha256_file(args.supplement_reproduction / "manifest.json"),
        },
        "files": {path.name: {"bytes": path.stat().st_size, "sha256": sha256_file(path)} for path in files},
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
