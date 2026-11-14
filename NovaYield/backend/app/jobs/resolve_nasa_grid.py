"""Operator command: map one supported place to NASA's returned grid geometry.

Example from backend/: ``python -m app.jobs.resolve_nasa_grid --location-key ejura``
This makes one small live NASA request and never prints or stores farm coordinates.
It does not start the historical backfill.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime

from httpx import AsyncClient

from app.core.config import get_settings
from app.database.connection import MongoConnection
from app.farms.location_catalog import SUPPORTED_LOCATION_SEEDS
from app.integrations.nasa.power import (
    NASAPowerHttpClient,
    NASAPowerService,
    PowerRequest,
    create_nasa_power_http_client,
    nasa_grid_cell_key,
)
from app.repositories.climate_store import ClimateStoreRepository
from app.repositories.supported_locations import SupportedLocationRepository
from app.services.climate_ingestion import latest_complete_date


async def resolve_location(location_key: str) -> str:
    settings = get_settings()
    mongo = MongoConnection(settings)
    http_client: AsyncClient | None = None
    try:
        if not await mongo.connect():
            raise RuntimeError("MongoDB is not ready; location grid mapping was not saved.")
        locations = SupportedLocationRepository()
        location = await locations.get_by_key(location_key)
        if location is None:
            raise ValueError(f"Unknown supported location key: {location_key}")
        http_client = create_nasa_power_http_client()
        service = NASAPowerService(NASAPowerHttpClient(http_client))
        day = latest_complete_date(
            today=datetime.now(UTC).date(),
            publication_lag_days=settings.nasa_recent_publication_lag_days,
        )
        result = await service.retrieve(
            PowerRequest(
                latitude=location.coordinates.latitude,
                longitude=location.coordinates.longitude,
                start_date=day,
                end_date=day,
            )
        )
        cell_key = nasa_grid_cell_key(result.grid_geometry)
        await locations.set_nasa_grid_resolution(
            location_key=location_key,
            cell_key=cell_key,
            grid_geometry=result.grid_geometry,
            spatial_resolution=result.provider_metadata.spatial_resolution_note,
        )
        await ClimateStoreRepository().register_cell(
            cell_key=cell_key,
            grid_geometry=result.grid_geometry,
            spatial_resolution=result.provider_metadata.spatial_resolution_note,
        )
        return cell_key
    finally:
        if http_client is not None:
            await http_client.aclose()
        await mongo.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve a supported place to its NASA grid cell.")
    parser.add_argument(
        "--location-key",
        required=True,
        choices=tuple(seed.location_key for seed in SUPPORTED_LOCATION_SEEDS),
    )
    arguments = parser.parse_args()
    cell_key = asyncio.run(resolve_location(arguments.location_key))
    print(f"Mapped {arguments.location_key} to NASA grid key {cell_key}; climate load is pending.")


if __name__ == "__main__":
    main()
