"""Owner-safe read/decision orchestration for the Product Direction API."""

from collections.abc import Callable
from datetime import date
from typing import Annotated

from beanie import PydanticObjectId
from fastapi import APIRouter, Body, Depends, HTTPException, status
from pymongo.errors import PyMongoError

from app.decisions.environmental_analysis import (
    CropEventWindow,
    DailyClimateRecord,
    EnvironmentalAnalysis,
    EnvironmentalThresholdConfiguration,
    analyze_farm_history,
)
from app.decisions.product_direction import (
    CropHistoryWeather,
    PlantingCalendar,
    RotationCrop,
    derive_growth_speed,
    generate_ranked_rotations,
)
from app.farms.routes import (
    get_crop_catalog_repository,
    get_farm_repository,
    get_supported_location_repository,
)
from app.models.climate_store import AnalysisConfig, ClimateCell
from app.models.crop_catalog import Crop, CropCalendar
from app.models.farms import Farm
from app.models.supported_locations import SupportedLocation
from app.models.users import User
from app.repositories.analysis_config import AnalysisConfigRepository
from app.repositories.climate_store import ClimateStoreRepository
from app.repositories.crop_catalog import CropCatalogRepository
from app.repositories.farms import FarmRepository
from app.repositories.rotation_results import RotationResultRepository
from app.repositories.supported_locations import SupportedLocationRepository
from app.rotation_results.routes import get_rotation_result_repository
from app.schemas.farms import FarmLocationSummary
from app.schemas.product_direction import (
    FarmEnvironmentalStatusResponse,
    ProductDirectionRecommendationRequest,
    ProductDirectionRecommendationResponse,
)

FARM_NOT_FOUND_DETAIL = "Farm not found."
FARM_HISTORY_NEEDS_REVIEW_DETAIL = (
    "Enter one to three actual dated crop-history events before requesting environmental "
    "context or a rotation comparison."
)
ENVIRONMENTAL_SERVICE_UNAVAILABLE_DETAIL = "Environmental data is temporarily unavailable."
ROTATION_RESULT_UNAVAILABLE_DETAIL = "The rotation result could not be saved. Please retry."
CATALOG_UNAVAILABLE_DETAIL = "The crop and calendar catalogs are temporarily unavailable."
ANALYSIS_CONFIGURATION_UNAVAILABLE_DETAIL = "Decision configuration is temporarily unavailable."


def get_climate_store_repository() -> ClimateStoreRepository:
    return ClimateStoreRepository()


def get_analysis_config_repository() -> AnalysisConfigRepository:
    return AnalysisConfigRepository()


