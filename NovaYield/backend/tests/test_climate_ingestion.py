"""Focused loader tests: retries, date chunks, bounded refresh, and safe failures."""

from __future__ import annotations

import os
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from pydantic import SecretStr
from pymongo.errors import DuplicateKeyError

from app.core.config import Settings
from app.database.connection import MongoConnection
from app.integrations.nasa.power import (
    NASA_POWER_PARAMETERS,
    DailyValue,
    DateCoverage,
    PowerDateWindow,
    PowerParameterMetadata,
    PowerParameterSeries,
    PowerProviderMetadata,
    PowerResult,
    SeasonalSummary,
    nasa_grid_cell_key,
)
from app.models.climate_store import ClimateCell, ClimateDaily
from app.repositories.climate_store import ClimateIncompleteChunk, ClimateStoreRepository
from app.services.climate_ingestion import (
    INITIAL_HISTORY_START,
    WEEKLY_REFRESH_DAYS,
    ClimateIngestionService,
    decade_chunks,
    latest_complete_date,
)

# NASA's live Daily response includes an optional third GeoJSON coordinate.
GRID = {"type": "Point", "coordinates": [-1.375, 7.375, 0.0]}
CELL_KEY = nasa_grid_cell_key(GRID)


def _chunk_key(start: date, end: date) -> str:
    return f"{start.isoformat()}..{end.isoformat()}"


def _power_result(request: Any, *, all_missing: bool = False) -> PowerResult:
    expected = (request.end_date - request.start_date).days + 1
    coverage = DateCoverage(
        requested_start_date=request.start_date,
        requested_end_date=request.end_date,
        returned_start_date=None,
        returned_end_date=None,
        expected_days=expected,
        valid_days=0 if all_missing else expected,
        missing_days=expected if all_missing else 0,
        coverage_percent=0 if all_missing else 100,
    )
    parameters = {}
    for code in NASA_POWER_PARAMETERS:
        is_rain = code == "PRECTOTCORR"
        metadata = PowerParameterMetadata(
            code=code,
            long_name=code,
            source_units="mm/day" if is_rain else "C",
            normalized_units="mm/day" if is_rain else "°C",
            source="MERRA2",
            spatial_resolution="NASA POWER grid",
            fill_value=-999,
        )
        parameters[code] = PowerParameterSeries(
            metadata=metadata,
            daily_values=[DailyValue(date=request.start_date, value=None if all_missing else 1.0)],
            seasonal_summary=SeasonalSummary(
                method="sum" if is_rain else "mean",
                value=None if all_missing else 1.0,
                units="mm/season" if is_rain else "°C",
                status="unavailable" if all_missing else "complete",
                coverage=coverage,
            ),
        )
    return PowerResult(
        retrieved_at=datetime.now(UTC),
        date_window=PowerDateWindow(start_date=request.start_date, end_date=request.end_date),
        grid_geometry=GRID,
        provider_metadata=PowerProviderMetadata(
            header_title="Synthetic test resolution",
            source_products=["MERRA2"],
            spatial_resolution_note="NASA POWER grid",
        ),
        parameters=parameters,
    )


class FakeRepository:
    def __init__(self, cell: ClimateCell) -> None:
        self.cell = cell
        self.upserts: list[tuple[str, date, date]] = []
        self.saved: list[tuple[str, list[str], list[str], str, str | None]] = []
        self.old_data_revision = 1

    async def get_cell(self, cell_key: str) -> ClimateCell | None:
        return self.cell if cell_key == self.cell.cell_key else None

    async def acquire_cell_lock(self, **_values: Any) -> bool:
        return True

    async def renew_cell_lock(self, **_values: Any) -> bool:
        return True

    async def release_cell_lock(self, **_values: Any) -> None:
        return None

    async def save_cell_progress(self, cell: ClimateCell) -> None:
        self.saved.append(
            (
                cell.load_status,
                list(cell.completed_chunks),
                list(cell.failed_chunks),
                cell.last_sync_status,
                cell.safe_error.message if cell.safe_error else None,
            )
        )

    async def upsert_power_result(self, *, cell_key: str, result: PowerResult) -> int:
        self.upserts.append((cell_key, result.date_window.start_date, result.date_window.end_date))
        self.old_data_revision += 1
        return 1


class FakeNASA:
    def __init__(self, *, fail_attempts: int = 0, all_missing: bool = False) -> None:
        self.requests: list[Any] = []
        self.fail_attempts = fail_attempts
        self.all_missing = all_missing

    async def retrieve(self, request: Any) -> PowerResult:
        self.requests.append(request)
        if self.fail_attempts:
            self.fail_attempts -= 1
            raise TimeoutError("private coordinate and credential must not leak")
        return _power_result(request, all_missing=self.all_missing)


