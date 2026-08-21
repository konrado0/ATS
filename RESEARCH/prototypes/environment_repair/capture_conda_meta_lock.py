from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    prefix = Path(sys.prefix).resolve()
    records = []
    for path in sorted((prefix / "conda-meta").glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        records.append(
            {
                "name": raw.get("name"),
                "version": raw.get("version"),
                "build": raw.get("build"),
                "build_number": raw.get("build_number"),
                "channel": raw.get("channel"),
                "subdir": raw.get("subdir"),
                "url": raw.get("url"),
                "md5": raw.get("md5"),
                "sha256": raw.get("sha256"),
                "depends": raw.get("depends", []),
                "record_file": path.name,
                "record_sha256": file_hash(path),
            }
        )

    distributions = sorted(
        (
            {
                "name": distribution.metadata.get("Name", distribution.name),
                "version": distribution.version,
            }
            for distribution in importlib.metadata.distributions()
        ),
        key=lambda item: (str(item["name"]).lower(), str(item["version"])),
    )

    lock = {
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "prefix": str(prefix),
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "conda_record_count": len(records),
        "python_distribution_count": len(distributions),
        "conda_records": records,
        "python_distributions": distributions,
    }

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    digest = file_hash(output)
    output.with_suffix(output.suffix + ".sha256").write_text(digest + "\n", encoding="ascii")
    print(json.dumps({"output": str(output), "sha256": digest, "records": len(records)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
