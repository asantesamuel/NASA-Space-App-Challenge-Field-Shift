"""Pure paired rainfall metrics for the bounded operator study."""

from calendar import monthrange
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from math import fsum
from typing import Literal

from app.decisions.environmental_analysis import DRY_DAY_THRESHOLD_MM, _longest_dry_run

PILOT_LOCATIONS = ("ejura", "anyinasu", "kintampo")
STUDY_START = date(2023, 1, 1)
STUDY_END = date(2024, 12, 31)
METHOD_VERSION = "paired-utc-rainfall-v1"
RainDays = Mapping[date, float | None]


@dataclass(frozen=True)
class RainfallComparison:
    location_key: str
    window_type: Literal["benchmark", "month"]
    start_date: date
    end_date: date
    expected_days: int
    power_valid_days: int
    imerg_valid_days: int
    paired_days: int
    paired_coverage: float
    power_paired_total_mm: float | None
    imerg_paired_total_mm: float | None
    total_difference_mm: float | None
    mean_daily_difference_mm: float | None
    mean_absolute_daily_difference_mm: float | None
    power_longest_dry_spell_days: int | None
    imerg_longest_dry_spell_days: int | None


def compare_window(
    location_key: str,
    window_type: Literal["benchmark", "month"],
    start: date,
    end: date,
    power: RainDays,
    imerg: RainDays,
) -> RainfallComparison:
    dates = [start + timedelta(days=offset) for offset in range((end - start).days + 1)]
    power_values = [power.get(day) for day in dates]
    imerg_values = [imerg.get(day) for day in dates]
    paired = [
        (p, i)
        for p, i in zip(power_values, imerg_values, strict=True)
        if p is not None and i is not None
    ]
    differences = [i - p for p, i in paired]
    count = len(paired)
    complete_benchmark = count == len(dates) and window_type == "benchmark"
    return RainfallComparison(
        location_key=location_key,
        window_type=window_type,
        start_date=start,
        end_date=end,
        expected_days=len(dates),
        power_valid_days=sum(value is not None for value in power_values),
        imerg_valid_days=sum(value is not None for value in imerg_values),
        paired_days=count,
        paired_coverage=count / len(dates),
        power_paired_total_mm=fsum(p for p, _ in paired) if count else None,
        imerg_paired_total_mm=fsum(i for _, i in paired) if count else None,
        total_difference_mm=fsum(differences) if count else None,
        mean_daily_difference_mm=fsum(differences) / count if count else None,
        mean_absolute_daily_difference_mm=fsum(map(abs, differences)) / count if count else None,
        power_longest_dry_spell_days=(
            _longest_dry_run(power_values, DRY_DAY_THRESHOLD_MM)[0] if complete_benchmark else None
        ),
        imerg_longest_dry_spell_days=(
            _longest_dry_run(imerg_values, DRY_DAY_THRESHOLD_MM)[0] if complete_benchmark else None
        ),
    )


def compare_pilot(
    power: Mapping[str, RainDays], imerg: Mapping[str, RainDays]
) -> list[RainfallComparison]:
    rows = []
    for location in PILOT_LOCATIONS:
        for year in range(STUDY_START.year, STUDY_END.year + 1):
            for start, end in (
                (date(year, 3, 1), date(year, 4, 30)),
                (date(year, 7, 15), date(year, 9, 10)),
            ):
                rows.append(
                    compare_window(
                        location, "benchmark", start, end, power.get(location, {}), imerg[location]
                    )
                )
            for month in range(1, 13):
                rows.append(
                    compare_window(
                        location,
                        "month",
                        date(year, month, 1),
                        date(year, month, monthrange(year, month)[1]),
                        power.get(location, {}),
                        imerg[location],
                    )
                )
    return rows