def _cell(*, completed_chunks: list[str] | None = None) -> ClimateCell:
    return ClimateCell.model_construct(
        cell_key=CELL_KEY,
        grid_geometry=GRID,
        spatial_resolution="NASA POWER grid",
        first_date=INITIAL_HISTORY_START,
        data_through=date(2020, 12, 31),
        load_status="ready",
        completed_chunks=completed_chunks or [],
        failed_chunks=[],
        has_missing_values=False,
        source_products=("MERRA2",),
        parameter_metadata={},
        last_sync_status="never",
        safe_error=None,
        lock_owner=None,
        lock_expires_at=None,
    )


def test_decade_chunks_are_inclusive_adjacent_and_start_in_1981() -> None:
    chunks = decade_chunks(date(1981, 1, 1), date(2026, 2, 3))

    assert chunks[0] == (date(1981, 1, 1), date(1990, 12, 31))
    assert chunks[1] == (date(1991, 1, 1), date(2000, 12, 31))
    assert chunks[-1] == (date(2021, 1, 1), date(2026, 2, 3))
    assert all(
        left_end + timedelta(days=1) == right_start
        for (_, left_end), (right_start, _) in zip(chunks, chunks[1:], strict=False)
    )
    assert decade_chunks(date(2020, 1, 1), date(2019, 12, 31)) == ()


def test_initial_loader_retries_only_the_incomplete_chunk() -> None:
    today = date.today()
    end = latest_complete_date(today=today, publication_lag_days=3)
    chunks = decade_chunks(INITIAL_HISTORY_START, end)
    remaining = chunks[-1]
    completed = [_chunk_key(start, finish) for start, finish in chunks[:-1]]
    cell = _cell(completed_chunks=completed)
    cell.failed_chunks = [_chunk_key(*remaining)]
    repository = FakeRepository(cell)
    nasa = FakeNASA(fail_attempts=1)
    worker = ClimateIngestionService(
        nasa_service=nasa,
        repository=repository,
        publication_lag_days=3,
        worker_id="test-worker",
    )

    assert asyncio_run(worker.load_initial_history(CELL_KEY)) is False
    assert repository.upserts == []
    assert cell.load_status == "error"
    assert cell.failed_chunks == [_chunk_key(*remaining)]
    assert "private coordinate" not in (cell.safe_error.message if cell.safe_error else "")

    assert asyncio_run(worker.load_initial_history(CELL_KEY)) is True
    assert len(nasa.requests) == 2
    assert (nasa.requests[1].start_date, nasa.requests[1].end_date) == remaining
    assert repository.upserts == [(CELL_KEY, *remaining)]
    assert cell.load_status == "ready"
    assert cell.failed_chunks == []


def test_weekly_sync_requests_only_the_last_120_days() -> None:
    cell = _cell()
    repository = FakeRepository(cell)
    nasa = FakeNASA()
    worker = ClimateIngestionService(
        nasa_service=nasa,
        repository=repository,
        publication_lag_days=3,
        worker_id="weekly-worker",
    )

    assert asyncio_run(worker.sync_recent_history(CELL_KEY)) is True
    end = latest_complete_date(today=date.today(), publication_lag_days=3)
    assert nasa.requests[0].end_date == end
    assert nasa.requests[0].start_date == max(
        INITIAL_HISTORY_START, end - timedelta(days=WEEKLY_REFRESH_DAYS - 1)
    )
    assert (nasa.requests[0].end_date - nasa.requests[0].start_date).days + 1 == 120
    assert cell.last_sync_status == "success"


def test_failed_weekly_refresh_keeps_existing_rows_and_records_safe_failure() -> None:
    cell = _cell()
    repository = FakeRepository(cell)
    original_revision = repository.old_data_revision
    nasa = FakeNASA(fail_attempts=1)
    worker = ClimateIngestionService(
        nasa_service=nasa,
        repository=repository,
        publication_lag_days=3,
        worker_id="weekly-worker",
    )

    assert asyncio_run(worker.sync_recent_history(CELL_KEY)) is False
    assert repository.old_data_revision == original_revision
    assert repository.upserts == []
    assert cell.last_sync_status == "error"
    assert cell.load_status == "ready"
    assert cell.safe_error is not None
    assert "private coordinate" not in cell.safe_error.message
    assert "credential" not in cell.safe_error.message


