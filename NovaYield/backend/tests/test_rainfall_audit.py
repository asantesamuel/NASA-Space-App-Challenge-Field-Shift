import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from app.decisions.rainfall_audit import PILOT_LOCATIONS, compare_pilot, compare_window
from app.jobs.rainfall_audit import AuditError, load_imerg, main


def write_inputs(path: Path, rows: str, **overrides):
    csv_path = path / "imerg.csv"
    data = ("location_key,date,rain_mm\n" + rows).encode()
    csv_path.write_bytes(data)
    manifest = {
        "collection": "GPM_3IMERGDF",
        "collection_version": "07",
        "edition": "V07B",
        "run": "Final",
        "doi": "10.5067/GPM/IMERGDF/DAY/07",
        "source_variable": "precipitation",
        "source_units": "mm/day",
        "normalized_units": "mm/day",
        "time_basis": "UTC 00:00–24:00",
        "grid_degrees": 0.1,
        "extraction": "containing_cell_west_south_inclusive",
        "source_fill_value": -9999.9,
        "latest_source_day_checked": "2025-09-30",
        "retrieved_on": "2026-11-14",
        "coverage_start": "2023-01-01",
        "coverage_end": "2024-12-31",
        "csv_sha256": hashlib.sha256(data).hexdigest(),
        "sample_kind": "fixture",
        **overrides,
    }
    manifest_path = path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return csv_path, manifest_path


def test_imerg_import_keeps_leap_date_zero_and_missing(tmp_path):
    inputs = write_inputs(
        tmp_path, "ejura,2024-02-29,0\nejura,2024-03-01,-9999.9\nejura,2024-03-02,\n"
    )
    _, series = load_imerg(*inputs)
    assert series["ejura"] == {
        date(2024, 2, 29): 0.0,
        date(2024, 3, 1): None,
        date(2024, 3, 2): None,
    }
    rows = compare_pilot({}, series)
    assert len(rows) == 84
    assert sum(row.window_type == "benchmark" for row in rows) == 12
    assert sum(row.window_type == "month" for row in rows) == 72
    february = next(row for row in rows if row.start_date == date(2024, 2, 1))
    assert (february.expected_days, february.imerg_valid_days, february.paired_days) == (29, 1, 0)
    assert february.total_difference_mm is None
    assert {row.location_key for row in rows} == set(PILOT_LOCATIONS)


@pytest.mark.parametrize(
    ("rows", "metadata"),
    [
        ("", {"run": "Early"}),
        ("", {"edition": "V08"}),
        ("", {"source_units": "in/day"}),
        ("", {"time_basis": "local"}),
        ("", {"coordinates": "sensitive"}),
        ("", {"csv_sha256": "0" * 64}),
        ("", {"coverage_end": "2025-01-01"}),
        ("ejura,2022-12-31,1\n", {}),
        ("unknown,2024-02-29,1\n", {}),
        ("ejura,2024-02-29,1\nejura,2024-02-29,2\n", {}),
        ("ejura,2024-02-29,-1\n", {}),
        ("ejura,2024-02-29,NaN\n", {}),
        ("ejura,2024-02-29,inf\n", {}),
    ],
)
def test_invalid_input_is_rejected_before_db(tmp_path, rows, metadata):
    with pytest.raises(AuditError) as caught:
        load_imerg(*write_inputs(tmp_path, rows, **metadata))
    assert "sensitive" not in str(caught.value)


def test_complete_and_partial_paired_metrics():
    first, second, third, last = (date(2024, 3, day) for day in range(1, 5))
    power = {first: 0.0, second: 0.5, third: 1.0, last: 8.0}
    imerg = {first: 0.0, second: 1.0, third: 0.0, last: 4.0}
    result = compare_window("ejura", "benchmark", first, last, power, imerg)
    assert result.paired_days == result.expected_days == 4
    assert result.paired_coverage == 1
    assert result.power_paired_total_mm == 9.5
    assert result.imerg_paired_total_mm == 5
    assert result.total_difference_mm == -4.5
    assert result.mean_daily_difference_mm == -1.125
    assert result.mean_absolute_daily_difference_mm == 1.375
    assert result.power_longest_dry_spell_days == 2
    assert result.imerg_longest_dry_spell_days == 1

    same = compare_window("ejura", "month", first, last, power, power)
    assert same.total_difference_mm == same.mean_absolute_daily_difference_mm == 0
    assert same.power_longest_dry_spell_days is None

    imerg[second] = None
    partial = compare_window("ejura", "benchmark", first, last, power, imerg)
    assert (partial.power_valid_days, partial.imerg_valid_days, partial.paired_days) == (4, 3, 3)
    assert partial.paired_coverage == 0.75
    assert partial.power_paired_total_mm == 9
    assert partial.imerg_paired_total_mm == 4
    assert partial.total_difference_mm == -5
    assert partial.power_longest_dry_spell_days is partial.imerg_longest_dry_spell_days is None


def test_cli_redacts_invalid_input_and_requires_explicit_audit_database(
    tmp_path, capsys, monkeypatch
):
    monkeypatch.delenv("NOVAYIELD_AUDIT_MONGODB_URI", raising=False)
    args = ["--output-dir", str(tmp_path / "report")]
    csv_path, manifest = write_inputs(tmp_path, "")
    args += ["--manifest", str(manifest), "--imerg-csv", str(csv_path)]
    assert main(args) == 1
    assert "dedicated audit MongoDB URI" in capsys.readouterr().err
    manifest.write_text('{"injected_location":"PRIVATE_FIXTURE"}', encoding="utf-8")
    assert main(args) == 1
    assert "PRIVATE_FIXTURE" not in capsys.readouterr().err
    assert not (tmp_path / "report").exists()
