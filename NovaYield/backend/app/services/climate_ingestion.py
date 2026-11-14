"""Resumable NASA climate-cell backfill and 120-day scheduled refresh."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from app.integrations.nasa.power import (
    NASA_POWER_PARAMETERS,
    NASAPowerService,
    PowerRequest,
    PowerResult,
    nasa_grid_cell_key,
)
from app.models.climate_store import ClimateCell, SafeClimateError
from app.repositories.climate_store import ClimateStoreRepository

INITIAL_HISTORY_START = date(1981, 1, 1)
WEEKLY_REFRESH_DAYS = 120
CLIMATE_LOCK_LEASE_SECONDS = 300
CLIMATE_LOCK_RENEW_INTERVAL_SECONDS = 60


def latest_complete_date(*, today: date, publication_lag_days: int) -> date:
    """Avoid requesting days NASA may still be publishing or revising."""

    return today - timedelta(days=publication_lag_days)


def decade_chunks(start: date, end: date) -> tuple[tuple[date, date], ...]:
    """Partition an inclusive span into calendar-aligned ten-year requests."""

    if end < start:
        return ()
    chunks: list[tuple[date, date]] = []
    year = start.year
    while year <= end.year:
        chunk_start = max(start, date(year, 1, 1))
        chunk_end = min(end, date(min(year + 9, 9999), 12, 31))
        chunks.append((chunk_start, chunk_end))
        year += 10
    return tuple(chunks)


def _chunk_key(start: date, end: date) -> str:
    return f"{start.isoformat()}..{end.isoformat()}"


def _grid_coordinates(cell: ClimateCell) -> tuple[float, float]:
    """Convert NASA GeoJSON [longitude, latitude, optional altitude] to API order."""

    coordinates = cell.grid_geometry.get("coordinates")
    if not isinstance(coordinates, (list, tuple)) or len(coordinates) not in {2, 3}:
        raise ValueError("Climate cell geometry is not a valid NASA point.")
    longitude, latitude = coordinates[:2]
    return float(latitude), float(longitude)


def _chunk_has_missing_values(result: PowerResult) -> bool:
    return any(
        item.value is None
        for code in NASA_POWER_PARAMETERS
        for item in result.parameters[code].daily_values
    )


def _safe_error(error: Exception, *, start: date, end: date) -> SafeClimateError:
    """Store only typed error identity and dates, never upstream payload or coordinates."""

    return SafeClimateError(
        code=type(error).__name__,
        message="The NASA climate request did not complete; the affected period can be retried.",
        occurred_at=datetime.now(UTC),
        chunk_start=start,
        chunk_end=end,
    )


class ClimateIngestionService:
    """A background-only writer; API workflow code must not call this service."""

    def __init__(
        self,
        *,
        nasa_service: NASAPowerService,
        repository: ClimateStoreRepository,
        publication_lag_days: int = 3,
        worker_id: str | None = None,
    ) -> None:
        self._nasa = nasa_service
        self._repository = repository
        self._publication_lag_days = publication_lag_days
        self._worker_id = worker_id or str(uuid4())

    async def load_initial_history(self, cell_key: str) -> bool:
        """Load missing decade chunks from 1981; completed chunks survive worker restarts."""

        cell = await self._repository.get_cell(cell_key)
        if cell is None:
            return False
        now = datetime.now(UTC)
        if not await self._repository.acquire_cell_lock(
            cell_key=cell_key,
            worker_id=self._worker_id,
            now=now,
            lease_seconds=CLIMATE_LOCK_LEASE_SECONDS,
        ):
            return False
        lock_lost = asyncio.Event()
        heartbeat = asyncio.create_task(self._maintain_lock(cell_key, lock_lost))
        try:
            cell = await self._repository.get_cell(cell_key)
            if cell is None:
                return False
            cell.load_status = "loading"
            cell.safe_error = None
            await self._repository.save_cell_progress(cell)
            end = latest_complete_date(
                today=datetime.now(UTC).date(),
                publication_lag_days=self._publication_lag_days,
            )
            chunks = decade_chunks(INITIAL_HISTORY_START, end)
            for start, finish in chunks:
                key = _chunk_key(start, finish)
                if key in cell.completed_chunks:
                    continue
                if lock_lost.is_set():
                    return False
                try:
                    result = await self._retrieve(cell, start, finish)
                    if lock_lost.is_set():
                        return False
                    await self._repository.upsert_power_result(cell_key=cell_key, result=result)
                except Exception as error:
                    cell.load_status = "error"
                    cell.safe_error = _safe_error(error, start=start, end=finish)
                    if key not in cell.failed_chunks:
                        cell.failed_chunks.append(key)
                    await self._repository.save_cell_progress(cell)
                    return False
                cell.completed_chunks.append(key)
                if key in cell.failed_chunks:
                    cell.failed_chunks.remove(key)
                cell.has_missing_values = cell.has_missing_values or _chunk_has_missing_values(
                    result
                )
                cell.source_products = tuple(result.provider_metadata.source_products)
                cell.parameter_metadata = _parameter_metadata(result)
                cell.data_through = max(cell.data_through or finish, finish)
                cell.safe_error = None
                await self._repository.save_cell_progress(cell)
            cell.load_status = "partial" if cell.has_missing_values else "ready"
            cell.first_date = INITIAL_HISTORY_START
            cell.data_through = end
            cell.safe_error = None
            await self._repository.save_cell_progress(cell)
            return True
        finally:
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)
            await self._repository.release_cell_lock(cell_key=cell_key, worker_id=self._worker_id)

    async def sync_recent_history(self, cell_key: str) -> bool:
        """Refresh only the last 120 days; a failed refresh never deletes old rows."""

        cell = await self._repository.get_cell(cell_key)
        if cell is None:
            return False
        if cell.load_status not in {"ready", "partial"}:
            return False
        if not await self._repository.acquire_cell_lock(
            cell_key=cell_key,
            worker_id=self._worker_id,
            now=datetime.now(UTC),
            lease_seconds=CLIMATE_LOCK_LEASE_SECONDS,
        ):
            return False
        lock_lost = asyncio.Event()
        heartbeat = asyncio.create_task(self._maintain_lock(cell_key, lock_lost))
        try:
            cell = await self._repository.get_cell(cell_key)
            if cell is None:
                return False
            end = latest_complete_date(
                today=datetime.now(UTC).date(),
                publication_lag_days=self._publication_lag_days,
            )
            start = max(INITIAL_HISTORY_START, end - timedelta(days=WEEKLY_REFRESH_DAYS - 1))
            cell.last_sync_at = datetime.now(UTC)
            try:
                result = await self._retrieve(cell, start, end)
                if lock_lost.is_set():
                    return False
                await self._repository.upsert_power_result(cell_key=cell_key, result=result)
            except Exception as error:
                cell.last_sync_status = "error"
                cell.safe_error = _safe_error(error, start=start, end=end)
                await self._repository.save_cell_progress(cell)
                return False
            cell.last_sync_status = "partial" if _chunk_has_missing_values(result) else "success"
            cell.last_sync_at = datetime.now(UTC)
            cell.has_missing_values = cell.has_missing_values or _chunk_has_missing_values(result)
            cell.data_through = max(cell.data_through or end, end)
            cell.source_products = tuple(result.provider_metadata.source_products)
            cell.parameter_metadata = _parameter_metadata(result)
            cell.safe_error = None
            if cell.load_status != "loading":
                cell.load_status = "partial" if cell.has_missing_values else "ready"
            await self._repository.save_cell_progress(cell)
            return True
        finally:
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)
            await self._repository.release_cell_lock(cell_key=cell_key, worker_id=self._worker_id)

    async def _maintain_lock(self, cell_key: str, lock_lost: asyncio.Event) -> None:
        """Keep the per-cell lease alive during long upstream or bulk-write work."""

        while True:
            await asyncio.sleep(CLIMATE_LOCK_RENEW_INTERVAL_SECONDS)
            try:
                renewed = await self._repository.renew_cell_lock(
                    cell_key=cell_key,
                    worker_id=self._worker_id,
                    now=datetime.now(UTC),
                    lease_seconds=CLIMATE_LOCK_LEASE_SECONDS,
                )
            except Exception:
                lock_lost.set()
                return
            if not renewed:
                lock_lost.set()
                return

    async def _retrieve(self, cell: ClimateCell, start: date, end: date) -> PowerResult:
        latitude, longitude = _grid_coordinates(cell)
        result = await self._nasa.retrieve(
            PowerRequest(
                latitude=latitude,
                longitude=longitude,
                start_date=start,
                end_date=end,
            )
        )
        if nasa_grid_cell_key(result.grid_geometry) != cell.cell_key:
            raise ValueError("NASA returned a different climate grid cell.")
        return result


def _parameter_metadata(result: PowerResult) -> dict[str, dict[str, str | float | None]]:
    return {
        code: {
            "long_name": series.metadata.long_name,
            "source_units": series.metadata.source_units,
            "normalized_units": series.metadata.normalized_units,
            "source": series.metadata.source,
            "spatial_resolution": series.metadata.spatial_resolution,
            "fill_value": series.metadata.fill_value,
        }
        for code, series in result.parameters.items()
    }


def _candidate_cells_for_sync(cells: Iterable[ClimateCell]) -> tuple[str, ...]:
    """Return stable keys for job callers without embedding cell coordinates in logs."""

    return tuple(sorted(cell.cell_key for cell in cells))
