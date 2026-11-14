"""Pure historical climate analysis for actual farmer-reported crop windows.

The caller supplies rows already read from the local climate store. Values are
never filled, converted to zero, or fetched from NASA here. All findings are
regional grid-cell weather context, not a field sensor, soil-moisture reading,
forecast, or crop-damage estimate.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import date, timedelta
from math import ceil, isfinite
from statistics import mean, median
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

REFERENCE_START_YEAR = 1991
REFERENCE_END_YEAR = 2020
DRY_DAY_THRESHOLD_MM = 1.0
RAINFALL_DRY_RATIO = 0.85
RAINFALL_WET_RATIO = 1.15
TEMPERATURE_DELTA_C = 1.0
DRY_SPELL_PERCENTILE = 75
ENVIRONMENTAL_METHOD_VERSION = "matched-daily-climate-v1"

ClimateStatus = Literal["ready", "partial", "unavailable", "pending", "error"]
RainfallCategory = Literal["Drier", "Normal", "Wetter"]
TemperatureCategory = Literal["Cooler", "Normal", "Hotter"]
DrySpellCategory = Literal["Shorter than usual", "Not longer than usual", "Longer than usual"]


class DailyClimateRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    day: date
    rain_mm: float | None = None
    t2m_c: float | None = None
    t2m_max_c: float | None = None


class CropEventWindow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    crop_key: str
    sequence_order: int = Field(ge=1, le=3)
    planting_date: date
    harvest_date: date


class MetricCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    expected_days: int
    valid_days: int
    missing_days: int
    leap_days_excluded: int = 0
    matching_reference_years: int = 0
    comparison_valid_days: int = 0
    reference_missing_days: int = 0


class EnvironmentalThresholdConfiguration(BaseModel):
    """Versioned interpretation thresholds; defaults are MVP policy, not validated constants."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = "analysis-config-v1"
    reference_start_year: int = REFERENCE_START_YEAR
    reference_end_year: int = REFERENCE_END_YEAR
    dry_day_threshold_mm: float = DRY_DAY_THRESHOLD_MM
    rainfall_drier_ratio: float = RAINFALL_DRY_RATIO
    rainfall_wetter_ratio: float = RAINFALL_WET_RATIO
    temperature_delta_c: float = TEMPERATURE_DELTA_C
    dry_spell_percentile: int = DRY_SPELL_PERCENTILE


DEFAULT_ENVIRONMENTAL_CONFIGURATION = EnvironmentalThresholdConfiguration()


class HistoricalWindowFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    window_type: Literal["crop_event", "since_harvest"]
    crop_key: str | None = None
    start_date: date
    end_date: date
    status: ClimateStatus
    rainfall_total_mm: float | None
    rainfall_comparison_total_mm: float | None = None
    rainfall_reference_median_mm: float | None
    rainfall_ratio: float | None
    rainfall_category: RainfallCategory | None
    rainfall_coverage: MetricCoverage
    mean_t2m_max_c: float | None = None
    comparison_mean_t2m_max_c: float | None = None
    reference_mean_t2m_max_c: float | None = None
    temperature_delta_c: float | None = None
    temperature_category: TemperatureCategory | None = None
    temperature_coverage: MetricCoverage | None = None
    longest_dry_spell_days: int | None = None
    longest_dry_spell_text: str | None = None
    reference_dry_spell_p75_days: int | None = None
    dry_spell_category: DrySpellCategory | None = None
    dry_spell_coverage: MetricCoverage | None = None
    missing_parameters: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    source: str = "NASA POWER Daily API"
    data_through: date | None = None
    method_version: str = ENVIRONMENTAL_METHOD_VERSION
    interpretation: str = (
        "Historical weather represented by a NASA POWER regional grid cell; this is not a "
        "farm sensor, forecast, soil-moisture value, or crop-damage estimate."
    )


class EnvironmentalAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: ClimateStatus
    reference_period_start: int = REFERENCE_START_YEAR
    reference_period_end: int = REFERENCE_END_YEAR
    data_through: date | None
    source: str = "NASA POWER Daily API"
    crop_windows: tuple[HistoricalWindowFinding, ...] = ()
    since_harvest: HistoricalWindowFinding | None = None
    weather_weight_adjustment: Literal["applied", "not_triggered"] | None = None
    weather_adjustment_reason: str | None = None
    missing_parameters: tuple[str, ...] = ()
    method_version: str = ENVIRONMENTAL_METHOD_VERSION


def _daily_map(records: Sequence[DailyClimateRecord]) -> dict[date, DailyClimateRecord]:
    return {record.day: record for record in records}


def _window_dates(start: date, end: date) -> list[date]:
    current = start
    result: list[date] = []
    while current <= end:
        result.append(current)
        current += timedelta(days=1)
    return result


def _same_month_day_dates(days: Sequence[date], year: int) -> list[date | None]:
    """Map matching month/day positions, dropping Feb 29 consistently."""

    mapped: list[date | None] = []
    for observed in days:
        if observed.month == 2 and observed.day == 29:
            mapped.append(None)
            continue
        try:
            mapped.append(date(year, observed.month, observed.day))
        except ValueError:
            # February 29 is the only valid month/day impossible in a non-leap year.
            mapped.append(None)
    return mapped


def _valid_nonnegative(value: float | None) -> bool:
    return value is not None and isfinite(value) and value >= 0


def _valid_temperature(value: float | None) -> bool:
    return value is not None and isfinite(value)


def _matching_reference_values(
    *,
    analyzed_dates: Sequence[date],
    actual_values: Sequence[float | None],
    daily: Mapping[date, DailyClimateRecord],
    year_attribute: str,
    is_valid: Callable[[float | None], bool],
    config: EnvironmentalThresholdConfiguration,
) -> tuple[list[int], list[dict[int, float]]]:
    """Find a common date mask shared by observed data and all reference years.

    Reference comparisons use identical calendar dates for the observed total/mean
    and every 1991–2020 year. A date missing in any required series is omitted
    from all 30 years, preventing unequal-coverage totals from being compared.
    """

    validator = is_valid
    values_by_year: list[dict[int, float]] = []
    for year in range(config.reference_start_year, config.reference_end_year + 1):
        mapped_dates = _same_month_day_dates(analyzed_dates, year)
        year_values: dict[int, float] = {}
        for index, reference_day in enumerate(mapped_dates):
            if reference_day is None:
                continue
            record = daily.get(reference_day)
            value = getattr(record, year_attribute) if record is not None else None
            if validator(value):
                year_values[index] = value
        values_by_year.append(year_values)

    common_indexes = [
        index
        for index, value in enumerate(actual_values)
        if validator(value) and all(index in year_values for year_values in values_by_year)
    ]
    return common_indexes, values_by_year


def _classify_rainfall(
    ratio: float | None,
    config: EnvironmentalThresholdConfiguration,
) -> RainfallCategory | None:
    if ratio is None:
        return None
    if ratio < config.rainfall_drier_ratio:
        return "Drier"
    if ratio > config.rainfall_wetter_ratio:
        return "Wetter"
    return "Normal"


def _classify_temperature(
    delta: float | None,
    config: EnvironmentalThresholdConfiguration,
) -> TemperatureCategory | None:
    if delta is None:
        return None
    if delta > config.temperature_delta_c:
        return "Hotter"
    if delta < -config.temperature_delta_c:
        return "Cooler"
    return "Normal"


def _longest_dry_run(
    values: Sequence[float | None],
    dry_day_threshold_mm: float,
) -> tuple[int, bool]:
    longest = current = 0
    missing_may_join_runs = False
    previous_was_dry = False
    missing_between_runs = False
    for value in values:
        if value is None or not isfinite(value) or value < 0:
            if current:
                previous_was_dry = True
            current = 0
            missing_between_runs = True
            continue
        if value < dry_day_threshold_mm:
            if missing_between_runs and previous_was_dry:
                missing_may_join_runs = True
            current += 1
            longest = max(longest, current)
            previous_was_dry = True
            missing_between_runs = False
        else:
            current = 0
            previous_was_dry = False
            missing_between_runs = False
    return longest, missing_may_join_runs


