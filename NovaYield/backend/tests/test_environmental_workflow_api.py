"""HTTP contract tests for stored-grid environmental and recommendation workflows."""

from datetime import UTC, date, datetime
from secrets import token_urlsafe
from types import SimpleNamespace
from typing import Any

from beanie import PydanticObjectId
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api.workflows import get_analysis_config_repository, get_climate_store_repository
from app.core.config import Settings
from app.decisions.environmental_analysis import DailyClimateRecord
from app.farms.contracts import LocationCoordinates
from app.farms.routes import (
    get_crop_catalog_repository,
    get_farm_repository,
    get_supported_location_repository,
)
from app.integrations.nasa.power import NASA_POWER_DAILY_ENDPOINT
from app.main import create_app
from app.models.climate_store import AnalysisConfig, ClimateCell
from app.models.crop_catalog import Crop, CropCalendar, PlantingWindow
from app.models.farms import CropHistoryEvent, Farm
from app.models.supported_locations import SupportedLocation
from app.models.users import User
from app.repositories.analysis_config import AnalysisConfigRepository
from app.repositories.rotation_results import RotationResultRepository
from app.rotation_results.routes import get_rotation_result_repository
from app.services.authentication import AUTH_COOKIE_NAME

FRONTEND_ORIGIN = "http://localhost:5173"
CSRF_SECRET = token_urlsafe(32)
LOCATION_SECRET = token_urlsafe(32)


class FakeMongoConnection:
    async def connect(self) -> bool:
        return True

    async def is_ready(self) -> bool:
        return True

    async def close(self) -> None:
        return None


class MemoryFarmRepository:
    def __init__(self, farm: Farm) -> None:
        self.farm = farm
        self.reads = 0

    async def get_by_owner(
        self, *, farm_id: PydanticObjectId, owner_user_id: PydanticObjectId
    ) -> Farm | None:
        self.reads += 1
        if farm_id != self.farm.id or owner_user_id != self.farm.owner_user_id:
            return None
        return self.farm


class MemoryLocationRepository:
    def __init__(self, location: SupportedLocation) -> None:
        self.location = location

    async def get_by_key(self, location_key: str) -> SupportedLocation | None:
        return self.location if location_key == self.location.location_key else None


class MemoryClimateRepository:
    def __init__(self, cell: ClimateCell | None, rows: list[DailyClimateRecord]) -> None:
        self.cell = cell
        self.rows = rows
        self.cell_reads = 0
        self.daily_reads = 0

    async def get_cell(self, cell_key: str) -> ClimateCell | None:
        self.cell_reads += 1
        if self.cell is None or self.cell.cell_key != cell_key:
            return None
        return self.cell

    async def get_daily_records(
        self, *, cell_key: str, start_date: date, end_date: date
    ) -> list[DailyClimateRecord]:
        self.daily_reads += 1
        return [row for row in self.rows if start_date <= row.day <= end_date]


class MemoryCropRepository:
    def __init__(self, crops: list[Crop], calendars: list[CropCalendar]) -> None:
        self.crops = {crop.crop_key: crop for crop in crops}
        self.calendars = calendars

    async def list_crops(self, *, usage: str | None = None) -> list[Crop]:
        if usage == "recommendation":
            return [crop for crop in self.crops.values() if crop.recommendation_candidate]
        return list(self.crops.values())

    async def list_by_keys(self, keys: set[str]) -> list[Crop]:
        return [self.crops[key] for key in sorted(keys) if key in self.crops]

    async def list_calendars(
        self, *, location_key: str, crop_ids: tuple[Any, ...]
    ) -> list[CropCalendar]:
        return [
            calendar
            for calendar in self.calendars
            if calendar.location_key == location_key and calendar.crop_id in crop_ids
        ]


class MemoryAnalysisConfigRepository(AnalysisConfigRepository):
    def __init__(self, config: AnalysisConfig) -> None:
        self.config = config

    async def get_active(self) -> AnalysisConfig:
        return self.config


class MemoryResultRepository(RotationResultRepository):
    def __init__(self) -> None:
        self.saved: list[dict[str, Any]] = []

    async def create_product_direction(self, **values: Any) -> Any:
        self.saved.append(values)
        return SimpleNamespace(id=PydanticObjectId(), created_at=datetime.now(UTC))


