from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any


MANIFEST_PATH = "RESEARCH/PHASE_D2_NO_M_MANIFEST.json"


def _git_bytes(repo: Path, revision: str, relative: str) -> bytes:
    safe = PurePosixPath(relative)
    if safe.is_absolute() or ".." in safe.parts:
        raise ValueError(f"unsafe manifest path: {relative}")
    result = subprocess.run(
        ["git", "-c", "core.autocrlf=false", "show", f"{revision}:{safe.as_posix()}"],
        cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if result.returncode:
        raise FileNotFoundError(result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout


def _working_bytes(repo: Path, relative: str) -> bytes:
    safe = PurePosixPath(relative)
    if safe.is_absolute() or ".." in safe.parts:
        raise ValueError(f"unsafe manifest path: {relative}")
    return (repo / Path(*safe.parts)).read_bytes()


def verify(repo: Path, *, commit: str | None = None, working_tree: bool = False) -> dict[str, Any]:
    if (commit is None) == (not working_tree):
        raise ValueError("select exactly one verification mode")
    reader = (lambda relative: _git_bytes(repo, commit or "", relative)) if commit else (lambda relative: _working_bytes(repo, relative))
    manifest = json.loads(reader(MANIFEST_PATH).decode("utf-8"))
    declared_basis = manifest.get("repository_artifact_hash_basis")
    expected_basis = "git_blob_committed_bytes" if commit else "working_tree_bytes"
    failures: list[dict[str, str]] = []
    if commit and declared_basis != "git_blob_committed_bytes":
        failures.append({"path": MANIFEST_PATH, "reason": f"declared basis is {declared_basis!r}, expected 'git_blob_committed_bytes'"})
    for record in manifest["repository_artifacts"]:
        try:
            payload = reader(record["path"])
        except (OSError, ValueError) as exc:
            failures.append({"path": record["path"], "reason": str(exc)})
            continue
        digest = hashlib.sha256(payload).hexdigest()
        if len(payload) != record["bytes"] or digest != record["sha256"]:
            failures.append({"path": record["path"], "reason": "byte length or SHA-256 mismatch"})
    resolved = None
    if commit:
        resolved = subprocess.run(["git", "rev-parse", commit], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    return {"status": "PASS" if not failures else "FAIL", "mode": expected_basis, "commit": resolved, "checked": len(manifest["repository_artifacts"]), "failures": failures}


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify D2-NM manifest against Git blobs or explicit checkout bytes")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--commit", help="Git revision whose committed blob bytes are authoritative, e.g. HEAD")
    modes.add_argument("--working-tree", action="store_true", help="Explicitly verify filesystem checkout bytes")
    args = parser.parse_args()
    result = verify(args.root.resolve(), commit=args.commit, working_tree=args.working_tree)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
