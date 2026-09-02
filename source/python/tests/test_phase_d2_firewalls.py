from __future__ import annotations

import pytest

from ats_ml.d2_stages import BLOCKS, require_stage_outcome_access


def test_2024_cannot_open_before_stage2a_is_sealed() -> None:
    with pytest.raises(PermissionError, match="predecessor"):
        require_stage_outcome_access("stage2b", BLOCKS["stage2b"], set())


def test_locked_cannot_open_before_stage2b_is_sealed() -> None:
    with pytest.raises(PermissionError, match="predecessor"):
        require_stage_outcome_access("stage2c", BLOCKS["stage2c"], {"stage2a"})


def test_each_stage_rejects_later_outcome_blocks() -> None:
    with pytest.raises(PermissionError, match="unpermitted"):
        require_stage_outcome_access("stage2a", [*BLOCKS["stage2a"], *BLOCKS["stage2b"]], set())
    require_stage_outcome_access("stage2a", BLOCKS["stage2a"], set())
    require_stage_outcome_access("stage2b", BLOCKS["stage2b"], {"stage2a"})
    require_stage_outcome_access("stage2c", BLOCKS["stage2c"], {"stage2a", "stage2b"})

