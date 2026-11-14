"""Frontend-facing contracts for the November 2026 Product Direction flow."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.decisions.environmental_analysis import EnvironmentalAnalysis
from app.decisions.product_direction import FarmerPriority, RotationGeneration
from app.schemas.farms import FarmLocationSummary


class ProductDirectionRecommendationRequest(BaseModel):
    """A run can select one priority; farmers cannot submit weather or future dates."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    priority: FarmerPriority | None = None


class FarmEnvironmentalStatusResponse(BaseModel):
    """Owner-safe current climate archive status and derived historical findings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    farm_id: str
    location: FarmLocationSummary
    status: Literal[
        "location_unmapped", "pending", "loading", "ready", "partial", "error", "unavailable"
    ]
    cell_key: str | None = None
    source: str = "NASA POWER Daily API"
    spatial_resolution: str | None = None
    first_date: date | None = None
    data_through: date | None = None
    completed_chunk_count: int = 0
    failed_chunk_count: int = 0
    safe_message: str | None = None
    analysis: EnvironmentalAnalysis | None = None


class ProductDirectionRecommendationResponse(BaseModel):
    """The newly saved top-three deterministic result and its provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    farm_id: str
    created_at: datetime
    environmental_status: FarmEnvironmentalStatusResponse
    environmental_analysis: EnvironmentalAnalysis
    recommendation: RotationGeneration
