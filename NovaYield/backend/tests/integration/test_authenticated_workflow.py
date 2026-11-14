"""Opt-in real-Mongo tests for the current stored-climate farmer workflow.

The test creates and drops only a uniquely named database on an explicitly
configured local Mongo listener. Crop evidence comes from the normal seed
catalog; weather records are synthetic test fixtures. Farmer requests never
call NASA POWER.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.database.connection import MongoConnection
from app.farms.location_catalog import SUPPORTED_LOCATION_SEEDS
from app.integrations.nasa.power import nasa_grid_cell_key
from app.main import create_app
from app.models.climate_store import ClimateDaily
from app.repositories.analysis_config import AnalysisConfigRepository
from app.repositories.climate_store import ClimateStoreRepository
from app.repositories.crop_catalog import CropCatalogRepository
from app.repositories.farm_reference_options import FarmReferenceRepository
from app.repositories.supported_locations import SupportedLocationRepository
from app.services.authentication import AUTH_COOKIE_NAME, AUTH_CSRF_COOKIE_NAME

FRONTEND_ORIGIN = "http://localhost:5173"
TEST_CSRF_SECRET = "product-direction-test-csrf-secret-at-least-32-bytes"
TEST_LOCATION_SECRET = "product-direction-test-location-key-at-least-32-bytes"
TEST_PASSWORD = f"Nova-{uuid4().hex}-GoodPass9!"
PRIVATE_EJURA_COORDINATES = ("7.3856", "-1.3562")


def _local_test_uri() -> str:
    uri = os.getenv("NOVAYIELD_TEST_MONGODB_URI")
    if not uri:
        pytest.skip("Set NOVAYIELD_TEST_MONGODB_URI to a direct local MongoDB listener")
    parsed = urlsplit(uri)
    if (
        parsed.scheme != "mongodb"
        or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
        or parsed.username is not None
        or parsed.password is not None
        or "," in parsed.netloc
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        pytest.fail("Integration tests require a direct, credential-free local Mongo URI")
    return uri


@asynccontextmanager
async def _isolated_app(uri: str):
    database_name = f"novayield_direction_test_{uuid4().hex}"
    assert database_name.startswith("novayield_direction_test_")
    settings = Settings(
        _env_file=None,
        environment="test",
        mongodb_uri=SecretStr(uri),
        mongodb_database_name=database_name,
        auth_cookie_secure=False,
        cors_allowed_origins=FRONTEND_ORIGIN,
        csrf_secret=SecretStr(TEST_CSRF_SECRET),
        location_hash_secret=SecretStr(TEST_LOCATION_SECRET),
    )
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        mongo: MongoConnection = app.state.mongo
        if not await mongo.is_ready():
            raise AssertionError("Configured local MongoDB is unavailable")
        try:
            yield app
        finally:
            if await mongo.is_ready():
                await mongo.client.drop_database(database_name)


async def _csrf_headers(client: httpx.AsyncClient) -> dict[str, str]:
    response = await client.get("/api/v1/auth/csrf", headers={"Origin": FRONTEND_ORIGIN})
    assert response.status_code == 204
    token = client.cookies.get(AUTH_CSRF_COOKIE_NAME)
    assert token
    return {"Origin": FRONTEND_ORIGIN, "X-CSRF-Token": token}


async def _register_and_login(client: httpx.AsyncClient, email: str) -> dict[str, str]:
    registered = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": TEST_PASSWORD},
        headers=await _csrf_headers(client),
    )
    assert registered.status_code == 201
    assert set(registered.json()) == {"id", "email"}
    logged_in = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": TEST_PASSWORD},
        headers=await _csrf_headers(client),
    )
    assert logged_in.status_code == 204
    assert client.cookies.get(AUTH_COOKIE_NAME)
    return registered.json()


async def _seed_synthetic_climate(app: Any) -> tuple[date, date, str]:
    """Map Ejura to a synthetic NASA grid and insert a tiny reproducible archive."""

    locations = SupportedLocationRepository()
    assert await locations.seed_missing(SUPPORTED_LOCATION_SEEDS) == 3
    geometry = {"type": "Point", "coordinates": [-1.375, 7.375]}
    cell_key = nasa_grid_cell_key(geometry)
    await locations.set_nasa_grid_resolution(
        location_key="ejura",
        cell_key=cell_key,
        grid_geometry=geometry,
        spatial_resolution="synthetic fixture grid",
    )
    climate = ClimateStoreRepository()
    cell = await climate.register_cell(
        cell_key=cell_key,
        grid_geometry=geometry,
        spatial_resolution="synthetic fixture grid",
    )
    event_start = date.today() - timedelta(days=7)
    event_end = date.today() - timedelta(days=5)
    data_through = event_end + timedelta(days=2)
    cell.first_date = date(1981, 1, 1)
    cell.data_through = data_through
    cell.load_status = "ready"
    cell.source_products = ("SYNTHETIC_TEST_FIXTURE",)
    cell.parameter_metadata = {
        "PRECTOTCORR": {"source_units": "mm/day", "normalized_units": "mm/day"},
        "T2M": {"source_units": "C", "normalized_units": "°C"},
        "T2M_MAX": {"source_units": "C", "normalized_units": "°C"},
    }
    await cell.save()

    days = [event_start + timedelta(days=offset) for offset in range(4)]
    for year in range(1991, 2021):
        for observed_day in days:
            reference_day = date(year, observed_day.month, observed_day.day)
            await ClimateDaily(
                cell_key=cell_key,
                day=reference_day,
                rain_mm=2.0,
                t2m_c=25.0,
                t2m_max_c=30.0,
                source_products=("SYNTHETIC_TEST_FIXTURE",),
            ).insert()
    for offset, day in enumerate(days):
        await ClimateDaily(
            cell_key=cell_key,
            day=day,
            rain_mm=2.0 if offset == 3 else 0.5,
            t2m_c=26.0,
            t2m_max_c=32.0,
            source_products=("SYNTHETIC_TEST_FIXTURE",),
        ).insert()
    await AnalysisConfigRepository().seed_default()
    await CropCatalogRepository().seed_missing()
    await FarmReferenceRepository().seed_missing()
    return event_start, event_end, cell_key


def test_authenticated_workflow_uses_stored_climate_and_persists_owner_scoped_results(
    caplog: pytest.LogCaptureFixture,
) -> None:
    uri = _local_test_uri()

    async def run() -> None:
        async with _isolated_app(uri) as app:
            event_start, event_end, cell_key = await _seed_synthetic_climate(app)
            async with (
                httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), base_url="http://testserver"
                ) as owner,
                httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), base_url="http://testserver"
                ) as other,
            ):
                crops = await owner.get("/api/v1/crops?usage=history")
                locations = await owner.get("/api/v1/farms/locations")
                assert crops.status_code == locations.status_code == 200
                assert any(crop["crop_key"] == "maize" for crop in crops.json()["crops"])
                assert locations.json()["locations"][0] == {
                    "location_key": "ejura",
                    "label": "Ejura",
                }
                for coordinate in PRIVATE_EJURA_COORDINATES:
                    assert coordinate not in crops.text + locations.text

                owner_user = await _register_and_login(owner, "owner.direction@example.com")
                other_user = await _register_and_login(other, "other.direction@example.com")
                assert owner_user["id"] != other_user["id"]

                farm_response = await owner.post(
                    "/api/v1/farms",
                    json={
                        "name": "Synthetic test plot",
                        "location_key": "ejura",
                        "soil_texture_key": "loamy",
                        "irrigation_access_key": "none",
                        "crop_history": [
                            {
                                "crop_key": "maize",
                                "sequence_order": 1,
                                "start_date": event_start.isoformat(),
                                "end_date": event_end.isoformat(),
                            }
                        ],
                        "labour_capacity": "High",
                        "farmer_priority": "water_security",
                    },
                    headers=await _csrf_headers(owner),
                )
                assert farm_response.status_code == 201
                farm = farm_response.json()
                farm_id = farm["id"]
                assert farm["schema_version"] == "farm-v3"
                assert farm["available_from"] == date.today().isoformat()
                assert farm["location"] == {"location_key": "ejura", "label": "Ejura"}
                assert "latitude" not in farm_response.text
                assert "longitude" not in farm_response.text
                for coordinate in PRIVATE_EJURA_COORDINATES:
                    assert coordinate not in farm_response.text

                environment = await owner.get(f"/api/v1/farms/{farm_id}/environment")
                assert environment.status_code == 200
                environment_body = environment.json()
                assert environment_body["status"] in {"ready", "partial"}
                assert environment_body["cell_key"] == cell_key
                assert (
                    environment_body["data_through"] == (event_end + timedelta(days=2)).isoformat()
                )
                assert environment_body["analysis"]["reference_period_start"] == 1991
                assert environment_body["analysis"]["reference_period_end"] == 2020
                assert environment_body["analysis"]["crop_windows"][0]["rainfall_total_mm"] == 1.5
                assert "soil-moisture" in environment_body["analysis"]["since_harvest"]["notes"][-1]
                assert "latitude" not in environment.text
                assert "longitude" not in environment.text

                started = datetime.now(UTC)
                recommendation = await owner.post(
                    f"/api/v1/farms/{farm_id}/recommendations",
                    json={"priority": "soil_health"},
                    headers=await _csrf_headers(owner),
                )
                elapsed = (datetime.now(UTC) - started).total_seconds()
                assert recommendation.status_code == 201
                assert elapsed < 60
                result = recommendation.json()
                generation = result["recommendation"]
                assert generation["status"] == "ranked"
                assert generation["selected_priority"] == "soil_health"
                assert 1 <= len(generation["options"]) <= 3
                assert all(len(option["events"]) == 3 for option in generation["options"])
                assert result["environmental_status"]["cell_key"] == cell_key
                assert "latitude" not in recommendation.text
                assert "longitude" not in recommendation.text
                for coordinate in PRIVATE_EJURA_COORDINATES:
                    assert coordinate not in recommendation.text

                # The farmer workflow has no NASA client. Repeating an assessment
                # reads the same stored rows and appends another deterministic result.
                repeated = await owner.post(
                    f"/api/v1/farms/{farm_id}/recommendations",
                    json={"priority": "soil_health"},
                    headers=await _csrf_headers(owner),
                )
                assert repeated.status_code == 201
                assert repeated.json()["recommendation"] == generation

                history = await owner.get(f"/api/v1/farms/{farm_id}/rotation-results")
                assert history.status_code == 200
                assert len(history.json()) == 2
                result_id = history.json()[0]["id"]
                detail = await owner.get(f"/api/v1/farms/{farm_id}/rotation-results/{result_id}")
                assert detail.status_code == 200
                assert detail.json()["product_direction"]["options"]
                assert detail.json()["climate_cell_key"] == cell_key
                assert (
                    detail.json()["climate_data_through"]
                    == (event_end + timedelta(days=2)).isoformat()
                )

                assert (await other.get(f"/api/v1/farms/{farm_id}")).status_code == 404
                assert (await other.get(f"/api/v1/farms/{farm_id}/environment")).status_code == 404
                assert (
                    await other.patch(
                        f"/api/v1/farms/{farm_id}",
                        json={"name": "Unauthorized"},
                        headers=await _csrf_headers(other),
                    )
                ).status_code == 404
                assert (
                    await other.get(f"/api/v1/farms/{farm_id}/rotation-results")
                ).status_code == 404
                assert (
                    await other.get(f"/api/v1/farms/{farm_id}/rotation-results/{result_id}")
                ).status_code == 404

                logout = await owner.post("/api/v1/auth/logout", headers=await _csrf_headers(owner))
                assert logout.status_code == 204
                assert (await owner.get("/api/v1/auth/me")).status_code == 401

                # A missing CSRF header blocks an authenticated state-changing call.
                owner.cookies.set(AUTH_COOKIE_NAME, "test-cookie-for-csrf-check")
                blocked = await owner.patch(
                    f"/api/v1/farms/{farm_id}", json={"name": "Missing token"}
                )
                assert blocked.status_code == 403

                assert app.state.mongo.database.name.startswith("novayield_direction_test_")
                assert (
                    await ClimateDaily.get_pymongo_collection().count_documents(
                        {"cell_key": cell_key}
                    )
                    > 0
                )

        assert TEST_PASSWORD not in caplog.text
        for coordinate in PRIVATE_EJURA_COORDINATES:
            assert coordinate not in caplog.text

    asyncio.run(run())
