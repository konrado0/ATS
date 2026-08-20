from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from ats_research.validation import _validate_source_snapshot, validate_run_directory


TRUSTED = Path(r"D:\Stock\data\ATS\phase_a\runs\phasea-2a2b3898aba37814")


@pytest.mark.skipif(not TRUSTED.exists(), reason="trusted local Phase A archive unavailable")
def test_phase_b_checkout_changes_do_not_invalidate_phase_a_archive() -> None:
    result = validate_run_directory(TRUSTED)
    assert result["passed"] is True
    assert result["validation_mode"] == "archive_integrity"
    # This checkout intentionally differs from the archived Phase A snapshot.
    with pytest.raises(ValueError, match="current code hash mismatch"):
        validate_run_directory(TRUSTED, strict_current_checkout=True)


@pytest.mark.skipif(not TRUSTED.exists(), reason="trusted local Phase A archive unavailable")
def test_phase_a_source_snapshot_tampering_is_detected(tmp_path: Path) -> None:
    manifest = json.loads((TRUSTED / "manifest.json").read_text(encoding="utf-8"))
    target = tmp_path / "run" / "artifacts"
    target.mkdir(parents=True)
    copied = target / "source_snapshot.zip"
    shutil.copy2(TRUSTED / "artifacts" / "source_snapshot.zip", copied)
    _validate_source_snapshot(target.parent, manifest, Path("."))
    payload = bytearray(copied.read_bytes()); payload[len(payload) // 2] ^= 0xFF; copied.write_bytes(payload)
    with pytest.raises(Exception):
        _validate_source_snapshot(target.parent, manifest, Path("."))