def test_chunk_with_no_valid_values_is_not_marked_complete() -> None:
    class FakeBulkCollection:
        called = False

        async def bulk_write(self, *_args: Any, **_kwargs: Any) -> Any:
            self.called = True
            return type("Outcome", (), {"upserted_count": 0, "modified_count": 0})()

    class FakeDailyModel:
        collection = FakeBulkCollection()

        @classmethod
        def get_pymongo_collection(cls) -> FakeBulkCollection:
            return cls.collection

    request = type(
        "Request",
        (),
        {"start_date": date(2026, 1, 1), "end_date": date(2026, 1, 1)},
    )()
    all_missing = _power_result(request, all_missing=True)
    repository = ClimateStoreRepository(daily_model=FakeDailyModel)

    with pytest.raises(ClimateIncompleteChunk):
        asyncio_run(repository.upsert_power_result(cell_key=CELL_KEY, result=all_missing))
    assert FakeDailyModel.collection.called is False


def test_null_refresh_values_are_omitted_from_update_fields() -> None:
    class FakeBulkCollection:
        operations: list[Any] = []

        async def bulk_write(self, operations: list[Any], **_kwargs: Any) -> Any:
            self.operations = operations
            return type("Outcome", (), {"upserted_count": 0, "modified_count": 1})()

    class FakeDailyModel:
        collection = FakeBulkCollection()

        @classmethod
        def get_pymongo_collection(cls) -> FakeBulkCollection:
            return cls.collection

    request = type(
        "Request",
        (),
        {"start_date": date(2026, 1, 1), "end_date": date(2026, 1, 1)},
    )()
    result = _power_result(request)
    result.parameters["T2M"].daily_values[0].value = None
    repository = ClimateStoreRepository(daily_model=FakeDailyModel)

    assert asyncio_run(repository.upsert_power_result(cell_key=CELL_KEY, result=result)) == 1
    update = FakeDailyModel.collection.operations[0]._doc
    assert update["$set"]["rain_mm"] == 1.0
    assert update["$set"]["t2m_max_c"] == 1.0
    assert update["$set"]["source_products"] == ["MERRA2"]
    assert "t2m_c" not in update["$set"]


def test_climate_daily_declares_a_unique_cell_and_day_index() -> None:
    index = next(
        index
        for index in ClimateDaily.Settings.indexes
        if index.document["name"] == "uq_climate_daily_cell_day"
    )

    assert index.document["key"] == {"cell_key": 1, "day": 1}
    assert index.document["unique"] is True


def test_real_mongo_upsert_accepts_normalized_power_result() -> None:
    """Exercise BSON serialization for the raw PyMongo bulk-write boundary."""

    uri = os.getenv("NOVAYIELD_TEST_MONGODB_URI")
    if not uri:
        pytest.skip("Set NOVAYIELD_TEST_MONGODB_URI to run the climate MongoDB integration test")

    async def run() -> None:
        database_name = f"ny_climate_test_{uuid4().hex}"
        connection = MongoConnection(
            Settings(
                _env_file=None,
                mongodb_uri=SecretStr(uri),
                mongodb_database_name=database_name,
            ),
            document_model_loader=lambda: (ClimateCell, ClimateDaily),
        )
        connected = False
        try:
            connected = await connection.connect()
            assert connected
            repository = ClimateStoreRepository()
            await repository.register_cell(
                cell_key=CELL_KEY,
                grid_geometry=GRID,
                spatial_resolution="synthetic fixture resolution",
            )
            request = type(
                "Request",
                (),
                {"start_date": date(2026, 1, 1), "end_date": date(2026, 1, 1)},
            )()
            result = _power_result(request)

            assert await repository.upsert_power_result(cell_key=CELL_KEY, result=result) == 1
            rows = await repository.get_daily_records(
                cell_key=CELL_KEY,
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 1),
            )
            assert len(rows) == 1
            assert rows[0].rain_mm == 1.0
            assert rows[0].t2m_c == 1.0
            assert rows[0].t2m_max_c == 1.0
            assert rows[0].source_products == ("MERRA2",)

            indexes = await ClimateDaily.get_pymongo_collection().index_information()
            unique_index = indexes["uq_climate_daily_cell_day"]
            assert unique_index["unique"] is True
            with pytest.raises(DuplicateKeyError):
                await ClimateDaily.get_pymongo_collection().insert_one(
                    {
                        "cell_key": CELL_KEY,
                        "day": datetime(2026, 1, 1, tzinfo=UTC),
                    }
                )
        finally:
            try:
                if connected:
                    await connection.client.drop_database(database_name)
            finally:
                await connection.close()

    asyncio_run(run())


def asyncio_run(coroutine: Any) -> Any:
    """Keep these synchronous pytest cases independent of async pytest plugins."""

    import asyncio

    return asyncio.run(coroutine)
