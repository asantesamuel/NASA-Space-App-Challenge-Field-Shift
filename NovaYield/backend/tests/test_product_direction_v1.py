from datetime import date, timedelta

from app.decisions.environmental_analysis import (
    CropEventWindow,
    DailyClimateRecord,
    analyze_crop_window,
    analyze_since_harvest,
)
from app.decisions.product_direction import (
    CropHistoryWeather,
    PlantingCalendar,
    RotationCrop,
    ScoringConfiguration,
    _step_score,
    derive_growth_speed,
    generate_ranked_rotations,
    schedule_rotation,
)


def _daily_for_window(
    start: date,
    end: date,
    *,
    rainfall: float | None,
    maximum_temperature: float | None,
) -> list[DailyClimateRecord]:
    rows: list[DailyClimateRecord] = []
    current = start
    while current <= end:
        rows.append(
            DailyClimateRecord(
                day=current,
                rain_mm=rainfall,
                t2m_max_c=maximum_temperature,
            )
        )
        current += timedelta(days=1)
    return rows


def _reference_and_observed_rows(
    *,
    observed_rain: tuple[float | None, float | None] = (1.0, 1.0),
    observed_maximum: float = 32.0,
    reference_rain: float = 2.0,
    reference_maximum: float = 30.0,
) -> list[DailyClimateRecord]:
    rows: list[DailyClimateRecord] = []
    for year in range(1991, 2021):
        rows.extend(
            _daily_for_window(
                date(year, 1, 1),
                date(year, 1, 2),
                rainfall=reference_rain,
                maximum_temperature=reference_maximum,
            )
        )
    rows.extend(
        [
            DailyClimateRecord(
                day=date(2026, 1, 1), rain_mm=observed_rain[0], t2m_max_c=observed_maximum
            ),
            DailyClimateRecord(
                day=date(2026, 1, 2), rain_mm=observed_rain[1], t2m_max_c=observed_maximum
            ),
        ]
    )
    return rows


def test_historical_window_uses_matched_30_year_context() -> None:
    finding = analyze_crop_window(
        event=CropEventWindow(
            crop_key="maize",
            sequence_order=1,
            planting_date=date(2026, 1, 1),
            harvest_date=date(2026, 1, 2),
        ),
        daily_records=_reference_and_observed_rows(),
        data_through=date(2026, 1, 2),
    )

    assert finding.rainfall_total_mm == 2.0
    assert finding.rainfall_comparison_total_mm == 2.0
    assert finding.rainfall_reference_median_mm == 4.0
    assert finding.rainfall_ratio == 0.5
    assert finding.rainfall_category == "Drier"
    assert finding.temperature_delta_c == 2.0
    assert finding.comparison_mean_t2m_max_c == 32.0
    assert finding.reference_mean_t2m_max_c == 30.0
    assert finding.temperature_category == "Hotter"
    assert finding.rainfall_coverage.valid_days == 2
    assert finding.rainfall_coverage.matching_reference_years == 30


def test_missing_observed_date_is_dropped_from_each_comparison() -> None:
    finding = analyze_crop_window(
        event=CropEventWindow(
            crop_key="maize",
            sequence_order=1,
            planting_date=date(2026, 1, 1),
            harvest_date=date(2026, 1, 2),
        ),
        daily_records=_reference_and_observed_rows(observed_rain=(2.0, None)),
        data_through=date(2026, 1, 2),
    )

    assert finding.rainfall_total_mm == 2.0
    assert finding.rainfall_reference_median_mm == 2.0
    assert finding.rainfall_ratio == 1.0
    assert finding.rainfall_coverage.valid_days == 1
    assert finding.rainfall_coverage.missing_days == 1
    assert finding.status == "partial"


def test_reference_missing_date_is_removed_from_all_years_for_matched_comparison() -> None:
    rows = _reference_and_observed_rows()
    rows = [row for row in rows if row.day != date(1995, 1, 2)]

    finding = analyze_crop_window(
        event=CropEventWindow(
            crop_key="maize",
            sequence_order=1,
            planting_date=date(2026, 1, 1),
            harvest_date=date(2026, 1, 2),
        ),
        daily_records=rows,
        data_through=date(2026, 1, 2),
    )

    assert finding.rainfall_total_mm == 2.0
    assert finding.rainfall_reference_median_mm == 2.0
    assert finding.rainfall_coverage.comparison_valid_days == 1
    assert finding.rainfall_coverage.reference_missing_days == 1
    assert finding.temperature_coverage is not None
    assert finding.temperature_coverage.comparison_valid_days == 1
    assert finding.temperature_coverage.reference_missing_days == 1
    assert finding.status == "partial"
    assert any("omitted from all reference years" in note for note in finding.notes)


