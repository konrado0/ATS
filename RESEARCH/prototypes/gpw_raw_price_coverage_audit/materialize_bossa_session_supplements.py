from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from audit_raw_coverage import read_bossa_session_page, sha256


OUTPUT_COLUMNS = [
    "<TICKER>",
    "<DTYYYYMMDD>",
    "<OPEN>",
    "<HIGH>",
    "<LOW>",
    "<CLOSE>",
    "<VOL>",
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Materialize pinned Bossa session-page copies as multi-ticker MST supplements"
    )
    parser.add_argument("--page-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    page_root = args.page_root.resolve()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {output}")
    output.mkdir(parents=True)

    source_manifest_path = page_root / "reference_manifest.json"
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    source_inputs = []
    materialized_outputs = []

    for item in source_manifest["files"]:
        source = page_root / str(item["filename"])
        actual_hash = sha256(source)
        if source.stat().st_size != int(item["byte_length"]) or actual_hash != str(item["sha256"]):
            raise ValueError(f"source manifest mismatch: {source}")
        session_date = pd.Timestamp(item["session_date"])
        parsed = read_bossa_session_page(source, session_date)
        valid = parsed.loc[parsed["valid_raw_bar"]].sort_values("page_ticker", kind="mergesort")
        if valid["page_ticker"].duplicated().any():
            raise ValueError(f"duplicate valid ticker rows in {source}")

        normalized = pd.DataFrame(
            {
                "<TICKER>": valid["page_ticker"],
                "<DTYYYYMMDD>": session_date.strftime("%Y%m%d"),
                "<OPEN>": valid["open"],
                "<HIGH>": valid["high"],
                "<LOW>": valid["low"],
                "<CLOSE>": valid["close"],
                "<VOL>": valid["volume"],
            }
        )[OUTPUT_COLUMNS]
        destination = output / f"bossa_session_{session_date:%Y%m%d}.mst"
        normalized.to_csv(
            destination,
            index=False,
            lineterminator="\n",
            float_format="%.4f",
        )
        source_inputs.append(
            {
                "filename": source.name,
                "session_date": session_date.date().isoformat(),
                "byte_length": source.stat().st_size,
                "sha256": actual_hash,
                "parsed_company_rows": len(parsed),
                "materialized_valid_bars": len(valid),
                "excluded_explicit_no_bar_rows": int((~parsed["valid_raw_bar"]).sum()),
                "session_date_evidence": item["session_date_evidence"],
            }
        )
        materialized_outputs.append(
            {
                "filename": destination.name,
                "session_date": session_date.date().isoformat(),
                "rows": len(normalized),
                "byte_length": destination.stat().st_size,
                "sha256": sha256(destination),
            }
        )

    readme = """# Bossa session supplements

These files preserve valid bars parsed from two owner-supplied Bossa `Akcje i PDA` session-page copies. They are session-scoped, multi-ticker files using the standard seven-column Bossa MST schema.

They are intentionally stored below `mstall` rather than appended to vendor-downloaded per-security files. Consumers must opt in, union by ticker and date, and reject conflicting duplicate bars. Explicit page rows with `-` prices/volume remain excluded; no bars are synthesized.

Source copies and date evidence are pinned under:

`D:\\Stock\\data\\reference\\bossa.pl\\manual_session_pages_2026-08-24`

Recreate into a new empty directory:

```powershell
& 'D:\\Stock\\ATS\\RESEARCH\\prototypes\\environment_repair\\invoke_repaired_python.ps1' `
  'D:\\Stock\\ATS\\RESEARCH\\prototypes\\gpw_raw_price_coverage_audit\\materialize_bossa_session_supplements.py' `
  '--page-root' 'D:\\Stock\\data\\reference\\bossa.pl\\manual_session_pages_2026-08-24' `
  '--output' '<new-empty-output-directory>'
```

Compare the recreated files and `manifest.json` by SHA-256. See `manifest.json` for the parser hash, input hashes, row counts, exclusions, schema, and output hashes.
"""
    readme_path = output / "README.md"
    readme_path.write_text(readme, encoding="utf-8", newline="\n")

    script_path = Path(__file__).resolve()
    parser_path = script_path.with_name("audit_raw_coverage.py")
    manifest = {
        "contract": {
            "format": "multi_ticker_session_scoped_bossa_mst",
            "schema": OUTPUT_COLUMNS,
            "valid_bars_only": True,
            "no_synthesized_bars": True,
            "duplicate_policy": "consumer_must_reject_conflicting_ticker_date_duplicates",
            "per_security_vendor_files_modified": False,
        },
        "materializer": {"path": str(script_path), "sha256": sha256(script_path)},
        "page_parser": {"path": str(parser_path), "sha256": sha256(parser_path)},
        "source_manifest": {
            "path": str(source_manifest_path),
            "sha256": sha256(source_manifest_path),
        },
        "source_inputs": source_inputs,
        "outputs": materialized_outputs
        + [
            {
                "filename": readme_path.name,
                "byte_length": readme_path.stat().st_size,
                "sha256": sha256(readme_path),
            }
        ],
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
