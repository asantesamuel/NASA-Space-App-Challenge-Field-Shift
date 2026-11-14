"""Grid-cell climate storage and versioned decision configuration documents."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, Literal

from beanie import Document
from pydantic import BaseModel, ConfigDict, Field
from pymongo import ASCENDING, IndexModel

from app.database.registry import register_document_model

ClimateLoadStatus = Literal["pending", "loading", "ready", "partial", "error"]


class SafeClimateError(BaseModel):
    """Provider error metadata safe for operator display and logs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str
    occurred_at: datetime
    chunk_start: date | None = None
    chunk_end: date | None = None


@register_document_model
class ClimateCell(Document):
    """One NASA-returned grid geometry and its historical backfill/sync state."""

    cell_key: str
    grid_geometry: dict[str, Any]
    spatial_resolution: str | None = None
    first_date: date = date(1981, 1, 1)
    data_through: date | None = None
    load_status: ClimateLoadStatus = "pending"
    has_missing_values: bool = False
    last_sync_at: datetime | None = None
    last_sync_status: Literal["never", "success", "partial", "error"] = "never"
    source_products: tuple[str, ...] = ()
    parameter_metadata: dict[str, dict[str, Any]] = Field(default_factory=dict)
    completed_chunks: list[str] = Field(default_factory=list)
    failed_chunks: list[str] = Field(default_factory=list)
    safe_error: SafeClimateError | None = None
    lock_owner: str | None = None
    lock_expires_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "climate_cells"
        indexes = [
            IndexModel([("cell_key", ASCENDING)], unique=True, name="uq_climate_cells_key"),
            IndexModel(
                [("load_status", ASCENDING), ("updated_at", ASCENDING)],
                name="ix_climate_cells_load_queue",
            ),
            IndexModel(
                [("load_status", ASCENDING), ("last_sync_at", ASCENDING)],
                name="ix_climate_cells_weekly_sync",
            ),
        ]


@register_document_model
class ClimateDaily(Document):
    """A single daily value row shared by every farm mapped to the same NASA cell."""

    cell_key: str
    day: date
    rain_mm: float | None = None
    t2m_c: float | None = None
    t2m_max_c: float | None = None
    source_products: tuple[str, ...] = ()
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "climate_daily"
        # This unique index also supports reverse day scans. Keep a single
        # compound declaration: Beanie merges index definitions by field set,
        # so a second ascending/descending variant can replace this unique one.
        indexes = [
            IndexModel(
                [("cell_key", ASCENDING), ("day", ASCENDING)],
                unique=True,
                name="uq_climate_daily_cell_day",
            )
        ]


@register_document_model
class AnalysisConfig(Document):
    """One immutable version of the accepted, configurable MVP calculation defaults."""

    version: str
    is_active: bool = False
    dry_day_threshold_mm: float = 1.0
    rainfall_drier_ratio: float = 0.85
    rainfall_wetter_ratio: float = 1.15
    temperature_delta_c: float = 1.0
    dry_spell_percentile: int = 75
    reference_start_year: int = 1991
    reference_end_year: int = 2020
    fast_growth_max_days: int = 75
    medium_growth_max_days: int = 150
    turnaround_days: int = 14
    calendar_horizon_months: int = 24
    starting_weight: int = 1
    step_one_weather_water_weight: int = 2
    preceding_cereal_soil_weight: int = 2
    farmer_priority_adjustment: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "analysis_config"
        indexes = [
            IndexModel([("version", ASCENDING)], unique=True, name="uq_analysis_config_version"),
            IndexModel(
                [("is_active", ASCENDING)],
                unique=True,
                partialFilterExpression={"is_active": True},
                name="uq_analysis_config_active",
            ),
        ]