def test_zero_rainfall_reference_is_explicitly_unclassified() -> None:
    finding = analyze_crop_window(
        event=CropEventWindow(
            crop_key="maize",
            sequence_order=1,
            planting_date=date(2026, 1, 1),
            harvest_date=date(2026, 1, 2),
        ),
        daily_records=_reference_and_observed_rows(reference_rain=0.0),
        data_through=date(2026, 1, 2),
    )

    assert finding.rainfall_total_mm == 2.0
    assert finding.rainfall_reference_median_mm == 0.0
    assert finding.rainfall_ratio is None
    assert finding.rainfall_category is None
    assert any("median is zero" in note for note in finding.notes)


def test_dry_spell_crosses_year_boundary_and_missing_day_reports_lower_bound() -> None:
    start = date(2025, 12, 30)
    end = date(2026, 1, 3)
    rows: list[DailyClimateRecord] = []
    actual_values = (0.2, 0.1, None, 0.3, 0.2)
    for year in range(1991, 2021):
        for index in range((end - start).days + 1):
            observed_day = start + timedelta(days=index)
            reference_day = date(year, observed_day.month, observed_day.day)
            rows.append(DailyClimateRecord(day=reference_day, rain_mm=2.0, t2m_max_c=30.0))
    rows.extend(
        DailyClimateRecord(
            day=start + timedelta(days=index),
            rain_mm=actual_values[index],
            t2m_max_c=32.0,
        )
        for index in range(len(actual_values))
    )

    finding = analyze_crop_window(
        event=CropEventWindow(
            crop_key="maize",
            sequence_order=1,
            planting_date=start,
            harvest_date=end,
        ),
        daily_records=rows,
        data_through=end,
    )

    assert finding.longest_dry_spell_days == 2
    assert finding.longest_dry_spell_text == "at least 2 days"
    assert finding.dry_spell_coverage is not None
    assert finding.dry_spell_coverage.matching_reference_years == 30
    assert any("lower bound" in note for note in finding.notes)


def test_leap_day_is_dropped_from_observed_and_reference_coverage() -> None:
    rows = _reference_and_observed_rows()
    rows.extend(
        [
            DailyClimateRecord(day=date(2024, 2, 28), rain_mm=1, t2m_max_c=30),
            DailyClimateRecord(day=date(2024, 2, 29), rain_mm=1, t2m_max_c=30),
            DailyClimateRecord(day=date(2024, 3, 1), rain_mm=1, t2m_max_c=30),
        ]
    )
    finding = analyze_crop_window(
        event=CropEventWindow(
            crop_key="maize",
            sequence_order=1,
            planting_date=date(2024, 2, 28),
            harvest_date=date(2024, 3, 1),
        ),
        daily_records=rows,
        data_through=date(2024, 3, 1),
    )

    assert finding.rainfall_coverage.expected_days == 2
    assert finding.rainfall_coverage.leap_days_excluded == 1
    assert any("29 February" in note for note in finding.notes)


def test_zero_valid_observed_days_make_window_unavailable_not_zero() -> None:
    finding = analyze_crop_window(
        event=CropEventWindow(
            crop_key="maize",
            sequence_order=1,
            planting_date=date(2026, 1, 1),
            harvest_date=date(2026, 1, 2),
        ),
        daily_records=[
            DailyClimateRecord(day=date(2026, 1, 1)),
            DailyClimateRecord(day=date(2026, 1, 2)),
        ],
        data_through=date(2026, 1, 2),
    )

    assert finding.status == "unavailable"
    assert finding.rainfall_total_mm is None
    assert finding.mean_t2m_max_c is None
    assert finding.rainfall_coverage.valid_days == 0
    assert finding.rainfall_coverage.missing_days == 2


def test_since_harvest_is_a_weather_note_with_no_soil_claim() -> None:
    finding = analyze_since_harvest(
        harvest_date=date(2026, 1, 1),
        data_through=date(2026, 1, 3),
        daily_records=[
            DailyClimateRecord(day=date(2026, 1, 2), rain_mm=1.0),
            DailyClimateRecord(day=date(2026, 1, 3), rain_mm=2.0),
        ],
    )

    assert finding.start_date == date(2026, 1, 2)
    assert finding.rainfall_total_mm == 3.0
    assert any("not a soil-moisture" in note for note in finding.notes)