def _nearest_rank_percentile(values: Sequence[int], percentile: int) -> int | None:
    """Use the documented nearest-rank percentile definition for an integer metric."""

    if not values:
        return None
    ordered = sorted(values)
    index = max(0, ceil(percentile / 100 * len(ordered)) - 1)
    return ordered[index]


def _rainfall_context(
    *,
    window_dates: Sequence[date],
    daily: Mapping[date, DailyClimateRecord],
    config: EnvironmentalThresholdConfiguration,
) -> tuple[
    float | None,
    float | None,
    float | None,
    float | None,
    RainfallCategory | None,
    MetricCoverage,
    list[str],
]:
    actual_values: list[float | None] = []
    analyzed_dates: list[date] = []
    leap_days = 0
    for day in window_dates:
        if day.month == 2 and day.day == 29:
            leap_days += 1
            continue
        analyzed_dates.append(day)
        record = daily.get(day)
        value = record.rain_mm if record is not None else None
        actual_values.append(value if _valid_nonnegative(value) else None)
    valid_values = [value for value in actual_values if value is not None]
    notes: list[str] = []
    if any(
        record.rain_mm is not None and not _valid_nonnegative(record.rain_mm)
        for record in daily.values()
    ):
        notes.append("Invalid negative/non-finite rainfall values were treated as missing.")
    if leap_days:
        notes.append("29 February was excluded from the observed and matched reference windows.")
    total = sum(valid_values) if valid_values else None
    comparable_indexes, values_by_year = _matching_reference_values(
        analyzed_dates=analyzed_dates,
        actual_values=actual_values,
        daily=daily,
        year_attribute="rain_mm",
        is_valid=_valid_nonnegative,
        config=config,
    )
    comparable_observed_total = (
        sum(actual_values[index] for index in comparable_indexes) if comparable_indexes else None
    )
    reference_totals = [
        sum(year_values[index] for index in comparable_indexes)
        for year_values in values_by_year
        if comparable_indexes
    ]
    reference_median = median(reference_totals) if reference_totals else None
    ratio = None
    category = None
    if comparable_observed_total is not None and reference_median is not None:
        if reference_median > 0:
            ratio = comparable_observed_total / reference_median
            category = _classify_rainfall(ratio, config)
        else:
            notes.append(
                "Rainfall comparison unavailable because the matching 1991–2020 median is zero; "
                "no ratio or category was invented."
            )
    reference_missing_days = max(
        0,
        sum(value is not None for value in actual_values) - len(comparable_indexes),
    )
    if reference_missing_days:
        notes.append(
            f"{reference_missing_days} observed-valid calendar day(s) were omitted from all "
            "reference years because at least one matched reference value was missing."
        )
    coverage = MetricCoverage(
        expected_days=len(analyzed_dates),
        valid_days=len(valid_values),
        missing_days=len(analyzed_dates) - len(valid_values),
        leap_days_excluded=leap_days,
        matching_reference_years=len(reference_totals),
        comparison_valid_days=len(comparable_indexes),
        reference_missing_days=reference_missing_days,
    )
    return total, comparable_observed_total, reference_median, ratio, category, coverage, notes


