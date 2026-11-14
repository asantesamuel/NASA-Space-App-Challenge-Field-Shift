"""Build an offline POWER/IMERG comparison from operator-prepared science data."""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import io
import os
import sys
from dataclasses import asdict, fields
from datetime import UTC, date, datetime, time
from math import isfinite
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError

from app.decisions.rainfall_audit import (
    DRY_DAY_THRESHOLD_MM,
    METHOD_VERSION,
    PILOT_LOCATIONS,
    STUDY_END,
    STUDY_START,
    RainfallComparison,
    compare_pilot,
)
from app.models.climate_store import ClimateDaily
from app.models.supported_locations import SUPPORTED_LOCATION_COLLECTION_NAME

IMERG_DOI = "10.5067/GPM/IMERGDF/DAY/07"
CSV_HEADER = ["location_key", "date", "rain_mm"]
MAX_CSV_BYTES = 256_000
MAX_MANIFEST_BYTES = 4_096
POWER_PRODUCTS = {"MERRA2", "POWER", "GEOS-IT", "GEOSIT"}
MAX_DAILY_RAIN_MM = 10_000  # Reject corrupted numeric inputs, well above real daily rainfall.


class AuditError(ValueError):
    """An error with a fixed operator-safe message."""


class ImergManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    collection: Literal["GPM_3IMERGDF"]
    collection_version: Literal["07"]
    edition: Literal["V07B"]
    run: Literal["Final"]
    doi: Literal["10.5067/GPM/IMERGDF/DAY/07"]
    source_variable: Literal["precipitation", "precipitationCal"]
    source_units: Literal["mm", "mm/day", "mm/hr"]
    normalized_units: Literal["mm/day"]
    time_basis: Literal["UTC 00:00–24:00"]
    grid_degrees: Literal[0.1]
    extraction: Literal["containing_cell_west_south_inclusive"]
    source_fill_value: float = Field(lt=0)
    latest_source_day_checked: date
    retrieved_on: date
    coverage_start: date
    coverage_end: date
    csv_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sample_kind: Literal["fixture", "real"]

    @model_validator(mode="after")
    def coverage_is_bounded(self) -> Self:
        if not STUDY_START <= self.coverage_start <= self.coverage_end <= STUDY_END:
            raise ValueError("Coverage must be inside the study.")
        if not self.coverage_end <= self.latest_source_day_checked <= self.retrieved_on:
            raise ValueError("Coverage exceeds checked source availability.")
        return self


def _read_bounded(path: Path, limit: int) -> bytes:
    with path.open("rb") as stream:
        content = stream.read(limit + 1)
    if len(content) > limit:
        raise AuditError("Input file exceeds the audit size limit.")
    return content


def _rain_value(value: float) -> float:
    if not isfinite(value) or not 0 <= value <= MAX_DAILY_RAIN_MM:
        raise AuditError("Invalid daily rainfall value.")
    return value


def load_imerg(
    csv_path: Path, manifest_path: Path
) -> tuple[ImergManifest, dict[str, dict[date, float | None]]]:
    try:
        manifest = ImergManifest.model_validate_json(
            _read_bounded(manifest_path, MAX_MANIFEST_BYTES)
        )
    except ValidationError:
        raise AuditError(
            "Incompatible IMERG manifest, provenance, units or UTC coverage."
        ) from None
    content = _read_bounded(csv_path, MAX_CSV_BYTES)
    if hashlib.sha256(content).hexdigest() != manifest.csv_sha256:
        raise AuditError("IMERG CSV checksum does not match the manifest.")
    series: dict[str, dict[date, float | None]] = {location: {} for location in PILOT_LOCATIONS}
    try:
        reader = csv.reader(io.StringIO(content.decode("utf-8-sig"), newline=""), strict=True)
        if next(reader, None) != CSV_HEADER:
            raise AuditError("Expected the IMERG CSV header location_key,date,rain_mm.")
        for location, raw_day, raw_rain in reader:
            day = date.fromisoformat(raw_day)
            if day.isoformat() != raw_day or not (
                manifest.coverage_start <= day <= manifest.coverage_end
            ):
                raise AuditError("IMERG day must be ISO formatted and inside manifest coverage.")
            if location not in series or day in series[location]:
                raise AuditError("Unsupported location key or duplicate IMERG date.")
            value = float(raw_rain) if raw_rain else None
            if value is not None:
                if value == manifest.source_fill_value:
                    value = None
                else:
                    value = _rain_value(value)
            series[location][day] = value
    except AuditError:
        raise
    except (ValueError, csv.Error):
        raise AuditError("Invalid IMERG CSV row encoding, date, or rainfall value.") from None
    return manifest, series


def _utc_midnight(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=UTC)


async def read_power(
    uri: str, database_name: str
) -> tuple[dict[str, dict[date, float | None]], dict[str, set[str]]]:
    """Use projections and bounded queries without running Beanie index initialization."""
    async with AsyncMongoClient(uri, tz_aware=True, serverSelectionTimeoutMS=5000) as client:
        database = client[database_name]
        locations = (
            await database[SUPPORTED_LOCATION_COLLECTION_NAME]
            .find(
                {"location_key": {"$in": PILOT_LOCATIONS}},
                {"_id": 0, "location_key": 1, "nasa_cell_key": 1},
            )
            .to_list()
        )
        series = {}
        editions = {}
        by_cell: dict[str, tuple[dict[date, float | None], set[str]]] = {}
        for location in locations:
            key = location.get("nasa_cell_key")
            if not key:
                continue
            if key not in by_cell:
                daily: dict[date, float | None] = {}
                products: set[str] = set()
                async for row in (
                    database[ClimateDaily.Settings.name]
                    .find(
                        {
                            "cell_key": key,
                            "day": {
                                "$gte": _utc_midnight(STUDY_START),
                                "$lte": _utc_midnight(STUDY_END),
                            },
                        },
                        {"_id": 0, "day": 1, "rain_mm": 1, "source_products": 1},
                    )
                    .sort("day", 1)
                ):
                    day = row["day"].date()
                    value = row.get("rain_mm")
                    daily[day] = _rain_value(value) if value is not None else None
                    for product in row.get("source_products", ()):
                        products.add(product if product in POWER_PRODUCTS else "other/undisclosed")
                by_cell[key] = daily, products
            series[location["location_key"]], editions[location["location_key"]] = by_cell[key]
    return series, editions