def create_workflow_router(current_active_user: Callable[..., User]) -> APIRouter:
    """Expose read-only climate context and save-only recommendation generation.

    The router never receives a NASA service. It can only read climate_daily via
    ClimateStoreRepository, which keeps all upstream HTTP in the worker boundary.
    """

    router = APIRouter(prefix="/farms", tags=["decision-workflows"])

    @router.get(
        "/{farm_id}/environment",
        response_model=FarmEnvironmentalStatusResponse,
        summary="Read stored climate status and historical crop-window findings",
        responses={
            401: {"description": "Authentication is required."},
            404: {"description": FARM_NOT_FOUND_DETAIL},
            409: {"description": FARM_HISTORY_NEEDS_REVIEW_DETAIL},
            503: {"description": ENVIRONMENTAL_SERVICE_UNAVAILABLE_DETAIL},
        },
    )
    async def get_farm_environment(
        farm_id: PydanticObjectId,
        user: Annotated[User, Depends(current_active_user)],
        farm_repository: Annotated[FarmRepository, Depends(get_farm_repository)],
        location_repository: Annotated[
            SupportedLocationRepository, Depends(get_supported_location_repository)
        ],
        climate_repository: Annotated[
            ClimateStoreRepository, Depends(get_climate_store_repository)
        ],
        config_repository: Annotated[
            AnalysisConfigRepository, Depends(get_analysis_config_repository)
        ],
    ) -> FarmEnvironmentalStatusResponse:
        farm, location = await _load_owned_farm_and_location(
            farm_id=farm_id,
            owner_user_id=user.id,
            farm_repository=farm_repository,
            location_repository=location_repository,
        )
        _require_dated_history(farm)
        try:
            config = await config_repository.get_active()
            if config is None:
                raise HTTPException(
                    status_code=503,
                    detail=ANALYSIS_CONFIGURATION_UNAVAILABLE_DETAIL,
                )
            return await _environment_status(
                farm=farm,
                location=location,
                climate_repository=climate_repository,
                environmental_config=config_repository.environmental_thresholds(config),
            )
        except PyMongoError:
            raise HTTPException(
                status_code=503,
                detail=ENVIRONMENTAL_SERVICE_UNAVAILABLE_DETAIL,
            ) from None

    @router.post(
        "/{farm_id}/recommendations",
        response_model=ProductDirectionRecommendationResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Generate and save the top three farm-specific rotations",
        responses={
            401: {"description": "Authentication is required."},
            403: {"description": "CSRF token verification failed."},
            404: {"description": FARM_NOT_FOUND_DETAIL},
            409: {"description": FARM_HISTORY_NEEDS_REVIEW_DETAIL},
            503: {"description": ROTATION_RESULT_UNAVAILABLE_DETAIL},
        },
    )
    async def generate_recommendations(
        farm_id: PydanticObjectId,
        user: Annotated[User, Depends(current_active_user)],
        farm_repository: Annotated[FarmRepository, Depends(get_farm_repository)],
        location_repository: Annotated[
            SupportedLocationRepository, Depends(get_supported_location_repository)
        ],
        crop_repository: Annotated[CropCatalogRepository, Depends(get_crop_catalog_repository)],
        climate_repository: Annotated[
            ClimateStoreRepository, Depends(get_climate_store_repository)
        ],
        config_repository: Annotated[
            AnalysisConfigRepository, Depends(get_analysis_config_repository)
        ],
        result_repository: Annotated[
            RotationResultRepository, Depends(get_rotation_result_repository)
        ],
        request_body: Annotated[ProductDirectionRecommendationRequest | None, Body()] = None,
    ) -> ProductDirectionRecommendationResponse:
        """Read persisted inputs, run pure analysis/scheduling/scoring, then append result."""

        farm, location = await _load_owned_farm_and_location(
            farm_id=farm_id,
            owner_user_id=user.id,
            farm_repository=farm_repository,
            location_repository=location_repository,
        )
        _require_dated_history(farm)
        if farm.labour_capacity is None:
            raise HTTPException(
                status_code=409,
                detail="Add a labour capacity to this farm before requesting recommendations.",
            )

        try:
            config_record = await config_repository.get_active()
            if config_record is None:
                raise HTTPException(
                    status_code=503,
                    detail=ANALYSIS_CONFIGURATION_UNAVAILABLE_DETAIL,
                )
            crop_options = await crop_repository.list_crops(usage="recommendation")
            history_crops = await crop_repository.list_by_keys(
                {event.crop_key_snapshot for event in farm.crop_history} | _rice_variant_keys(farm)
            )
            crop_by_key = {crop.crop_key: crop for crop in (*crop_options, *history_crops)}
            calendar_documents = await crop_repository.list_calendars(
                location_key=location.location_key,
                crop_ids=tuple(crop.id for crop in crop_options if crop.id is not None),
            )
        except PyMongoError:
            raise HTTPException(status_code=503, detail=CATALOG_UNAVAILABLE_DETAIL) from None

        try:
            climate_status, analysis, cell = await _get_analysis_for_farm(
                farm=farm,
                location=location,
                climate_repository=climate_repository,
                environmental_config=config_repository.environmental_thresholds(config_record),
            )
        except PyMongoError:
            raise HTTPException(
                status_code=503,
                detail=ENVIRONMENTAL_SERVICE_UNAVAILABLE_DETAIL,
            ) from None
        crop_key_by_id = {crop.id: crop.crop_key for crop in crop_options if crop.id is not None}
        calendars = tuple(
            planting_calendar
            for calendar in calendar_documents
            if (
                planting_calendar := _planting_calendar(
                    calendar,
                    crop_key_by_id.get(calendar.crop_id, ""),
                )
            )
            is not None
        )
        rotation_crops = tuple(
            rotation_crop
            for crop in crop_options
            if (rotation_crop := _rotation_crop(crop, config_record)) is not None
        )
        latest_crop = _latest_history_crop(farm, crop_by_key, config_record)
        priority = (
            request_body.priority
            if request_body is not None and "priority" in request_body.model_fields_set
            else farm.farmer_priority
        )
        weather = _latest_weather(analysis)
        scoring_config = config_repository.scoring_configuration(config_record)
        generation = generate_ranked_rotations(
            crops=rotation_crops,
            calendars=calendars,
            location_key=location.location_key,
            available_from=farm.available_from or max(date.today(), farm.crop_history[-1].end_date),
            today=date.today(),
            labour_capacity=farm.labour_capacity,
            priority=priority,
            latest_crop=latest_crop,
            weather=weather,
            catalogue_version=_catalogue_version(crop_options),
            calendar_version=_calendar_version(calendar_documents),
            config=scoring_config,
        )
        try:
            current_farm = await farm_repository.get_by_owner(
                farm_id=farm_id,
                owner_user_id=user.id,
            )
        except PyMongoError:
            raise HTTPException(
                status_code=503,
                detail=ENVIRONMENTAL_SERVICE_UNAVAILABLE_DETAIL,
            ) from None
        if current_farm is None or current_farm.revision != farm.revision:
            raise HTTPException(
                status_code=409,
                detail=(
                    "The farm changed while this recommendation was being prepared. Please retry."
                ),
            )
        try:
            result = await result_repository.create_product_direction(
                owner_user_id=user.id,
                farm=farm,
                generation=generation,
                environmental_analysis=analysis,
                climate_cell_key=cell.cell_key if cell is not None else None,
                climate_data_through=cell.data_through if cell is not None else None,
            )
        except PyMongoError:
            raise HTTPException(
                status_code=503,
                detail=ROTATION_RESULT_UNAVAILABLE_DETAIL,
            ) from None

        environment = _status_response(
            farm=farm,
            location=location,
            cell=cell,
            analysis=analysis,
            override_status=climate_status,
        )
        return ProductDirectionRecommendationResponse(
            id=str(result.id),
            farm_id=str(farm.id),
            created_at=result.created_at,
            environmental_status=environment,
            environmental_analysis=analysis,
            recommendation=generation,
        )

    return router


