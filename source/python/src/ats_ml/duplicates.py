from __future__ import annotations

from dataclasses import dataclass
import re

import numpy as np
import pandas as pd

from ats_ml.contracts import FrozenD0Contract


@dataclass(frozen=True)
class PairMetric:
    left: str
    right: str
    paired_rows: int
    qualifying_sessions: int
    pooled_spearman: float | None
    median_session_percentile_distance: float | None
    exact_duplicate: bool
    algebraic_duplicate: bool
    near_duplicate: bool


def _affine_duplicate(x: np.ndarray, y: np.ndarray) -> bool:
    if len(x) < 3 or np.std(x) == 0.0:
        return bool(np.allclose(x, y, rtol=1e-12, atol=1e-12))
    design = np.column_stack([x, np.ones(len(x))])
    coefficients, *_ = np.linalg.lstsq(design, y, rcond=None)
    residual = y - design @ coefficients
    return bool(np.max(np.abs(residual)) <= 1e-12)


def registry_formula_collision_audit(contract: FrozenD0Contract) -> dict[str, object]:
    """Audit all 30 frozen formula declarations without opening predictor values."""
    by_normalized_formula: dict[str, list[str]] = {}
    block_by_name = {item["canonical_name"]: item["block"] for item in contract.registry["features"]}
    for item in contract.registry["features"]:
        normalized = re.sub(r"\s+", "", str(item["formula"]).lower())
        by_normalized_formula.setdefault(normalized, []).append(item["canonical_name"])
    collisions = [names for names in by_normalized_formula.values() if len(names) > 1]
    outside_p = [names for names in collisions if any(block_by_name[name] != "P" for name in names)]
    if outside_p:
        raise ValueError(f"exact normalized-formula collision outside permitted P reduction: {outside_p}")
    return {
        "registered_feature_count": len(block_by_name),
        "normalized_formula_count": len(by_normalized_formula),
        "normalized_formula_collisions": collisions,
        "outside_p_collision_count": len(outside_p),
        "status": "PASS",
    }


def resolve_p_duplicates(frame: pd.DataFrame, contract: FrozenD0Contract) -> dict[str, object]:
    p_names = contract.feature_blocks["P"]
    if not {"decision_session", *p_names}.issubset(frame.columns):
        raise ValueError("P structural frame is incomplete")
    population = frame.loc[pd.to_datetime(frame["decision_session"]).le(pd.Timestamp("2024-12-30"))].copy()
    coverage = {name: float(population[name].notna().mean()) for name in p_names}
    metrics: list[PairMetric] = []
    edges: list[tuple[str, str]] = []
    for left_index, left in enumerate(p_names):
        for right in p_names[left_index + 1:]:
            paired = population[["decision_session", left, right]].dropna()
            x = paired[left].to_numpy(dtype=float)
            y = paired[right].to_numpy(dtype=float)
            exact = len(paired) > 0 and bool(np.allclose(x, y, rtol=1e-12, atol=1e-12))
            algebraic = len(paired) > 0 and _affine_duplicate(x, y)
            spearman = float(paired[left].corr(paired[right], method="spearman")) if len(paired) >= 2 else np.nan
            distances: list[float] = []
            qualifying_sessions = 0
            for _, group in paired.groupby("decision_session", sort=True):
                if len(group) < 2:
                    continue
                left_rank = group[left].rank(method="average", pct=True)
                right_rank = group[right].rank(method="average", pct=True)
                distances.extend((left_rank - right_rank).abs().tolist())
                qualifying_sessions += 1
            distance = float(np.median(distances)) if distances else np.nan
            near = bool(
                len(paired) >= 10000
                and qualifying_sessions >= 200
                and np.isfinite(spearman)
                and abs(spearman) >= 0.995
                and np.isfinite(distance)
                and distance <= 0.01
            )
            if exact or algebraic or near:
                edges.append((left, right))
            metrics.append(PairMetric(
                left=left,
                right=right,
                paired_rows=len(paired),
                qualifying_sessions=qualifying_sessions,
                pooled_spearman=spearman if np.isfinite(spearman) else None,
                median_session_percentile_distance=distance if np.isfinite(distance) else None,
                exact_duplicate=exact,
                algebraic_duplicate=algebraic,
                near_duplicate=near,
            ))

    parent = {name: name for name in p_names}
    def find(name: str) -> str:
        while parent[name] != name:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name
    def union(left: str, right: str) -> None:
        a, b = find(left), find(right)
        if a != b:
            parent[b] = a
    for left, right in edges:
        union(left, right)
    components: dict[str, list[str]] = {}
    for name in p_names:
        components.setdefault(find(name), []).append(name)
    specs = contract.feature_specs
    order = {name: index for index, name in enumerate(p_names)}
    def preference(name: str) -> tuple[float, int, int, int]:
        spec = specs[name]
        return (-coverage[name], int(spec["lookback_sessions"]), len(spec["raw_dependencies"]), order[name])
    survivors: list[str] = []
    decisions: list[dict[str, object]] = []
    for component in components.values():
        keep = min(component, key=preference)
        survivors.append(keep)
        for remove in component:
            if remove != keep:
                decisions.append({"removed": remove, "retained": keep, "preference": "higher coverage, shorter lookback, fewer raw dependencies, registry order"})
    survivors.sort(key=order.get)
    if len(survivors) < 5:
        raise ValueError("fewer than five P features survive the frozen duplicate rule")
    return {
        "population_cutoff": "2024-12-30",
        "population_rows": len(population),
        "population_sessions": int(population["decision_session"].nunique()),
        "coverage": coverage,
        "pair_metrics": [metric.__dict__ for metric in metrics],
        "decisions": decisions,
        "survivors": survivors,
        "survivor_count": len(survivors),
    }
