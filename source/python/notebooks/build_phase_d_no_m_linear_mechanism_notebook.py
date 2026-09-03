from __future__ import annotations

from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parent
path = ROOT / "06_phase_d_no_m_linear_mechanism_review.ipynb"
nb = nbf.v4.new_notebook()
nb.metadata.kernelspec = {"display_name": "Python 3", "language": "python", "name": "python3"}
nb.metadata.language_info = {"name": "python", "version": "3.12"}


def md(text: str):
    return nbf.v4.new_markdown_cell(text.strip())


def code(text: str):
    return nbf.v4.new_code_cell(text.strip())


nb.cells = [
    md("""
# Phase D2 C+P+X model-mechanism review

This notebook reads sealed prediction and rank-evaluation artifacts only. It
does not fit a model, load a training label, calculate a candidate threshold,
access a network, or write beneath the data root. The evidence is retrospective
hypothesis development and robustness because D2 and D2-NM results motivated
this test.
"""),
    code("""
from pathlib import Path
import hashlib
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from IPython.display import display, Markdown

PRIMARY = Path("D:/Stock/data/ATS/phase_d_ml/mechanism_runs/phase-d2-no-m-linear-mechanism-20260903-v1")
REPRO = Path("D:/Stock/data/ATS/phase_d_ml/mechanism_runs/phase-d2-no-m-linear-mechanism-20260903-v1-reproduction")
EVALUATION = Path("D:/Stock/data/ATS/phase_d_ml/mechanism_evaluation_runs/phase-d2-no-m-linear-mechanism-evaluation-20260903-v1")
INDEPENDENT = Path("D:/Stock/data/ATS/phase_d_ml/mechanism_reproductions/phase-d2-no-m-linear-mechanism-independent-20260903-v1")

def load(name):
    return json.loads((EVALUATION / name).read_text(encoding="utf-8"))

assert all(path.is_dir() for path in (PRIMARY, REPRO, EVALUATION, INDEPENDENT))
assert hashlib.sha256((PRIMARY / "predictions.parquet").read_bytes()).hexdigest() == hashlib.sha256((REPRO / "predictions.parquet").read_bytes()).hexdigest()
integrity, verdict, contrasts, diagnostics = load("integrity.json"), load("verdict.json"), load("contrasts.json"), load("diagnostics.json")
sessions = pd.read_parquet(EVALUATION / "per_session.parquet")
independent = json.loads((INDEPENDENT / "results.json").read_text(encoding="utf-8"))
assert integrity["independent_evaluation_match"] is True
assert verdict["verdict"] == independent["decision_core"]["scientific_verdict_if_all_integrity_checks_pass"]
print("Sealed prediction, reproduction, and two evaluators: PASS")
"""),
    md("""
## What is being separated

`RICH_NO_M_LINEAR − C_LINEAR` measures whether adding P+X helps under the same
Ridge procedure. `RICH_NO_M_LIGHTGBM − RICH_NO_M_LINEAR` then isolates the
increment associated with nonlinear estimation while holding the 18 C+P+X
features fixed. Every practical claim is also protected against both frozen
conventional comparators.
"""),
    code("""
cells = ["C_LINEAR", "C_LIGHTGBM", "RICH_NO_M_LINEAR", "RICH_NO_M_LIGHTGBM"]
cell_table = pd.DataFrame({
    "mean_session_ic": {cell: sessions[f"ic__{cell}"].mean() for cell in cells},
    "median_session_ic": {cell: sessions[f"ic__{cell}"].median() for cell in cells},
})
display(cell_table.style.format("{:+.5f}"))
ax = cell_table["mean_session_ic"].plot(kind="bar", color=["#64748b", "#f59e0b", "#2563eb", "#7c3aed"], figsize=(8, 4))
ax.axhline(0, color="black", linewidth=.8); ax.set_ylabel("Equal-session mean rank IC")
ax.set_title("Pooled model and representation levels"); plt.xticks(rotation=20, ha="right"); plt.tight_layout(); plt.show()
"""),
    code("""
names = ["RIDGE_VS_C_LINEAR", "RIDGE_VS_C_LIGHTGBM", "NONLINEAR_INCREMENT", "LIGHTGBM_VS_C_LINEAR", "LIGHTGBM_VS_C_LIGHTGBM"]
summary = pd.DataFrame([{ 
    "contrast": name,
    "mean_delta": contrasts[name]["pooled_mean_delta"],
    "median_delta": contrasts[name]["pooled_median_delta"],
    "positive_half_years": contrasts[name]["positive_half_year_count"],
    "positive_sessions": contrasts[name]["positive_session_fraction"],
    "interval_low": contrasts[name]["moving_block_95_interval"]["lower"],
    "interval_high": contrasts[name]["moving_block_95_interval"]["upper"],
    "broad_increment": contrasts[name]["broad_increment"],
} for name in names]).set_index("contrast")
display(summary.style.format({"mean_delta":"{:+.5f}", "median_delta":"{:+.5f}", "positive_sessions":"{:.1%}", "interval_low":"{:+.5f}", "interval_high":"{:+.5f}"}))
"""),
    code("""
half = pd.DataFrame({
    "Ridge−C_LINEAR": contrasts["RIDGE_VS_C_LINEAR"]["half_year_mean_deltas"],
    "Ridge−C_LIGHTGBM": contrasts["RIDGE_VS_C_LIGHTGBM"]["half_year_mean_deltas"],
    "LightGBM−Ridge": contrasts["NONLINEAR_INCREMENT"]["half_year_mean_deltas"],
})
display(half.style.format("{:+.5f}"))
ax = half.plot(kind="bar", figsize=(10, 4), color=["#2563eb", "#0ea5e9", "#7c3aed"])
ax.axhline(0, color="black", linewidth=.8); ax.set_ylabel("Mean paired session-IC delta")
ax.set_title("Chronological mechanism evidence"); plt.xticks(rotation=20, ha="right"); plt.tight_layout(); plt.show()
"""),
    code("""
checks = pd.DataFrame({
    "Ridge vs C_LINEAR": contrasts["RIDGE_VS_C_LINEAR"]["broad_increment_checks"],
    "Ridge vs C_LIGHTGBM": contrasts["RIDGE_VS_C_LIGHTGBM"]["broad_increment_checks"],
    "LightGBM vs Ridge": contrasts["NONLINEAR_INCREMENT"]["broad_increment_checks"],
})
display(checks)
display(Markdown(f'''## Mechanical verdict: `{verdict["verdict"]}`

Ridge C+P+X fails against `C_LINEAR`: only
{contrasts["RIDGE_VS_C_LINEAR"]["positive_half_year_count"]}/7 half-years are
positive, the median half-year delta is nonpositive, and leaving out 2023 H1
reverses the pooled delta. LightGBM passes the broad nonlinear-increment gate
with C+P+X held fixed. The accepted LightGBM C+P+X cell retains positive pooled
deltas and at least 4/7 positive half-years against both conventional controls.
'''))
"""),
    code("""
correlation = pd.Series(diagnostics["cpx_mean_session_score_spearman_by_half_year"], name="mean score-rank correlation")
display(correlation.to_frame().style.format("{:.3f}"))
coef = pd.DataFrame({block: record["standardized_coefficients"] for block, record in diagnostics["ridge_coefficients_by_refit"].items()}).T
coef_summary = pd.DataFrame({"positive_refits": (coef > 0).sum(), "negative_refits": (coef < 0).sum(), "median_coefficient": coef.median()}).sort_values("median_coefficient")
display(coef_summary.style.format({"median_coefficient":"{:+.5f}"}))
"""),
    md("""
## Decision boundary

This result permits discussion of a separately frozen 36m-versus-48m rank-only
diagnostic. It does not authorize execution of that diagnostic. The original D2
`STOP` and the existing prospective LightGBM stream remain unchanged. There is
no portfolio, return, alpha, prospective-confirmation, or deployment claim here.
"""),
]

nbf.write(nb, path)
print(path)

