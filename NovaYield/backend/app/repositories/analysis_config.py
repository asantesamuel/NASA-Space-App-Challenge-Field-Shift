"""Read and seed the one versioned policy record used by the pure decision modules."""

from typing import Any

from pymongo.errors import DuplicateKeyError

from app.decisions.environmental_analysis import EnvironmentalThresholdConfiguration
from app.decisions.product_direction import ScoringConfiguration
from app.models.climate_store import AnalysisConfig

PRODUCT_DIRECTION_CONFIG_VERSION = "product-direction-config-v1"


class AnalysisConfigRepository:
    def __init__(self, config_model: Any = AnalysisConfig) -> None:
        self._config_model = config_model

    async def get_active(self) -> AnalysisConfig | None:
        return await self._config_model.find_one({"is_active": True})

    async def seed_default(self) -> int:
        """Insert a versioned default only when an operator has not already seeded one."""

        if await self.get_active() is not None:
            return 0
        config = self._config_model(
            version=PRODUCT_DIRECTION_CONFIG_VERSION,
            is_active=True,
        )
        try:
            await config.insert()
        except DuplicateKeyError:
            if await self.get_active() is None:
                raise
            return 0
        return 1

    @staticmethod
    def environmental_thresholds(config: AnalysisConfig) -> EnvironmentalThresholdConfiguration:
        return EnvironmentalThresholdConfiguration(
            version=config.version,
            reference_start_year=config.reference_start_year,
            reference_end_year=config.reference_end_year,
            dry_day_threshold_mm=config.dry_day_threshold_mm,
            rainfall_drier_ratio=config.rainfall_drier_ratio,
            rainfall_wetter_ratio=config.rainfall_wetter_ratio,
            temperature_delta_c=config.temperature_delta_c,
            dry_spell_percentile=config.dry_spell_percentile,
        )

    @staticmethod
    def scoring_configuration(config: AnalysisConfig) -> ScoringConfiguration:
        return ScoringConfiguration(
            version=config.version,
            fast_growth_max_days=config.fast_growth_max_days,
            medium_growth_max_days=config.medium_growth_max_days,
            turnaround_days=config.turnaround_days,
            horizon_months=config.calendar_horizon_months,
            base_weight=config.starting_weight,
            adverse_weather_water_weight=config.step_one_weather_water_weight,
            preceding_cereal_soil_weight=config.preceding_cereal_soil_weight,
            priority_adjustment=config.farmer_priority_adjustment,
        )
