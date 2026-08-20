from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq

from ats_data.config import PhaseBConfig
from ats_data.ingest import stage_us_tables


def test_filename_and_header_tickers_are_retained_and_validity_is_not_inferred(tmp_path: Path) -> None:
    source = tmp_path / "data"
    raw = source / "daily" / "us" / "nasdaq stocks" / "1" / "_prn.us.txt"
    raw.parent.mkdir(parents=True)
    raw.write_text(
        "<TICKER>,<PER>,<DATE>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>,<OPENINT>\n"
        "PRN.US,D,20250102,000000,10,11,9,10.5,100,0\n",
        encoding="utf-8",
    )
    empty = raw.with_name("empty.us.txt")
    empty.write_text("<TICKER>,<PER>,<DATE>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>,<OPENINT>\n", encoding="utf-8")
    malformed = raw.with_name("zzz.us.txt")
    malformed.write_text(
        "<TICKER>,<PER>,<DATE>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>,<OPENINT>\n"
        "ZZZ.US,D,20250102,000000,10,8,9,10.5,100,0\n",
        encoding="utf-8",
    )
    trusted = source / "ATS" / "phase_a" / "runs" / "trusted"; trusted.mkdir(parents=True)
    config = PhaseBConfig(
        phase_root=source / "ATS" / "phase_b", trusted_phase_a_run=trusted,
        source_data_root=source, ingestion_timestamp=datetime(2026, 8, 20, tzinfo=timezone.utc),
        duckdb_memory_limit="128MB", stream_batch_size=1,
    )
    stage = config.phase_root / "staging" / "fixture"; stage.mkdir(parents=True)
    files, report, _paths = stage_us_tables(config, stage)

    aliases = pq.read_table(stage / files["security_aliases"][0]).to_pandas()
    prn = aliases[aliases["raw_identifier"].isin(["PRN.US", "_PRN.US", "PRN", "_PRN"])]
    values = dict(zip(prn["identifier_type"], prn["identifier_value"]))
    assert values["ticker"] == "PRN"
    assert values["source_filename_ticker"] == "_PRN"
    assert aliases["valid_from"].isna().all() and aliases["valid_to"].isna().all()
    assert prn["observed_from"].notna().all() and prn["observed_to"].notna().all()
    empty_aliases = aliases[aliases["provenance"].str.contains("empty.us.txt")]
    assert empty_aliases["valid_from"].isna().all() and empty_aliases["observed_from"].isna().all()
    assert empty_aliases.loc[empty_aliases["identifier_type"] == "ticker", "identifier_value"].isna().all()

    bars = pq.read_table(stage / files["bars"][0])
    assert "ticker_filename_mismatch" in bars["quality_flags"][0].as_py()
    issues = pq.read_table(stage / files["ingestion_issues"][0]).to_pandas()
    assert issues["issue_code"].tolist() == ["ticker_filename_mismatch", "invalid_ohlcv"]
    assert report["ticker_filename_mismatches"] == 1
    assert report["ticker_filename_mismatch_bar_rows"] == 1
    assert report["empty_or_no_bar_listings"] == 2
