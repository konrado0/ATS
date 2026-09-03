from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import nbformat
from nbclient import NotebookClient


if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


NOTEBOOKS = (
    "00_orientation_and_system_map.ipynb",
    "01_data_identity_and_point_in_time.ipynb",
    "02_research_findings_and_diagnostics.ipynb",
    "03_portfolio_ledger_and_end_to_end_flow.ipynb",
    "04_phase_d_pooled_ml_review.ipynb",
    "05_phase_d_no_m_followup.ipynb",
)


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def execute(path: Path) -> dict[str, object]:
    notebook = nbformat.read(path, as_version=4)
    started = time.perf_counter()

    def announce_cell(cell: dict[str, object], cell_index: int) -> None:
        if cell.get("cell_type") != "code":
            return
        first_line = "".join(cell.get("source", "")).splitlines()[0][:80]
        print(f"  cell {cell_index}: {first_line}", flush=True)

    client = NotebookClient(
        notebook,
        timeout=600,
        kernel_name="python3",
        resources={"metadata": {"path": str(path.parent)}},
        allow_errors=False,
        record_timing=True,
        on_cell_start=announce_cell,
    )
    try:
        client.execute()
    finally:
        # Preserve the executed state on failure so the error remains visible.
        nbformat.write(notebook, path)
    elapsed = time.perf_counter() - started
    outputs = sum(len(cell.get("outputs", [])) for cell in notebook.cells if cell.cell_type == "code")
    errors = [
        output
        for cell in notebook.cells
        if cell.cell_type == "code"
        for output in cell.get("outputs", [])
        if output.get("output_type") == "error"
    ]
    if errors:
        raise RuntimeError(f"{path.name} retained {len(errors)} cell errors")
    return {
        "notebook": path.name,
        "elapsed_seconds": round(elapsed, 3),
        "code_cells": sum(cell.cell_type == "code" for cell in notebook.cells),
        "retained_outputs": outputs,
        "cell_errors": 0,
        "bytes": path.stat().st_size,
        "sha256": file_hash(path),
    }


def main() -> None:
    root = Path(__file__).resolve().parent
    requested = tuple(sys.argv[1:]) or NOTEBOOKS
    unknown = sorted(set(requested) - set(NOTEBOOKS))
    if unknown:
        raise ValueError(f"Unknown review notebook(s): {unknown}")

    results: list[dict[str, object]] = []
    for name in requested:
        path = root / name
        if not path.is_file():
            raise FileNotFoundError(path)
        print(f"Executing {name} from a fresh kernel...", flush=True)
        result = execute(path)
        results.append(result)
        print(json.dumps(result, sort_keys=True), flush=True)

    report = {
        "schema_version": "ats.review_notebook_execution.v1",
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "fresh_kernel_per_notebook": True,
        "network_required": False,
        "canonical_data_writes": False,
        "results": results,
    }
    report_name = (
        "execution_report.json"
        if not sys.argv[1:]
        else "execution_report__" + "__".join(Path(name).stem for name in requested) + ".json"
    )
    (root / report_name).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