def _crop(
    key: str,
    group: str,
    *,
    labour: str = "Low",
    growth: str = "Medium",
    water: str = "Medium",
    soil: str = "Neutral",
    maturity: int = 30,
    candidate: bool = True,
    production_system: str | None = None,
) -> RotationCrop:
    return RotationCrop(
        crop_key=key,
        name=key.title(),
        group=group,
        water_resilience=water,
        soil_effect=soil,
        growth_speed=growth,
        labour=labour,
        maturity_days_min=maturity,
        maturity_days_max=maturity,
        recommendation_candidate=candidate,
        production_system=production_system,
    )


def _calendar(key: str, group: str) -> PlantingCalendar:
    return PlantingCalendar(
        location_key="ejura",
        crop_key=key,
        season_key="any-season",
        start_month=1,
        start_day=1,
        end_month=12,
        end_day=31,
        source=f"test-{group}",
        version="test-v1",
    )


def _generate(
    crops: tuple[RotationCrop, ...],
    *,
    priority: str | None = None,
    adverse: bool = False,
    labour_capacity: str = "Medium",
    latest_crop: RotationCrop | None = None,
    calendars: tuple[PlantingCalendar, ...] | None = None,
    maximum_options: int = 3,
):
    return generate_ranked_rotations(
        crops=crops,
        calendars=(
            calendars
            if calendars is not None
            else tuple(_calendar(crop.crop_key, crop.group) for crop in crops)
        ),
        location_key="ejura",
        available_from=date(2026, 1, 1),
        today=date(2026, 1, 1),
        labour_capacity=labour_capacity,
        priority=priority,
        latest_crop=latest_crop,
        weather=CropHistoryWeather(
            rainfall_status="Drier" if adverse else "Normal",
            context_status="ready",
        ),
        catalogue_version="catalog-v1",
        calendar_version="calendar-v1",
        config=ScoringConfiguration(),
        maximum_options=maximum_options,
    )


def test_hard_filters_and_soft_group_diversity() -> None:
    crops = (
        _crop("maize", "Cereal"),
        _crop("cowpea", "Legume"),
        _crop("yam", "Root/tuber"),
        _crop("high-labour", "Cereal", labour="High"),
        _crop("disabled", "Cereal").model_copy(update={"recommendation_candidate": False}),
    )
    result = _generate(crops)

    assert result.status == "ranked"
    assert len(result.options) == 3
    assert all("high-labour" not in option.crops for option in result.options)
    assert all("disabled" not in option.crops for option in result.options)
    assert any(option.diversity_transitions == 2 for option in result.options)
    assert result.exclusion_counts["labour_capacity"] == 1
    assert result.exclusion_counts["candidate_disabled"] == 1


def test_weather_adjustment_applies_only_to_first_future_step() -> None:
    crop = _crop("maize", "Cereal")
    result = _generate((crop,), adverse=True)
    option = result.options[0]

    assert option.step_scores[0].weights["water_resilience"] == 2
    assert option.step_scores[0].weather_adjustment == "applied"
    assert option.step_scores[1].weights["water_resilience"] == 1
    assert option.step_scores[2].weights["water_resilience"] == 1


def test_same_inputs_reproduce_order_and_one_priority_is_applied() -> None:
    crops = (_crop("maize", "Cereal"), _crop("cowpea", "Legume"), _crop("yam", "Root/tuber"))
    first = _generate(crops, priority="fast_turnover")
    second = _generate(crops, priority="fast_turnover")

    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.selected_priority == "fast_turnover"
    assert all("growth_speed" in option.step_scores[0].weights for option in first.options)


def test_diversity_is_the_first_tie_break_and_output_is_capped_at_three() -> None:
    crops = (
        _crop("maize", "Cereal"),
        _crop("cowpea", "Legume"),
        _crop("yam", "Root/tuber"),
    )
    result = _generate(crops, maximum_options=100)

    assert len(result.options) == 3
    assert all(option.score == result.options[0].score for option in result.options)
    assert all(option.diversity_transitions == 2 for option in result.options)
    assert all(len(option.events) == 3 for option in result.options)


def test_farmer_priority_changes_weighted_scores_without_overriding_constraints() -> None:
    water_strong = _crop(
        "water-strong", "Cereal", water="High", soil="Draws down", growth="Slow", labour="High"
    )
    labour_strong = _crop(
        "labour-strong", "Legume", water="Low", soil="Adds nitrogen", growth="Fast", labour="Low"
    )
    neutral = _crop("neutral", "Root/tuber")
    water_first = _generate(
        (water_strong, labour_strong, neutral), priority="water_security", labour_capacity="High"
    )
    labour_first = _generate(
        (water_strong, labour_strong, neutral), priority="low_labour", labour_capacity="High"
    )

    assert water_first.options[0].crops != labour_first.options[0].crops
    assert all(
        "water-strong" in option.crops or "labour-strong" in option.crops
        for option in water_first.options
    )
    low_capacity = _generate(
        (water_strong, labour_strong, neutral), priority="water_security", labour_capacity="Low"
    )
    assert all("water-strong" not in option.crops for option in low_capacity.options)


