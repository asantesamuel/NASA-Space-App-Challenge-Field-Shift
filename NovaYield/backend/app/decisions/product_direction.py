"""Pure scheduling and scoring rules for the November 2026 product direction.

This module deliberately accepts already-loaded crop, calendar, farm, and
weather values. It has no MongoDB, HTTP, clock, or filesystem dependency, so a
result can be reproduced from its persisted input/configuration versions.
"""

from __future__ import annotations

from datetime import date, timedelta
from fractions import Fraction
from itertools import product
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ENGINE_VERSION = "product-direction-engine-v1"
SCHEDULER_VERSION = "location-calendar-scheduler-v1"

CropGroup = Literal["Cereal", "Legume", "Root/tuber"]
WaterResilience = Literal["High", "Medium", "Low"]
SoilEffect = Literal["Adds nitrogen", "Neutral", "Draws down"]
GrowthSpeed = Literal["Fast", "Medium", "Slow"]
LabourDemand = Literal["Low", "Medium", "High"]
FarmerPriority = Literal["water_security", "soil_health", "fast_turnover", "low_labour"]
WeatherState = Literal["Drier", "Normal", "Wetter", "Hotter", "Cooler", "Longer than usual"]

WATER_SCORE = {"High": 3, "Medium": 2, "Low": 1}
SOIL_SCORE = {"Adds nitrogen": 3, "Neutral": 2, "Draws down": 1}
GROWTH_SCORE = {"Fast": 3, "Medium": 2, "Slow": 1}
LABOUR_SCORE = {"Low": 3, "Medium": 2, "High": 1}


