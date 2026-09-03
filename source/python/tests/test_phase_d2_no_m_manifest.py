from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[3] / "RESEARCH/prototypes/phase_d2_no_m/validate_manifest.py"
SPEC = importlib.util.spec_from_file_location("phase_d2_nm_validate_manifest", SCRIPT)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def _git(repo: Path, *args: str, capture: bool = False):
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=capture)


def test_commit_mode_uses_git_blobs_while_working_tree_mode_sees_windows_crlf(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "ATS Test")
    _git(repo, "config", "user.email", "ats-test@example.invalid")
    _git(repo, "config", "core.autocrlf", "true")
    tracked = repo / "tracked.txt"
    tracked.write_bytes(b"one\ntwo\n")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-qm", "tracked")
    blob = _git(repo, "show", "HEAD:tracked.txt", capture=True).stdout
    manifest = {
        "repository_artifact_hash_basis": "git_blob_committed_bytes",
        "repository_artifacts": [{"path": "tracked.txt", "bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()}],
    }
    manifest_path = repo / "RESEARCH/PHASE_D2_NO_M_MANIFEST.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    _git(repo, "add", "RESEARCH/PHASE_D2_NO_M_MANIFEST.json")
    _git(repo, "commit", "-qm", "manifest")
    tracked.write_bytes(b"one\r\ntwo\r\n")

    assert validator.verify(repo, commit="HEAD")["status"] == "PASS"
    working = validator.verify(repo, working_tree=True)
    assert working["status"] == "FAIL"
    assert working["mode"] == "working_tree_bytes"
    assert working["failures"][0]["path"] == "tracked.txt"