def _workflow_fixture(*, cell_status: str = "ready") -> tuple[TestClient, dict[str, Any]]:
    owner_id = PydanticObjectId()
    farm_id = PydanticObjectId()
    maize_id, cowpea_id = PydanticObjectId(), PydanticObjectId()
    history = CropHistoryEvent(
        event_id="history-1",
        crop_id=maize_id,
        crop_key_snapshot="maize",
        sequence_order=1,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 3),
    )
    farm = Farm.model_construct(
        id=farm_id,
        owner_user_id=owner_id,
        schema_version="farm-v3",
        revision=1,
        name="Research plot",
        location_key="ejura",
        location_coordinates=LocationCoordinates(latitude=7.3856, longitude=-1.3562),
        nasa_cell_key="power-test-cell-key",
        soil_texture_key="loamy",
        irrigation_access_key="none",
        history_status="complete",
        crop_history=[history],
        declared_gaps=[],
        labour_capacity="High",
        available_from=date.today(),
        farmer_priority="water_security",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    location = SupportedLocation.model_construct(
        location_key="ejura",
        label="Ejura",
        coordinates=LocationCoordinates(latitude=7.3856, longitude=-1.3562),
        nasa_cell_key="power-test-cell-key",
        nasa_spatial_resolution="NASA POWER grid",
    )
    cell = ClimateCell.model_construct(
        cell_key="power-test-cell-key",
        grid_geometry={"type": "Point", "coordinates": [-1.375, 7.375]},
        spatial_resolution="NASA POWER grid",
        first_date=date(1981, 1, 1),
        data_through=(None if cell_status == "pending" else date(2025, 1, 5)),
        load_status=cell_status,
        completed_chunks=["1981-01-01..1990-12-31"],
        failed_chunks=[],
        source_products=("MERRA2", "POWER"),
        parameter_metadata={},
    )
    rows: list[DailyClimateRecord] = []
    for year in range(1991, 2021):
        for day_number in range(1, 4):
            rows.append(
                DailyClimateRecord(
                    day=date(year, 1, day_number),
                    rain_mm=2.0,
                    t2m_c=25.0,
                    t2m_max_c=30.0,
                )
            )
    rows.extend(
        [
            DailyClimateRecord(day=date(2025, 1, 1), rain_mm=0.0, t2m_max_c=32.0),
            DailyClimateRecord(day=date(2025, 1, 2), rain_mm=0.0, t2m_max_c=32.0),
            DailyClimateRecord(day=date(2025, 1, 3), rain_mm=0.0, t2m_max_c=32.0),
            DailyClimateRecord(day=date(2025, 1, 4), rain_mm=2.0, t2m_max_c=31.0),
            DailyClimateRecord(day=date(2025, 1, 5), rain_mm=1.0, t2m_max_c=31.0),
        ]
    )
    crops = [
        Crop.model_construct(
            id=maize_id,
            crop_key="maize",
            common_name="Maize",
            catalog_status="active",
            catalog_version="test-catalog-v1",
            group="Cereal",
            water_resilience="Medium",
            soil_effect="Draws down",
            maturity_days_min=30,
            maturity_days_max=30,
            labour="Low",
            recommendation_candidate=True,
            parameter_evidence={},
        ),
        Crop.model_construct(
            id=cowpea_id,
            crop_key="cowpea",
            common_name="Cowpea",
            catalog_status="active",
            catalog_version="test-catalog-v1",
            group="Legume",
            water_resilience="High",
            soil_effect="Adds nitrogen",
            maturity_days_min=30,
            maturity_days_max=30,
            labour="Medium",
            recommendation_candidate=True,
            parameter_evidence={},
        ),
    ]
    calendars = [
        CropCalendar.model_construct(
            id=PydanticObjectId(),
            location_key="ejura",
            crop_id=crop.id,
            profile_revision_id=None,
            season_key="year-round-test",
            calendar_version="test-calendar-v1",
            is_active=True,
            planting_window=PlantingWindow(
                start_month_day="01-01",
                end_month_day="12-31",
                crosses_year=False,
            ),
            evidence=None,
            source_note="Synthetic test-only calendar",
            status="provisional",
        )
        for crop in crops
    ]
    config = AnalysisConfig.model_construct(version="test-config-v1", is_active=True)
    farm_repository = MemoryFarmRepository(farm)
    location_repository = MemoryLocationRepository(location)
    climate_repository = MemoryClimateRepository(cell, rows)
    crop_repository = MemoryCropRepository(crops, calendars)
    config_repository = MemoryAnalysisConfigRepository(config)
    result_repository = MemoryResultRepository()
    settings = Settings(
        _env_file=None,
        environment="test",
        auth_cookie_secure=False,
        cors_allowed_origins=FRONTEND_ORIGIN,
        csrf_secret=SecretStr(CSRF_SECRET),
        location_hash_secret=SecretStr(LOCATION_SECRET),
    )
    app = create_app(
        settings,
        mongo_connection_factory=lambda _settings: FakeMongoConnection(),
    )
    user = User.model_construct(id=owner_id, email="farmer@example.com", is_active=True)
    app.dependency_overrides[app.state.current_active_user] = lambda: user
    app.dependency_overrides[get_farm_repository] = lambda: farm_repository
    app.dependency_overrides[get_supported_location_repository] = lambda: location_repository
    app.dependency_overrides[get_climate_store_repository] = lambda: climate_repository
    app.dependency_overrides[get_crop_catalog_repository] = lambda: crop_repository
    app.dependency_overrides[get_analysis_config_repository] = lambda: config_repository
    app.dependency_overrides[get_rotation_result_repository] = lambda: result_repository
    return TestClient(app), {
        "app": app,
        "farm": farm,
        "other_user_id": PydanticObjectId(),
        "farm_repository": farm_repository,
        "location_repository": location_repository,
        "climate_repository": climate_repository,
        "crop_repository": crop_repository,
        "result_repository": result_repository,
    }


def _csrf_headers(client: TestClient) -> dict[str, str]:
    initialized = client.get("/api/v1/auth/csrf", headers={"Origin": FRONTEND_ORIGIN})
    assert initialized.status_code == 204
    token = client.cookies.get("nova_yield_csrf")
    assert token
    return {"Origin": FRONTEND_ORIGIN, "X-CSRF-Token": token}


def test_environment_endpoint_reports_pending_and_never_exposes_coordinates() -> None:
    client, state = _workflow_fixture(cell_status="pending")
    with client:
        response = client.get(f"/api/v1/farms/{state['farm'].id}/environment")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert body["first_date"] is None
    assert body["data_through"] is None
    assert body["safe_message"]
    assert body["analysis"]["status"] == "pending"
    assert body["location"] == {"location_key": "ejura", "label": "Ejura"}
    assert "7.3856" not in response.text
    assert "-1.3562" not in response.text
    assert "latitude" not in response.text
    assert state["climate_repository"].daily_reads == 0


def test_environment_endpoint_reads_persisted_history_and_explains_partial_weather() -> None:
    client, state = _workflow_fixture()
    with client:
        response = client.get(f"/api/v1/farms/{state['farm'].id}/environment")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["data_through"] == "2025-01-05"
    finding = body["analysis"]["crop_windows"][0]
    assert finding["window_type"] == "crop_event"
    assert finding["rainfall_category"] == "Drier"
    assert finding["temperature_category"] == "Hotter"
    assert finding["dry_spell_category"] == "Longer than usual"
    assert finding["source"] == "NASA POWER Daily API"
    assert state["climate_repository"].daily_reads == 1
    assert "coordinates" not in response.text


def test_recommendation_uses_stored_weather_persists_top_three_and_requires_csrf() -> None:
    client, state = _workflow_fixture()
    with client:
        farm_id = state["farm"].id
        # The dependency override supplies a user without a persisted session.
        client.cookies.set(AUTH_COOKIE_NAME, "test-session")
        blocked = client.post(f"/api/v1/farms/{farm_id}/recommendations", json={})
        assert blocked.status_code == 403

        response = client.post(
            f"/api/v1/farms/{farm_id}/recommendations",
            json={"priority": "soil_health"},
            headers=_csrf_headers(client),
        )

    assert response.status_code == 201
    body = response.json()
    recommendation = body["recommendation"]
    assert recommendation["selected_priority"] == "soil_health"
    assert recommendation["status"] == "ranked"
    assert len(recommendation["options"]) == 3
    assert all(len(option["events"]) == 3 for option in recommendation["options"])
    assert all(option["rank"] == index for index, option in enumerate(recommendation["options"], 1))
    assert state["climate_repository"].daily_reads == 1
    assert len(state["result_repository"].saved) == 1
    saved = state["result_repository"].saved[0]
    assert saved["generation"].model_dump(mode="json") == recommendation
    assert saved["climate_cell_key"] == "power-test-cell-key"
    assert "7.3856" not in response.text
    assert "-1.3562" not in response.text
    assert "credentials" not in response.text.casefold()
    assert not hasattr(state["app"].state, "nasa_power_http_client")
    assert NASA_POWER_DAILY_ENDPOINT not in response.text


def test_unowned_farm_is_404_before_location_or_climate_access() -> None:
    client, state = _workflow_fixture()
    current_user = User.model_construct(
        id=state["other_user_id"], email="other@example.com", is_active=True
    )
    state["app"].dependency_overrides[state["app"].state.current_active_user] = lambda: current_user
    with client:
        response = client.get(f"/api/v1/farms/{state['farm'].id}/environment")

    assert response.status_code == 404
    assert response.json()["detail"] == "Farm not found."
    assert state["location_repository"].location.nasa_cell_key == "power-test-cell-key"
    assert state["climate_repository"].cell_reads == 0