class RotationCrop(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    crop_key: str
    name: str
    group: CropGroup
    water_resilience: WaterResilience
    soil_effect: SoilEffect
    growth_speed: GrowthSpeed
    labour: LabourDemand
    maturity_days_min: int = Field(gt=0)
    maturity_days_max: int = Field(gt=0)
    recommendation_candidate: bool = True
    production_system: str | None = None
    source_references: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()


class CalendarEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_url: str | None = None
    window_basis: Literal["zone_guidance", "local_trial_analogue"] | None = None
    applicability: str
    limitations: str


class PlantingCalendar(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    location_key: str
    crop_key: str
    season_key: str
    start_month: int = Field(ge=1, le=12)
    start_day: int = Field(ge=1, le=31)
    end_month: int = Field(ge=1, le=12)
    end_day: int = Field(ge=1, le=31)
    source: str
    version: str
    status: Literal["provisional", "locally_reviewed"] = "provisional"
    evidence: CalendarEvidence | None = None


class CropHistoryWeather(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rainfall_status: WeatherState | None = None
    temperature_status: WeatherState | None = None
    dry_spell_status: WeatherState | None = None
    context_status: Literal["ready", "partial", "unavailable", "pending"]

    @property
    def adverse(self) -> bool:
        return any(
            value in {"Drier", "Hotter", "Longer than usual"}
            for value in (
                self.rainfall_status,
                self.temperature_status,
                self.dry_spell_status,
            )
        )

    @property
    def decisive(self) -> bool:
        return self.context_status == "ready" or self.adverse


class ScheduledEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    order: int
    crop_key: str
    crop_name: str
    planting_date: date
    harvest_earliest: date
    harvest_latest: date
    season_key: str
    calendar_source: str
    calendar_version: str
    calendar_status: str
    calendar_evidence: CalendarEvidence | None = None


class RotationStepScore(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    order: int
    crop_key: str
    ratings: dict[str, int]
    weights: dict[str, int]
    weighted_score: float
    weather_adjustment: Literal["applied", "not_triggered"] | None
    rationale: tuple[str, ...]


class RotationOption(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rank: int
    crops: tuple[str, str, str]
    score: float
    diversity_transitions: int
    events: tuple[ScheduledEvent, ScheduledEvent, ScheduledEvent]
    step_scores: tuple[RotationStepScore, RotationStepScore, RotationStepScore]
    benefits: tuple[str, ...]
    trade_offs: tuple[str, ...]
    assumptions: tuple[str, ...]
    evidence: tuple[str, ...] = ()


class RotationGeneration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["ranked", "no_options"]
    engine_version: str = ENGINE_VERSION
    scheduler_version: str = SCHEDULER_VERSION
    catalogue_version: str
    calendar_version: str
    configuration_version: str
    weather_context_status: str
    weather_weight_adjustment: Literal["applied", "not_triggered"] | None
    selected_priority: FarmerPriority | None
    criteria: tuple[str, str, str, str] = (
        "water_resilience",
        "soil_health",
        "growth_speed",
        "labour",
    )
    options: tuple[RotationOption, ...] = ()
    exclusion_counts: dict[str, int] = Field(default_factory=dict)
    reason: str | None = None


class ScoringConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = "analysis-config-v1"
    fast_growth_max_days: int = Field(default=75, ge=1)
    medium_growth_max_days: int = Field(default=150, ge=75)
    turnaround_days: int = Field(default=14, ge=0)
    horizon_months: int = Field(default=24, ge=1)
    base_weight: int = Field(default=1, ge=1)
    adverse_weather_water_weight: int = Field(default=2, ge=1)
    preceding_cereal_soil_weight: int = Field(default=2, ge=1)
    priority_adjustment: int = Field(default=1, ge=0)


def derive_growth_speed(
    minimum_days: int,
    maximum_days: int,
    *,
    fast_growth_max_days: int = 75,
    medium_growth_max_days: int = 150,
) -> GrowthSpeed:
    """Classify the midpoint of a source-reported maturity range using config cutoffs."""

    midpoint = (minimum_days + maximum_days) / 2
    if midpoint < fast_growth_max_days:
        return "Fast"
    if midpoint <= medium_growth_max_days:
        return "Medium"
    return "Slow"


def _calendar_start(year: int, month: int, day: int) -> date:
    # A Feb 29 calendar is meaningful only in leap years. No synthetic date is made.
    if month == 2 and day == 29:
        return date(year, 2, 29)
    return date(year, month, day)


def _window_for_year(calendar: PlantingCalendar, year: int) -> tuple[date, date] | None:
    try:
        start = _calendar_start(year, calendar.start_month, calendar.start_day)
        end_year = year + (
            (calendar.end_month, calendar.end_day) < (calendar.start_month, calendar.start_day)
        )
        end = _calendar_start(end_year, calendar.end_month, calendar.end_day)
    except ValueError:
        return None
    return start, end


def _next_window(
    *,
    location_key: str,
    crop: RotationCrop,
    calendars: tuple[PlantingCalendar, ...],
    earliest: date,
    horizon_end: date,
) -> tuple[date, PlantingCalendar] | None:
    choices: list[tuple[date, PlantingCalendar]] = []
    for calendar in calendars:
        if calendar.location_key != location_key or calendar.crop_key != crop.crop_key:
            continue
        for year in range(earliest.year - 1, horizon_end.year + 1):
            bounds = _window_for_year(calendar, year)
            if bounds is None:
                continue
            window_start, window_end = bounds
            plant_on = max(earliest, window_start)
            if plant_on <= min(window_end, horizon_end):
                choices.append((plant_on, calendar))
    return min(choices, key=lambda item: (item[0], item[1].season_key)) if choices else None


def schedule_rotation(
    *,
    crop_keys: tuple[str, str, str],
    crops_by_key: dict[str, RotationCrop],
    calendars: tuple[PlantingCalendar, ...],
    location_key: str,
    available_from: date,
    today: date,
    horizon_months: int = 24,
    turnaround_days: int = 14,
) -> tuple[ScheduledEvent, ScheduledEvent, ScheduledEvent] | None:
    """Greedily place each event in its next location-scoped calendar window."""

    start_date = max(today, available_from)
    try:
        horizon_end = start_date.replace(
            month=((start_date.month - 1 + horizon_months) % 12) + 1,
            year=start_date.year + (start_date.month - 1 + horizon_months) // 12,
        )
    except ValueError:
        # Day 29-31 can overflow when the horizon target month is shorter.
        month_index = start_date.month - 1 + horizon_months
        target_year, target_month = start_date.year + month_index // 12, month_index % 12 + 1
        last_day = (
            date(target_year + (target_month == 12), (target_month % 12) + 1, 1) - timedelta(days=1)
        ).day
        horizon_end = date(target_year, target_month, min(start_date.day, last_day))

    events: list[ScheduledEvent] = []
    earliest = start_date
    for order, key in enumerate(crop_keys, start=1):
        crop = crops_by_key[key]
        selected = _next_window(
            location_key=location_key,
            crop=crop,
            calendars=calendars,
            earliest=earliest,
            horizon_end=horizon_end,
        )
        if selected is None:
            return None
        planting, calendar = selected
        harvest_earliest = planting + timedelta(days=crop.maturity_days_min)
        harvest_latest = planting + timedelta(days=crop.maturity_days_max)
        events.append(
            ScheduledEvent(
                order=order,
                crop_key=key,
                crop_name=crop.name,
                planting_date=planting,
                harvest_earliest=harvest_earliest,
                harvest_latest=harvest_latest,
                season_key=calendar.season_key,
                calendar_source=calendar.source,
                calendar_version=calendar.version,
                calendar_status=calendar.status,
                calendar_evidence=calendar.evidence,
            )
        )
        earliest = harvest_latest + timedelta(days=turnaround_days)
    return tuple(events)  # type: ignore[return-value]


def _priority_criterion(priority: FarmerPriority | None) -> str | None:
    return {
        "water_security": "water_resilience",
        "soil_health": "soil_health",
        "fast_turnover": "growth_speed",
        "low_labour": "labour",
    }.get(priority)


def _ratings(crop: RotationCrop) -> dict[str, int]:
    return {
        "water_resilience": WATER_SCORE[crop.water_resilience],
        "soil_health": SOIL_SCORE[crop.soil_effect],
        "growth_speed": GROWTH_SCORE[crop.growth_speed],
        "labour": LABOUR_SCORE[crop.labour],
    }


def _step_score(
    *,
    order: int,
    crop: RotationCrop,
    preceding: RotationCrop | None,
    weather: CropHistoryWeather,
    priority: FarmerPriority | None,
    config: ScoringConfiguration,
) -> RotationStepScore:
    weights = {
        criterion: config.base_weight
        for criterion in ("water_resilience", "soil_health", "growth_speed", "labour")
    }
    weather_adjustment: Literal["applied", "not_triggered"] | None = None
    rationale: list[str] = []
    if order == 1:
        if weather.adverse:
            weights["water_resilience"] = config.adverse_weather_water_weight
            weather_adjustment = "applied"
            rationale.append(
                "Recent historical crop weather contains an adverse finding; water resilience "
                "receives the configured step-one weight adjustment."
            )
        elif weather.context_status == "ready":
            weather_adjustment = "not_triggered"
            rationale.append(
                "Available recent weather did not trigger a step-one water adjustment."
            )
        else:
            rationale.append(
                "Weather is unavailable or partial; no weather bonus is assumed and the base "
                "water weight is retained."
            )
    if preceding is not None and (
        preceding.group == "Cereal" or preceding.soil_effect == "Draws down"
    ):
        weights["soil_health"] = config.preceding_cereal_soil_weight
        rationale.append(
            f"The preceding crop ({preceding.name}) is a cereal or has a drawdown soil profile; "
            "the configured soil weight applies."
        )
    priority_criterion = _priority_criterion(priority)
    if priority_criterion:
        weights[priority_criterion] += config.priority_adjustment
        rationale.append(
            f"Farmer priority increases the {priority_criterion.replace('_', ' ')} weight."
        )
    ratings = _ratings(crop)
    total_weight = sum(weights.values())
    score = Fraction(sum(ratings[key] * weights[key] for key in weights), total_weight)
    rationale.append(
        "The displayed score is a deterministic weighted average of relative 1–3 trait ratings; "
        "it is not a probability or yield prediction."
    )
    return RotationStepScore(
        order=order,
        crop_key=crop.crop_key,
        ratings=ratings,
        weights=weights,
        weighted_score=float(score),
        weather_adjustment=weather_adjustment,
        rationale=tuple(rationale),
    )


def generate_ranked_rotations(
    *,
    crops: tuple[RotationCrop, ...],
    calendars: tuple[PlantingCalendar, ...],
    location_key: str,
    available_from: date,
    today: date,
    labour_capacity: LabourDemand,
    priority: FarmerPriority | None,
    latest_crop: RotationCrop | None,
    weather: CropHistoryWeather,
    catalogue_version: str,
    calendar_version: str,
    config: ScoringConfiguration,
    maximum_options: int = 3,
) -> RotationGeneration:
    """Generate, filter, schedule, score and explain at most three sequences."""

    maximum_options = max(0, min(maximum_options, 3))

    capacity = {"Low": 1, "Medium": 2, "High": 3}[labour_capacity]
    rice_supported = {"upland", "rain-fed-lowland", "irrigated"}
    unsupported_rice = sum(
        crop.recommendation_candidate
        and crop.crop_key.startswith("rice")
        and crop.production_system not in rice_supported
        for crop in crops
    )
    allowed = tuple(
        crop
        for crop in crops
        if crop.recommendation_candidate
        and {"Low": 1, "Medium": 2, "High": 3}[crop.labour] <= capacity
        and not (crop.crop_key.startswith("rice") and crop.production_system not in rice_supported)
    )
    exclusions = {
        "candidate_disabled": sum(not crop.recommendation_candidate for crop in crops),
        "labour_capacity": sum(
            crop.recommendation_candidate
            and {"Low": 1, "Medium": 2, "High": 3}[crop.labour] > capacity
            for crop in crops
        ),
        "unsupported_rice_system": unsupported_rice,
        "calendar_or_horizon": 0,
    }
    crops_by_key = {crop.crop_key: crop for crop in allowed}
    generated: list[
        tuple[
            Fraction,
            int,
            int,
            tuple[str, str, str],
            tuple[ScheduledEvent, ...],
            tuple[RotationStepScore, ...],
            int,
        ]
    ] = []
    seen: set[tuple[str, str, str]] = set()
    for sequence in product(sorted(allowed, key=lambda item: item.crop_key), repeat=3):
        keys = tuple(crop.crop_key for crop in sequence)
        if keys in seen:
            continue
        seen.add(keys)
        schedule = schedule_rotation(
            crop_keys=keys,
            crops_by_key=crops_by_key,
            calendars=calendars,
            location_key=location_key,
            available_from=available_from,
            today=today,
            horizon_months=config.horizon_months,
            turnaround_days=config.turnaround_days,
        )
        if schedule is None:
            exclusions["calendar_or_horizon"] += 1
            continue
        steps: list[RotationStepScore] = []
        preceding = latest_crop
        for order, crop in enumerate(sequence, start=1):
            steps.append(
                _step_score(
                    order=order,
                    crop=crop,
                    preceding=preceding,
                    weather=weather,
                    priority=priority,
                    config=config,
                )
            )
            preceding = crop
        score = sum((Fraction(str(step.weighted_score)) for step in steps), Fraction(0, 1)) / len(
            steps
        )
        diversity = sum(sequence[index].group != sequence[index - 1].group for index in (1, 2))
        priority_criterion = _priority_criterion(priority)
        priority_sum = (
            sum(step.ratings[priority_criterion] for step in steps) if priority_criterion else 0
        )
        horizon = (schedule[-1].harvest_latest - schedule[0].planting_date).days
        generated.append((score, diversity, priority_sum, keys, schedule, tuple(steps), horizon))

    generated.sort(key=lambda row: (-row[0], -row[1], -row[2], row[6], row[3]))
    options: list[RotationOption] = []
    for rank, row in enumerate(generated[:maximum_options], start=1):
        score, diversity, _priority_sum, keys, schedule, steps, _horizon = row
        avg_ratings = {
            criterion: sum(step.ratings[criterion] for step in steps) / len(steps)
            for criterion in ("water_resilience", "soil_health", "growth_speed", "labour")
        }
        benefits = tuple(
            f"Relative strength in {criterion.replace('_', ' ')} across the sequence."
            for criterion, value in avg_ratings.items()
            if value >= 2.5
        )
        weakest = min(avg_ratings, key=avg_ratings.get)
        trade_offs = (
            f"The sequence's weakest relative criterion is {weakest.replace('_', ' ')}; a higher "
            "priority on another criterion can change the ordering, not remove the trade-off.",
        )
        if diversity < 2:
            trade_offs += (
                "Adjacent crops do not span all three broad crop groups; diversity is a soft "
                "tie preference and did not exclude this sequence.",
            )
        assumptions = tuple(
            dict.fromkeys(
                assumption
                for crop in (crops_by_key[key] for key in keys)
                for assumption in crop.assumptions
            )
        )
        evidence = tuple(
            dict.fromkeys(
                reference
                for crop in (crops_by_key[key] for key in keys)
                for reference in crop.source_references
            )
        )
        if any(event.calendar_status != "locally_reviewed" for event in schedule):
            assumptions += ("One or more planting windows are provisional desk-research evidence.",)
        options.append(
            RotationOption(
                rank=rank,
                crops=keys,
                score=float(score),
                diversity_transitions=diversity,
                events=schedule,
                step_scores=steps,
                benefits=benefits,
                trade_offs=trade_offs,
                assumptions=assumptions,
                evidence=evidence,
            )
        )
    return RotationGeneration(
        status="ranked" if options else "no_options",
        catalogue_version=catalogue_version,
        calendar_version=calendar_version,
        configuration_version=config.version,
        weather_context_status=weather.context_status,
        weather_weight_adjustment=(
            "applied"
            if weather.adverse
            else "not_triggered"
            if weather.context_status == "ready"
            else None
        ),
        selected_priority=priority,
        options=tuple(options),
        exclusion_counts=exclusions,
        reason=None
        if options
        else (
            "No three-crop sequence satisfies the enabled crop, labour, and location-calendar "
            "constraints within the configured horizon."
        ),
    )
