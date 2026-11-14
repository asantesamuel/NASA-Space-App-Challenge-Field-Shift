"""Run as a separate scheduled process, never as a FastAPI worker or request task.

Examples from backend::

    python -m app.jobs.climate_worker --mode pending --confirm-large-download
    python -m app.jobs.climate_worker --mode weekly

The weekly command is enabled only after a verified historical backfill.
"""

from __future__ import annotations

import argparse
import asyncio

from httpx import AsyncClient

from app.core.config import get_settings
from app.database.connection import MongoConnection
from app.integrations.nasa.power import (
    NASAPowerHttpClient,
    NASAPowerService,
    create_nasa_power_http_client,
)
from app.models.climate_store import ClimateCell
from app.repositories.climate_store import ClimateStoreRepository
from app.services.climate_ingestion import ClimateIngestionService


async def run_worker(mode: str, *, cell_key: str | None, confirm_large_download: bool) -> int:
    settings = get_settings()
    if mode in {"pending", "backfill"} and not confirm_large_download:
        raise ValueError("Initial history loads require --confirm-large-download.")
    if mode == "weekly" and not settings.nasa_climate_weekly_sync_enabled:
        raise ValueError(
            "Weekly sync is disabled until initial history has been verified; enable "
            "NOVAYIELD_NASA_CLIMATE_WEEKLY_SYNC_ENABLED only after that review."
        )

    mongo = MongoConnection(settings)
    http_client: AsyncClient | None = None
    try:
        if not await mongo.connect():
            raise RuntimeError("MongoDB is not ready; climate work did not start.")
        http_client = create_nasa_power_http_client()
        nasa_service = NASAPowerService(NASAPowerHttpClient(http_client))
        repository = ClimateStoreRepository()
        worker = ClimateIngestionService(
            nasa_service=nasa_service,
            repository=repository,
            publication_lag_days=settings.nasa_recent_publication_lag_days,
        )

        if mode == "backfill":
            if not cell_key:
                raise ValueError("--cell-key is required in backfill mode.")
            cells = [cell_key]
        elif mode == "pending":
            cells = [
                cell.cell_key
                for cell in await ClimateCell.find(
                    {"load_status": {"$in": ["pending", "error", "loading"]}}
                ).to_list()
            ]
        else:
            cells = [
                cell.cell_key
                for cell in await ClimateCell.find(
                    {"load_status": {"$in": ["ready", "partial"]}}
                ).to_list()
            ]

        failures = 0
        for key in sorted(set(cells)):
            succeeded = (
                await worker.sync_recent_history(key)
                if mode == "weekly"
                else await worker.load_initial_history(key)
            )
            status = "updated" if succeeded else "skipped or failed"
            print(f"{key}: {status}")
            failures += int(not succeeded)
        print(f"Processed {len(set(cells))} climate cell(s); {failures} did not complete.")
        return 1 if failures else 0
    finally:
        if http_client is not None:
            await http_client.aclose()
        await mongo.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run NovaYield's separate NASA climate worker.")
    parser.add_argument("--mode", choices=("pending", "backfill", "weekly"), required=True)
    parser.add_argument("--cell-key", help="Required for an explicitly targeted backfill.")
    parser.add_argument(
        "--confirm-large-download",
        action="store_true",
        help="Acknowledge that pending/backfill modes may download 1981-to-current history.",
    )
    arguments = parser.parse_args()
    raise SystemExit(
        asyncio.run(
            run_worker(
                arguments.mode,
                cell_key=arguments.cell_key,
                confirm_large_download=arguments.confirm_large_download,
            )
        )
    )


if __name__ == "__main__":
    main()
