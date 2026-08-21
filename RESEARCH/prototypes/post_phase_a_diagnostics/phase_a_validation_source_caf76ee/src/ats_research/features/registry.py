from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    version: int
    frequency: str
    lookback: str
    dependencies: tuple[str, ...]
    expression_fingerprint: str
    pipeline_fingerprint: str
    code_fingerprint: str

    @property
    def column(self) -> str:
        return f"feature__{self.name}__v{self.version}"


_REGISTRY: dict[str, FeatureSpec] = {}


def _shared_pipeline_fingerprint(function: Callable) -> str:
    package_root = Path(__file__).resolve().parents[1]
    paths = [
        Path(inspect.getsourcefile(function) or "").resolve(),
        Path(__file__).resolve(),
        package_root / "bars.py",
        package_root / "panel.py",
        package_root / "universe.py",
    ]
    digest = hashlib.sha256()
    for path in sorted(set(paths), key=lambda item: item.as_posix()):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
    return digest.hexdigest()


def feature(name: str, version: int, frequency: str, lookback: str, dependencies: tuple[str, ...]) -> Callable:
    def decorate(function: Callable) -> Callable:
        source = inspect.getsource(function).replace("\r\n", "\n").encode("utf-8")
        expression_fingerprint = hashlib.sha256(source).hexdigest()
        pipeline_fingerprint = _shared_pipeline_fingerprint(function)
        fingerprint = hashlib.sha256(
            json.dumps(
                {"expression": expression_fingerprint, "pipeline": pipeline_fingerprint, "dependencies": dependencies},
                sort_keys=True, separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        spec = FeatureSpec(
            name, version, frequency, lookback, dependencies,
            expression_fingerprint, pipeline_fingerprint, fingerprint,
        )
        if name in _REGISTRY:
            raise ValueError(f"duplicate feature registration: {name}")
        _REGISTRY[name] = spec
        setattr(function, "feature_spec", spec)
        return function
    return decorate


def feature_specs() -> tuple[FeatureSpec, ...]:
    return tuple(_REGISTRY[name] for name in sorted(_REGISTRY))