def test_soil_weight_uses_preceding_crop_and_water_adjustment_does_not_carry_forward() -> None:
    maize = _crop("maize", "Cereal", soil="Draws down")
    cowpea = _crop("cowpea", "Legume", soil="Adds nitrogen")
    yam = _crop("yam", "Root/tuber")
    adverse_weather = CropHistoryWeather(rainfall_status="Drier", context_status="ready")
    normal_weather = CropHistoryWeather(context_status="ready")
    config = ScoringConfiguration()
    first = _step_score(
        order=1,
        crop=cowpea,
        preceding=maize,
        weather=adverse_weather,
        priority=None,
        config=config,
    )
    second = _step_score(
        order=2,
        crop=yam,
        preceding=cowpea,
        weather=adverse_weather,
        priority=None,
        config=config,
    )
    third = _step_score(
        order=3,
        crop=maize,
        preceding=yam,
        weather=normal_weather,
        priority=None,
        config=config,
    )

    assert first.weights["water_resilience"] == 2
    assert first.weights["soil_health"] == 2
    assert second.weights["water_resilience"] == 1
    assert second.weights["soil_health"] == 1
    assert third.weights["soil_health"] == 1


def test_growth_speed_uses_configured_maturity_cutoffs() -> None:
    assert derive_growth_speed(60, 80) == "Fast"
    assert derive_growth_speed(74, 76) == "Medium"
    assert derive_growth_speed(150, 150) == "Medium"
    assert derive_growth_speed(151, 180) == "Slow"


def test_unsupported_rice_and_disabled_crops_are_filtered_without_group_exclusion() -> None:
    crops = (
        _crop("maize", "Cereal"),
        _crop("rice-unknown", "Cereal", production_system="unknown"),
        _crop("disabled", "Legume", candidate=False),
    )
    result = _generate(crops)

    assert result.status == "ranked"
    assert all("rice-unknown" not in option.crops for option in result.options)
    assert all("disabled" not in option.crops for option in result.options)
    assert any(len(set(option.crops)) == 1 for option in result.options)
    assert result.exclusion_counts["unsupported_rice_system"] == 1


def test_scheduler_uses_the_open_window_then_handles_a_december_january_window() -> None:
    crops = {
        key: _crop(key, group, maturity=20)
        for key, group in (("maize", "Cereal"), ("cowpea", "Legume"), ("yam", "Root/tuber"))
    }
    calendars = (
        PlantingCalendar(
            location_key="ejura",
            crop_key="maize",
            season_key="already-open",
            start_month=1,
            start_day=1,
            end_month=1,
            end_day=31,
            source="test",
            version="v1",
        ),
        PlantingCalendar(
            location_key="ejura",
            crop_key="cowpea",
            season_key="crosses-year",
            start_month=12,
            start_day=15,
            end_month=1,
            end_day=15,
            source="test",
            version="v1",
        ),
        PlantingCalendar(
            location_key="ejura",
            crop_key="yam",
            season_key="year-round",
            start_month=1,
            start_day=1,
            end_month=12,
            end_day=31,
            source="test",
            version="v1",
        ),
    )

    events = schedule_rotation(
        crop_keys=("maize", "cowpea", "yam"),
        crops_by_key=crops,
        calendars=calendars,
        location_key="ejura",
        available_from=date(2026, 1, 10),
        today=date(2026, 1, 1),
        horizon_months=24,
        turnaround_days=14,
    )

    assert events is not None
    assert events[0].planting_date == date(2026, 1, 10)
    assert events[1].planting_date == date(2026, 12, 15)
    assert events[1].harvest_earliest == date(2027, 1, 4)
    assert events[2].planting_date == date(2027, 1, 18)


def test_long_maturity_sequence_with_no_full_schedule_in_horizon_is_rejected() -> None:
    long_crop = _crop("cassava", "Root/tuber", maturity=365)
    calendars = (_calendar("cassava", "Root/tuber"),)
    result = _generate(
        (long_crop,),
        calendars=calendars,
    )

    assert result.status == "no_options"
    assert result.options == ()
    assert result.exclusion_counts["calendar_or_horizon"] > 0