def _temperature_context(
    *,
    window_dates: Sequence[date],
    daily: Mapping[date, DailyClimateRecord],
    config: EnvironmentalThresholdConfiguration,
) -> tuple[
    float | None,
    float | None,
    float | None,
    float | None,
    TemperatureCategory | None,
    MetricCoverage,
    list[str],
]:
    analyzed_dates = [day for day in window_dates if not (day.month == 2 and day.day == 29)]
    actual_values = [
        daily[day].t2m_max_c if daily.get(day) is not None else None for day in analyzed_dates
    ]
    valid_values = [value for value in actual_values if _valid_temperature(value)]
    observed_mean = mean(valid_values) if valid_values else None
    comparable_indexes, values_by_year = _matching_reference_values(
        analyzed_dates=analyzed_dates,
        actual_values=actual_values,
        daily=daily,
        year_attribute="t2m_max_c",
        is_valid=_valid_temperature,
        config=config,
    )
    reference_year_means = [
        mean(year_values[index] for index in comparable_indexes)
        for year_values in values_by_year
        if comparable_indexes
    ]
    reference_mean = mean(reference_year_means) if reference_year_means else None
    matched_observed_mean = (
        mean(actual_values[index] for index in comparable_indexes) if comparable_indexes else None
    )
    delta = (
        matched_observed_mean - reference_mean
        if matched_observed_mean is not None and reference_mean is not None
        else None
    )
    reference_missing_days = max(
        0,
        sum(value is not None for value in actual_values) - len(comparable_indexes),
    )
    coverage = MetricCoverage(
        expected_days=len(analyzed_dates),
        valid_days=len(valid_values),
        missing_days=len(analyzed_dates) - len(valid_values),
        leap_days_excluded=len(window_dates) - len(analyzed_dates),
        matching_reference_years=len(reference_year_means),
        comparison_valid_days=len(comparable_indexes),
        reference_missing_days=reference_missing_days,
    )
    notes = []
    if coverage.missing_days:
        notes.append("Missing maximum-temperature days were not imputed.")
    if coverage.leap_days_excluded:
        notes.append("29 February was excluded from the observed and matched reference windows.")
    if reference_missing_days:
        notes.append(
            f"{reference_missing_days} observed-valid calendar day(s) were omitted from all "
            "reference years because at least one matched reference value was missing."
        )
    return (
        observed_mean,
        matched_observed_mean,
        reference_mean,
        delta,
        _classify_temperature(delta, config),
        coverage,
        notes,
    )


def _dry_spell_context(
    *,
    window_dates: Sequence[date],
    daily: Mapping[date, DailyClimateRecord],
    config: EnvironmentalThresholdConfiguration,
) -> tuple[int | None, str | None, int | None, DrySpellCategory | None, MetricCoverage, list[str]]:
    analyzed_dates = [day for day in window_dates if not (day.month == 2 and day.day == 29)]
    actual_values = [
        daily[day].rain_mm if daily.get(day) is not None else None for day in analyzed_dates
    ]
    actual_values = [value if _valid_nonnegative(value) else None for value in actual_values]
    valid = [value for value in actual_values if value is not None]
    longest, may_join = _longest_dry_run(
        actual_values,
        dry_day_threshold_mm=config.dry_day_threshold_mm,
    )
    comparable_indexes, values_by_year = _matching_reference_values(
        analyzed_dates=analyzed_dates,
        actual_values=actual_values,
        daily=daily,
        year_attribute="rain_mm",
        is_valid=_valid_nonnegative,
        config=config,
    )
    reference_maxima: list[int] = []
    if comparable_indexes:
        common_set = set(comparable_indexes)
        for year_values in values_by_year:
            ref_values = [
                year_values.get(index) if index in common_set else None
                for index in range(len(analyzed_dates))
            ]
            maximum, _ = _longest_dry_run(
                ref_values,
                dry_day_threshold_mm=config.dry_day_threshold_mm,
            )
            reference_maxima.append(maximum)
    p75 = _nearest_rank_percentile(reference_maxima, config.dry_spell_percentile)
    category = None
    if valid and p75 is not None:
        category = "Longer than usual" if longest > p75 else "Not longer than usual"
    coverage = MetricCoverage(
        expected_days=len(analyzed_dates),
        valid_days=len(valid),
        missing_days=len(analyzed_dates) - len(valid),
        leap_days_excluded=len(window_dates) - len(analyzed_dates),
        matching_reference_years=len(reference_maxima),
        comparison_valid_days=len(comparable_indexes),
        reference_missing_days=max(
            0,
            sum(value is not None for value in actual_values) - len(comparable_indexes),
        ),
    )
    notes: list[str] = []
    if may_join:
        notes.append(
            "Missing days may join observed dry runs; the reported length is a lower bound."
        )
    if coverage.missing_days:
        notes.append("Missing rainfall is not assumed to be dry or wet.")
    if coverage.reference_missing_days:
        notes.append(
            f"{coverage.reference_missing_days} observed-valid calendar day(s) were omitted from "
            "all reference dry-spell comparisons because a matched reference value was missing."
        )
    text = f"at least {longest} days" if may_join else f"{longest} days"
    return (longest if valid else None), (text if valid else None), p75, category, coverage, notes


