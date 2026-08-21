from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Sequence

from pydantic import BaseModel

from ats_contracts.portfolio import LEDGER_MODELS, LedgerEvent, TargetWeightIntent
from ats_portfolio.hashing import canonical_json


def logical_rows_hash(rows: Sequence[BaseModel]) -> str:
    digest = hashlib.sha256()
    for row in sorted(rows, key=lambda value: getattr(value, "sequence", 0)):
        digest.update(canonical_json(row.model_dump(mode="json")))
        digest.update(b"\n")
    return digest.hexdigest()


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return str(value)


def write_ledger(path: Path, name: str, rows: Sequence[LedgerEvent]) -> str:
    model = LEDGER_MODELS[name]
    fields = list(model.model_fields)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in sorted(rows, key=lambda value: value.sequence):
            dumped = row.model_dump(mode="json")
            writer.writerow({field: _cell(dumped.get(field)) for field in fields})
    return logical_rows_hash(rows)


def _parse_cell(value: str) -> Any:
    if value == "":
        return None
    if value.startswith("[") or value.startswith("{"):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def read_ledger(path: Path, name: str) -> list[LedgerEvent]:
    model = LEDGER_MODELS[name]
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = []
        for raw in csv.DictReader(handle):
            parsed = {key: _parse_cell(value) for key, value in raw.items()}
            rows.append(model.model_validate(parsed))
    return rows


def write_intents(path: Path, rows: Sequence[TargetWeightIntent]) -> str:
    fields = list(TargetWeightIntent.model_fields)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in sorted(rows, key=lambda value: (value.batch_id, value.security_id, value.intent_id)):
            dumped = row.model_dump(mode="json")
            writer.writerow({field: _cell(dumped.get(field)) for field in fields})
    digest = hashlib.sha256()
    for row in sorted(rows, key=lambda value: (value.batch_id, value.security_id, value.intent_id)):
        digest.update(canonical_json(row.model_dump(mode="json")))
        digest.update(b"\n")
    return digest.hexdigest()


def read_intents(path: Path) -> list[TargetWeightIntent]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [TargetWeightIntent.model_validate({key: _parse_cell(value) for key, value in raw.items()}) for raw in csv.DictReader(handle)]


def logical_intents_hash(rows: Sequence[TargetWeightIntent]) -> str:
    digest = hashlib.sha256()
    for row in sorted(rows, key=lambda value: (value.batch_id, value.security_id, value.intent_id)):
        digest.update(canonical_json(row.model_dump(mode="json")))
        digest.update(b"\n")
    return digest.hexdigest()