async def _load_owned_farm_and_location(
    *,
    farm_id: PydanticObjectId,
    owner_user_id: PydanticObjectId,
    farm_repository: FarmRepository,
    location_repository: SupportedLocationRepository,
) -> tuple[Farm, SupportedLocation]:
    """Always apply owner constraint before resolving private farm data."""

    try:
        farm = await farm_repository.get_by_owner(farm_id=farm_id, owner_user_id=owner_user_id)
    except PyMongoError:
        raise HTTPException(
            status_code=503, detail=ENVIRONMENTAL_SERVICE_UNAVAILABLE_DETAIL
        ) from None
    if farm is None:
        raise HTTPException(status_code=404, detail=FARM_NOT_FOUND_DETAIL)
    try:
        location = await location_repository.get_by_key(farm.location_key)
    except PyMongoError:
        raise HTTPException(
            status_code=503, detail=ENVIRONMENTAL_SERVICE_UNAVAILABLE_DETAIL
        ) from None
    if location is None:
        raise HTTPException(status_code=503, detail="Farm location details are unavailable.")
    return farm, location


def _require_dated_history(farm: Farm) -> None:
    if not farm.crop_history or any(
        event.start_date is None or event.end_date is None for event in farm.crop_history
    ):
        raise HTTPException(status_code=409, detail=FARM_HISTORY_NEEDS_REVIEW_DETAIL)