def build_report(
    manifest: ImergManifest, rows: list[RainfallComparison], power_products: dict[str, set[str]]
) -> str:
    paired_days = sum(row.paired_days for row in rows if row.window_type == "month")
    report = [
        "# Ghana pilot rainfall comparison",
        "",
        f"**Sample:** {manifest.sample_kind.upper()} · **Method:** `{METHOD_VERSION}`",
        "",
        f"Study dates: {STUDY_START} through {STUDY_END}, inclusive. UTC daily windows.",
        f"Paired location-days across the study: {paired_days}.",
        "The benchmark dates are fixed comparison intervals. They describe neither farm "
        "history nor planting guidance.",
        "",
        "- POWER Daily AG uses persisted PRECTOTCORR at the NASA-returned grid cell. "
        "The documented MERRA-2 grid is approximately 0.5° × 0.625°. The archive "
        "contains source product labels but no per-day POWER API version.",
        f"- IMERG Final {manifest.edition}, collection {manifest.collection_version}, "
        f"[DOI](https://doi.org/{IMERG_DOI}), 0.1° native cell. Final incorporates "
        "monthly gauge adjustment and has a multi-month publication lag.",
        f"- IMERG source variable: {manifest.source_variable} ({manifest.source_units}). "
        f"Declared fill: {manifest.source_fill_value}. "
        "Containing native cell with west/south edges inclusive. "
        f"Checked archive through {manifest.latest_source_day_checked}. "
        f"Retrieved {manifest.retrieved_on}. Extract {manifest.coverage_start} to "
        f"{manifest.coverage_end}. CSV SHA-256: `{manifest.csv_sha256}`.",
        f"- A dry day is strictly below {DRY_DAY_THRESHOLD_MM} mm/day. A dry-spell result "
        "requires every benchmark day to have a valid pair.",
        "",
        "Different footprints, input observations, estimation methods and rainfall timing can "
        "cause disagreement. Neither product is a field gauge. Totals use only matched valid "
        "days. Differences are IMERG minus POWER.",
        "",
        "| Location | Window | Start | End | Expected | POWER valid | IMERG valid | Paired | "
        "Coverage | POWER mm | IMERG mm | Difference mm | Mean difference mm/day | "
        "Mean absolute difference mm/day | POWER dry days | IMERG dry days |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | "
        "---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        values = asdict(row)
        values["paired_coverage"] = f"{row.paired_coverage:.1%}"
        report.append(
            "| "
            + " | ".join(
                "—" if value is None else f"{value:.3f}" if isinstance(value, float) else str(value)
                for value in values.values()
            )
            + " |"
        )
    report.extend(("", "POWER archive source labels in the study:", ""))
    for location in PILOT_LOCATIONS:
        sources = ", ".join(sorted(power_products.get(location, ()))) or "unavailable"
        report.append(f"- {location}: {sources}")
    report.extend(
        (
            "",
            "A future gauge comparison should verify data rights and quality flags, align the "
            "actual gauge accumulation periods, and hold out sites or dates before fitting any "
            "correction. Prefer gauges outside the products' adjustments where possible. "
            "[Ghana Meteorological Agency data requests](https://www.meteo.gov.gh/data-request/)",
            "",
        )
    )
    return "\n".join(report)


def write_reports(
    output: Path,
    manifest: ImergManifest,
    rows: list[RainfallComparison],
    products: dict[str, set[str]],
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    with (output / "rainfall-audit.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=[field.name for field in fields(RainfallComparison)]
        )
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)
    (output / "rainfall-audit.md").write_text(
        build_report(manifest, rows, products), encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--imerg-csv", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest, imerg = load_imerg(args.imerg_csv, args.manifest)
        inputs = {args.imerg_csv.resolve(), args.manifest.resolve()}
        if any(
            (args.output_dir / name).resolve() in inputs
            for name in ("rainfall-audit.csv", "rainfall-audit.md")
        ):
            raise AuditError("Choose an output directory that does not overwrite the inputs.")
        uri = os.getenv("NOVAYIELD_AUDIT_MONGODB_URI")
        database = os.getenv("NOVAYIELD_AUDIT_MONGODB_DATABASE")
        if not uri or not database:
            raise AuditError("Set the dedicated audit MongoDB URI and database before running.")
        power, products = asyncio.run(read_power(uri, database))
        rows = compare_pilot(power, imerg)
        write_reports(args.output_dir, manifest, rows, products)
    except AuditError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (OSError, ValueError, TypeError, KeyError, PyMongoError):
        print(
            "Rainfall audit failed reading local files or the read-only archive.", file=sys.stderr
        )
        return 1
    print(f"Rainfall audit wrote {len(rows)} rows ({manifest.sample_kind}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