def analyze_crop_window(
    *,
    event: CropEventWindow,
    daily_records: Sequence[DailyClimateRecord],
    data_through: date | None,
    config: EnvironmentalThresholdConfiguration = DEFAULT_ENVIRONMENTAL_CONFIGURATION,
) -> HistoricalWindowFinding:
    """Calculate source-comparable rainfall, temperature, and dry-spell context."""

    dates = _window_dates(event.planting_date, event.harvest_date)
    daily = _daily_map(daily_records)
    (
        rain_total,
        rain_comparison_total,
        rain_ref,
        rain_ratio,
        rain_category,
        rain_coverage,
        rain_notes,
    ) = _rainfall_context(window_dates=dates, daily=daily, config=config)
    (
        temp_mean,
        temp_comparison_mean,
        temp_ref,
        temp_delta,
        temp_category,
        temp_cov,
        temp_notes,
    ) = _temperature_context(window_dates=dates, daily=daily, config=config)
    dry_days, dry_text, dry_ref, dry_category, dry_cov, dry_notes = _dry_spell_context(
        window_dates=dates,
        daily=daily,
        config=config,
    )
    missing_parameters = tuple(
        key
        for key, coverage in (
            ("PRECTOTCORR", rain_coverage),
            ("T2M_MAX", temp_cov),
            ("PRECTOTCORR dry spell", dry_cov),
        )
        if coverage.valid_days == 0
    )
    no_observed_metric = not rain_coverage.valid_days and not temp_cov.valid_days
    incomplete_comparison = any(
        coverage.missing_days
        or coverage.reference_missing_days
        or coverage.comparison_valid_days == 0
        for coverage in (rain_coverage, temp_cov, dry_cov)
    )
    missing_finding = any(value is None for value in (rain_category, temp_category, dry_category))
    status: ClimateStatus = (
        "unavailable"
        if no_observed_metric
        else "partial"
        if incomplete_comparison or missing_finding
        else "ready"
    )
    return HistoricalWindowFinding(
        window_type="crop_event",
        crop_key=event.crop_key,
        start_date=event.planting_date,
        end_date=event.harvest_date,
        status=status,
        rainfall_total_mm=rain_total,
        rainfall_comparison_total_mm=rain_comparison_total,
        rainfall_reference_median_mm=rain_ref,
        rainfall_ratio=rain_ratio,
        rainfall_category=rain_category,
        rainfall_coverage=rain_coverage,
        mean_t2m_max_c=temp_mean,
        comparison_mean_t2m_max_c=temp_comparison_mean,
        reference_mean_t2m_max_c=temp_ref,
        temperature_delta_c=temp_delta,
        temperature_category=temp_category,
        temperature_coverage=temp_cov,
        longest_dry_spell_days=dry_days,
        longest_dry_spell_text=dry_text,
        reference_dry_spell_p75_days=dry_ref,
        dry_spell_category=dry_category,
        dry_spell_coverage=dry_cov,
        missing_parameters=missing_parameters,
        notes=tuple(rain_notes + temp_notes + dry_notes),
        data_through=data_through,
    )