async def _environment_status(
    *,
    farm: Farm,
    location: SupportedLocation,
    climate_repository: ClimateStoreRepository,
    environmental_config: EnvironmentalThresholdConfiguration,
) -> FarmEnvironmentalStatusResponse:
    _status, analysis, cell = await _get_analysis_for_farm(
        farm=farm,
        location=location,
        climate_repository=climate_repository,
        environmental_config=environmental_config,
    )
    return _status_response(
        farm=farm,
        location=location,
        cell=cell,
        analysis=analysis,
        override_status=_status,
    )


async def _get_analysis_for_farm(
    *,
    farm: Farm,
    location: SupportedLocation,
    climate_repository: ClimateStoreRepository,
    environmental_config: EnvironmentalThresholdConfiguration,
) -> tuple[str, EnvironmentalAnalysis, ClimateCell | None]:
    cell_key = location.nasa_cell_key or farm.nasa_cell_key
    if not cell_key:
        return (
            "location_unmapped",
            analyze_farm_history(
                events=(),
                daily_records=(),
                data_through=None,
                cell_status="pending",
                config=environmental_config,
            ),
            None,
        )
    cell = await climate_repository.get_cell(cell_key)
    if cell is None:
        return (
            "pending",
            analyze_farm_history(
                events=(),
                daily_records=(),
                data_through=None,
                cell_status="pending",
                config=environmental_config,
            ),
            None,
        )
    status = cell.load_status
    if status in {"pending", "loading", "error"} or cell.data_through is None:
        analysis_status = "error" if status == "error" else "pending"
        analysis = analyze_farm_history(
            events=(),
            daily_records=(),
            data_through=cell.data_through,
            cell_status=analysis_status,
            config=environmental_config,
        )
        return status, analysis, cell

    events = tuple(
        CropEventWindow(
            crop_key=event.crop_key_snapshot,
            sequence_order=event.sequence_order,
            planting_date=event.start_date,
            harvest_date=event.end_date,
        )
        for event in farm.crop_history
        if event.start_date is not None and event.end_date is not None
    )
    records = await climate_repository.get_daily_records(
        cell_key=cell_key,
        start_date=date(1981, 1, 1),
        end_date=max(date(2020, 12, 31), cell.data_through),
    )
    analysis = analyze_farm_history(
        events=events,
        daily_records=[
            DailyClimateRecord(
                day=record.day,
                rain_mm=record.rain_mm,
                t2m_c=record.t2m_c,
                t2m_max_c=record.t2m_max_c,
            )
            for record in records
        ],
        data_through=cell.data_through,
        cell_status="partial" if status == "partial" else "ready",
        config=environmental_config,
    )
    return status, analysis, cell


def _status_response(
    *,
    farm: Farm,
    location: SupportedLocation,
    cell: ClimateCell | None,
    analysis: EnvironmentalAnalysis,
    override_status: str,
) -> FarmEnvironmentalStatusResponse:
    status_value = override_status
    if override_status in {"ready", "partial"} and analysis.status == "partial":
        status_value = "partial"
    message_by_status = {
        "location_unmapped": "This supported place has not yet been mapped to a NASA grid cell.",
        "pending": "Historical climate data is queued and has not finished loading.",
        "loading": "Historical climate data is loading in the background.",
        "ready": None,
        "partial": "Some daily source values are missing; each finding reports its coverage.",
        "error": "The climate load stopped and can be resumed by an operator.",
        "unavailable": "No stored climate context is available for this place.",
    }
    return FarmEnvironmentalStatusResponse(
        farm_id=str(farm.id),
        location=FarmLocationSummary(location_key=farm.location_key, label=location.label),
        status=status_value,
        cell_key=cell.cell_key if cell else None,
        spatial_resolution=cell.spatial_resolution if cell else location.nasa_spatial_resolution,
        first_date=cell.first_date if cell and cell.data_through is not None else None,
        data_through=cell.data_through if cell else None,
        completed_chunk_count=len(cell.completed_chunks) if cell else 0,
        failed_chunk_count=len(cell.failed_chunks) if cell else 0,
        safe_message=(
            cell.safe_error.message
            if cell and cell.safe_error
            else message_by_status.get(status_value)
        ),
        analysis=analysis,
    )


