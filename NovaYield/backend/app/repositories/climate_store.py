"""Mongo persistence boundary for the shared NASA grid-cell daily archive.

This repository is called by the explicit climate loader/sync jobs. Farmer API
services use its read methods only, so a user request never triggers NASA IO or
writes climate_daily rows.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from pymongo import ASCENDING, ReturnDocument, UpdateOne
from pymongo.errors import DuplicateKeyError

from app.integrations.nasa.power import (
    NASA_POWER_PARAMETERS,
    PowerResult,
    nasa_grid_cell_key,
)
from app.models.climate_store import ClimateCell, ClimateDaily


class ClimateGridMismatch(ValueError):
    """Provider returned a different grid geometry than the registered cell."""


class ClimateIncompleteChunk(ValueError):
    """A response did not contain a complete normalized daily date sequence."""


class ClimateStoreRepository:
    """Persist/read climate by NASA-returned cell key, independent of farm IDs."""

    def __init__(self, cell_model: Any = ClimateCell, daily_model: Any = ClimateDaily) -> None:
        self._cell_model = cell_model
        self._daily_model = daily_model

    async def register_cell(
        self,
        *,
        cell_key: str,
        grid_geometry: dict[str, Any],
        spatial_resolution: str | None,
    ) -> ClimateCell:
        """Create one pending cell; geometry determines identity, never farm coordinates."""

        if nasa_grid_cell_key(grid_geometry) != cell_key:
            raise ClimateGridMismatch()
        existing = await self._cell_model.find_one({"cell_key": cell_key})
        if existing is not None:
            if nasa_grid_cell_key(existing.grid_geometry) != cell_key:
                raise ClimateGridMismatch()
            if existing.spatial_resolution is None and spatial_resolution:
                existing.spatial_resolution = spatial_resolution
                existing.updated_at = datetime.now(UTC)
                await existing.save()
            return existing
        cell = self._cell_model(
            cell_key=cell_key,
            grid_geometry=grid_geometry,
            spatial_resolution=spatial_resolution,
        )
        try:
            await cell.insert()
        except DuplicateKeyError:
            existing = await self._cell_model.find_one({"cell_key": cell_key})
            if existing is None:
                raise
            return existing
        return cell

    async def get_cell(self, cell_key: str) -> ClimateCell | None:
        return await self._cell_model.find_one({"cell_key": cell_key})

    async def get_daily_records(
        self,
        *,
        cell_key: str,
        start_date: date,
        end_date: date,
    ) -> list[ClimateDaily]:
        """Read a date-bounded range in ascending day order for deterministic analysis."""

        if end_date < start_date:
            return []
        return await (
            self._daily_model.find(
                {
                    "cell_key": cell_key,
                    "day": {"$gte": start_date, "$lte": end_date},
                }
            )
            .sort([("day", ASCENDING)])
            .to_list()
        )

    async def upsert_power_result(self, *, cell_key: str, result: PowerResult) -> int:
        """Upsert a full normalized chunk while preserving valid values on null refreshes."""

        if nasa_grid_cell_key(result.grid_geometry) != cell_key:
            raise ClimateGridMismatch()
        dates = _expected_dates(result.date_window.start_date, result.date_window.end_date)
        parameter_series = result.parameters
        if set(parameter_series) != set(NASA_POWER_PARAMETERS):
            raise ClimateIncompleteChunk()
        if not any(
            item.value is not None
            for series in parameter_series.values()
            for item in series.daily_values
        ):
            raise ClimateIncompleteChunk()
        for code in NASA_POWER_PARAMETERS:
            if [item.date for item in parameter_series[code].daily_values] != dates:
                raise ClimateIncompleteChunk()

        # Raw PyMongo bulk operations do not pass through Beanie's tuple
        # serializer, so encode provider products as a BSON array explicitly.
        source_products = list(result.provider_metadata.source_products)
        operations: list[UpdateOne] = []
        retrieved_at = result.retrieved_at.astimezone(UTC)
        for index, day in enumerate(dates):
            # Beanie converts `date` fields to BSON datetimes during document
            # writes. This raw PyMongo bulk path must perform that conversion
            # explicitly, using UTC midnight as the stable date identity.
            bson_day = datetime.combine(day, datetime.min.time(), tzinfo=UTC)
            values = {
                "rain_mm": parameter_series["PRECTOTCORR"].daily_values[index].value,
                "t2m_c": parameter_series["T2M"].daily_values[index].value,
                "t2m_max_c": parameter_series["T2M_MAX"].daily_values[index].value,
            }
            # A later fill value must not erase a previously valid source value.
            set_values = {name: value for name, value in values.items() if value is not None}
            set_values.update(updated_at=retrieved_at)
            operations.append(
                UpdateOne(
                    {"cell_key": cell_key, "day": bson_day},
                    {
                        "$setOnInsert": {
                            "cell_key": cell_key,
                            "day": bson_day,
                        },
                        "$set": {**set_values, "source_products": source_products},
                    },
                    upsert=True,
                )
            )
        if not operations:
            raise ClimateIncompleteChunk()
        outcome = await self._daily_model.get_pymongo_collection().bulk_write(
            operations,
            ordered=False,
        )
        return int(outcome.upserted_count + outcome.modified_count)

    async def save_cell_progress(self, cell: ClimateCell) -> None:
        cell.updated_at = datetime.now(UTC)
        await cell.save()

    async def acquire_cell_lock(
        self, *, cell_key: str, worker_id: str, now: datetime, lease_seconds: int
    ) -> bool:
        """Atomically claim a cell for one background worker instance."""

        expires_at = datetime.fromtimestamp(now.timestamp() + lease_seconds, tz=UTC)
        raw = await self._cell_model.get_pymongo_collection().find_one_and_update(
            {
                "cell_key": cell_key,
                "$or": [
                    {"lock_expires_at": {"$exists": False}},
                    {"lock_expires_at": None},
                    {"lock_expires_at": {"$lte": now}},
                    {"lock_owner": worker_id},
                ],
            },
            {"$set": {"lock_owner": worker_id, "lock_expires_at": expires_at}},
            return_document=ReturnDocument.AFTER,
        )
        return raw is not None

    async def release_cell_lock(self, *, cell_key: str, worker_id: str) -> None:
        await self._cell_model.get_pymongo_collection().update_one(
            {"cell_key": cell_key, "lock_owner": worker_id},
            {"$unset": {"lock_owner": "", "lock_expires_at": ""}},
        )

    async def renew_cell_lock(
        self, *, cell_key: str, worker_id: str, now: datetime, lease_seconds: int
    ) -> bool:
        """Extend a live owner lease without taking a lock another worker claimed."""

        expires_at = datetime.fromtimestamp(now.timestamp() + lease_seconds, tz=UTC)
        result = await self._cell_model.get_pymongo_collection().update_one(
            {"cell_key": cell_key, "lock_owner": worker_id, "lock_expires_at": {"$gt": now}},
            {"$set": {"lock_expires_at": expires_at, "updated_at": now}},
        )
        return result.matched_count == 1


def _expected_dates(start_date: date, end_date: date) -> list[date]:
    if end_date < start_date:
        return []
    days = (end_date - start_date).days + 1
    from datetime import timedelta

    return [start_date + timedelta(days=index) for index in range(days)]