def analyze_since_harvest(
    *,
    harvest_date: date,
    data_through: date,
    daily_records: Sequence[DailyClimateRecord],
    config: EnvironmentalThresholdConfiguration = DEFAULT_ENVIRONMENTAL_CONFIGURATION,
) -> HistoricalWindowFinding:
    """Return rainfall context after harvest, explicitly as weather rather than soil moisture."""

    start = harvest_date + timedelta(days=1)
    if data_through < start:
        return HistoricalWindowFinding(
            window_type="since_harvest",
            start_date=start,
            end_date=data_through,
            status="unavailable",
            rainfall_total_mm=None,
            rainfall_comparison_total_mm=None,
            rainfall_reference_median_mm=None,
            rainfall_ratio=None,
            rainfall_category=None,
            rainfall_coverage=MetricCoverage(expected_days=0, valid_days=0, missing_days=0),
            missing_parameters=("PRECTOTCORR",),
            notes=(
                "No stored daily weather covers a day after the last harvest.",
                "This is a weather note and does not measure soil moisture.",
            ),
            data_through=data_through,
        )
    dates = _window_dates(start, data_through)
    daily = _daily_map(daily_records)
    total, comparison_total, reference, ratio, category, coverage, notes = _rainfall_context(
        window_dates=dates,
        daily=daily,
        config=config,
    )
    status: ClimateStatus = (
        "unavailable"
        if coverage.valid_days == 0
        else "partial"
        if (
            coverage.missing_days
            or coverage.reference_missing_days
            or coverage.comparison_valid_days == 0
            or category is None
        )
        else "ready"
    )
    extra = list(notes)
    extra.append("This is a historical weather note, not a soil-moisture measurement.")
    return HistoricalWindowFinding(
        window_type="since_harvest",
        start_date=start,
        end_date=data_through,
        status=status,
        rainfall_total_mm=total,
        rainfall_comparison_total_mm=comparison_total,
        rainfall_reference_median_mm=reference,
        rainfall_ratio=ratio,
        rainfall_category=category,
        rainfall_coverage=coverage,
        missing_parameters=("PRECTOTCORR",) if coverage.valid_days == 0 else (),
        notes=tuple(extra),
        data_through=data_through,
    )


def analyze_farm_history(
    *,
    events: Sequence[CropEventWindow],
    daily_records: Sequence[DailyClimateRecord],
    data_through: date | None,
    cell_status: ClimateStatus,
    config: EnvironmentalThresholdConfiguration = DEFAULT_ENVIRONMENTAL_CONFIGURATION,
) -> EnvironmentalAnalysis:
    """Analyze every actual crop event and a separate post-harvest interval."""

    if cell_status in {"pending", "error", "unavailable"} or data_through is None:
        return EnvironmentalAnalysis(
            status=cell_status,
            data_through=data_through,
            reference_period_start=config.reference_start_year,
            reference_period_end=config.reference_end_year,
            missing_parameters=("PRECTOTCORR", "T2M_MAX"),
        )
    windows = tuple(
        analyze_crop_window(
            event=event,
            daily_records=daily_records,
            data_through=data_through,
            config=config,
        )
        for event in events
    )
    since_harvest = (
        analyze_since_harvest(
            harvest_date=events[-1].harvest_date,
            data_through=data_through,
            daily_records=daily_records,
            config=config,
        )
        if events
        else None
    )
    latest = windows[-1] if windows else None
    adverse = latest is not None and any(
        (
            latest.rainfall_category == "Drier",
            latest.temperature_category == "Hotter",
            latest.dry_spell_category == "Longer than usual",
        )
    )
    adjustment = (
        "applied" if adverse else "not_triggered" if latest and latest.status == "ready" else None
    )
    reason = (
        "At least one available latest-crop weather indicator meets an adverse threshold."
        if adverse
        else "Latest-crop climate context is complete and does not meet an adverse threshold."
        if adjustment == "not_triggered"
        else "Weather context is incomplete or unavailable; no adjustment is assumed."
    )
    status = "ready" if all(item.status == "ready" for item in windows) else "partial"
    if cell_status == "partial":
        status = "partial"
    missing = tuple(
        dict.fromkeys(parameter for window in windows for parameter in window.missing_parameters)
    )
    return EnvironmentalAnalysis(
        status=status,
        data_through=data_through,
        reference_period_start=config.reference_start_year,
        reference_period_end=config.reference_end_year,
        crop_windows=windows,
        since_harvest=since_harvest,
        weather_weight_adjustment=adjustment,
        weather_adjustment_reason=reason,
        missing_parameters=missing,
    )