def _latest_weather(analysis: EnvironmentalAnalysis) -> CropHistoryWeather:
    latest = analysis.crop_windows[-1] if analysis.crop_windows else None
    if latest is None:
        context = "pending" if analysis.status == "pending" else "unavailable"
        if analysis.status == "error":
            context = "unavailable"
        return CropHistoryWeather(context_status=context)
    context = "ready" if latest.status == "ready" else "partial"
    return CropHistoryWeather(
        rainfall_status=latest.rainfall_category,
        temperature_status=latest.temperature_category,
        dry_spell_status=(
            "Longer than usual" if latest.dry_spell_category == "Longer than usual" else None
        ),
        context_status=context,
    )


def _rotation_crop(crop: Crop, config: AnalysisConfig) -> RotationCrop | None:
    required = (
        crop.group,
        crop.water_resilience,
        crop.soil_effect,
        crop.maturity_days_min,
        crop.maturity_days_max,
        crop.labour,
    )
    if not crop.recommendation_candidate or any(value is None for value in required):
        return None
    growth = derive_growth_speed(
        crop.maturity_days_min,
        crop.maturity_days_max,
        fast_growth_max_days=config.fast_growth_max_days,
        medium_growth_max_days=config.medium_growth_max_days,
    )
    parameter_evidence = crop.parameter_evidence or {}
    evidence = [detail for detail in parameter_evidence.values()]
    references = tuple(dict.fromkeys(url for entry in evidence for url in entry.source_urls))
    assumptions = tuple(
        f"{crop.common_name}: {entry.applicability} Limitations: {entry.limitations}"
        for entry in evidence
    )
    return RotationCrop(
        crop_key=crop.crop_key,
        name=crop.common_name,
        group=crop.group,
        water_resilience=crop.water_resilience,
        soil_effect=crop.soil_effect,
        growth_speed=growth,
        labour=crop.labour,
        maturity_days_min=crop.maturity_days_min,
        maturity_days_max=crop.maturity_days_max,
        recommendation_candidate=crop.recommendation_candidate,
        production_system=crop.production_system,
        source_references=references,
        assumptions=assumptions,
    )


def _planting_calendar(calendar: CropCalendar, crop_key: str) -> PlantingCalendar | None:
    window = calendar.planting_window
    if window is None or not calendar.is_active:
        return None
    start_month, start_day = (int(part) for part in window.start_month_day.split("-"))
    end_month, end_day = (int(part) for part in window.end_month_day.split("-"))
    return PlantingCalendar(
        location_key=calendar.location_key,
        crop_key=crop_key,
        season_key=calendar.season_key,
        start_month=start_month,
        start_day=start_day,
        end_month=end_month,
        end_day=end_day,
        source=(
            calendar.evidence.source_title
            if calendar.evidence
            else calendar.source_note or "Unspecified"
        ),
        version=calendar.calendar_version,
        status=("locally_reviewed" if calendar.status == "locally_reviewed" else "provisional"),
    )


def _latest_history_crop(
    farm: Farm,
    crop_by_key: dict[str, Crop],
    config: AnalysisConfig,
) -> RotationCrop | None:
    if not farm.crop_history:
        return None
    event = farm.crop_history[-1]
    key = event.crop_key_snapshot
    if key == "rice":
        system = event.production_system_key
        if system not in {"upland", "rain-fed-lowland", "irrigated"}:
            return None
        key = f"rice-{system}"
    crop = crop_by_key.get(key)
    return _rotation_crop(crop, config) if crop is not None else None


def _rice_variant_keys(farm: Farm) -> set[str]:
    return {
        f"rice-{event.production_system_key}"
        for event in farm.crop_history
        if event.crop_key_snapshot == "rice"
        and event.production_system_key in {"upland", "rain-fed-lowland", "irrigated"}
    }


def _catalogue_version(crops: list[Crop]) -> str:
    return ",".join(sorted({crop.catalog_version for crop in crops})) or "empty"


def _calendar_version(calendars: list[CropCalendar]) -> str:
    return ",".join(sorted({calendar.calendar_version for calendar in calendars})) or "empty"
