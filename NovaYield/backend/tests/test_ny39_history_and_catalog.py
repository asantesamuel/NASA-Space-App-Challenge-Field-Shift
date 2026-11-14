"""Product Direction crop catalog and farmer-reported history contracts."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.farms.catalog_seed_data import (
    CROP_IDENTITY_SEEDS,
    PRODUCT_CROP_PARAMETER_SEEDS,
    REFERENCE_OPTION_SEEDS,
    REGIONAL_CALENDAR_SEEDS,
)
from app.schemas.farms import FarmCreate


def _event(crop: str, order: int, start: str, end: str, **extra: object) -> dict[str, object]:
    return {
        "crop_key": crop,
        "sequence_order": order,
        "start_date": start,
        "end_date": end,
        **extra,
    }


def _profile(events: list[dict[str, object]], **overrides: object) -> FarmCreate:
    fields: dict[str, object] = {
        "name": "Synthetic plot",
        "location_key": "ejura",
        "soil_texture_key": "unknown",
        "irrigation_access_key": "unknown",
        "labour_capacity": "Medium",
        "history_status": "complete",
        "crop_history": events,
    }
    fields.update(overrides)
    return FarmCreate.model_validate(fields)


def test_actual_crop_events_are_preserved_without_artificial_context_dates() -> None:
    history = [
        _event("maize", 1, "2024-03-15", "2024-07-15"),
        _event("cowpea", 2, "2024-10-01", "2024-12-15"),
        _event("rice", 3, "2025-02-01", "2025-05-15", production_system_key="unknown"),
    ]
    profile = _profile(history, available_from="2025-06-01", farmer_priority="water_security")

    assert len(profile.crop_history) == 3
    assert profile.crop_history[0].start_date == date(2024, 3, 15)
    assert profile.crop_history[2].production_system_key == "unknown"
    assert profile.available_from == date(2025, 6, 1)
    assert profile.farmer_priority == "water_security"
    assert not hasattr(profile, "environment_start_date")


def test_one_to_three_event_limit_and_oldest_first_order() -> None:
    one = _profile([_event("maize", 1, "2024-03-15", "2024-07-15")])
    two_with_gap = _profile(
        [
            _event("maize", 1, "2023-03-15", "2023-07-15"),
            _event("cowpea", 2, "2024-08-01", "2024-10-01"),
        ]
    )
    assert len(one.crop_history) == 1
    assert two_with_gap.crop_history[1].start_date == date(2024, 8, 1)

    with pytest.raises(ValidationError, match="at least 1 item"):
        _profile([])
    with pytest.raises(ValidationError, match="ordered oldest first"):
        _profile(
            [
                _event("cowpea", 2, "2024-08-01", "2024-10-01"),
                _event("maize", 1, "2023-03-15", "2023-07-15"),
            ]
        )


def test_overlapping_future_or_reversed_crop_dates_are_rejected() -> None:
    with pytest.raises(ValidationError, match="cannot overlap"):
        _profile(
            [
                _event("maize", 1, "2024-03-01", "2024-06-01"),
                _event("cowpea", 2, "2024-05-01", "2024-08-01"),
            ]
        )
    with pytest.raises(ValidationError, match="future"):
        _profile([_event("maize", 1, "2099-01-01", "2099-03-01")])
    with pytest.raises(ValidationError, match="on or after"):
        _profile([_event("maize", 1, "2024-03-01", "2024-02-01")])


def test_rice_unknown_ecology_is_preserved_but_never_inferred() -> None:
    profile = _profile([_event("rice", 1, "2024-03-01", "2024-06-01")])
    assert profile.crop_history[0].production_system_key == "unknown"

    with pytest.raises(ValidationError, match="only be supplied for rice"):
        _profile(
            [
                _event(
                    "maize",
                    1,
                    "2024-03-01",
                    "2024-06-01",
                    production_system_key="irrigated",
                )
            ]
        )


def test_contract_rejects_coordinates_nasa_ranges_legacy_text_and_multi_priority_object() -> None:
    base = [_event("maize", 1, "2024-03-01", "2024-06-01")]
    for unapproved in (
        {"latitude": 7.2, "longitude": -1.5},
        {"nasa_start_date": "2024-01-01", "nasa_end_date": "2024-12-31"},
        {"current_practice": "maize then cowpea"},
        {"farmer_priority": ["water_security", "soil_health"]},
    ):
        with pytest.raises(ValidationError):
            _profile(base, **unapproved)


def test_single_shared_catalog_has_scoped_rice_and_history_only_crops() -> None:
    identities = {seed["crop_key"]: seed for seed in CROP_IDENTITY_SEEDS}
    assert identities["rice"]["history_selectable"] is True
    assert identities["rice"]["recommendation_candidate"] is False
    assert {key for key in identities if key.startswith("rice-")} == {
        "rice-upland",
        "rice-rain-fed-lowland",
        "rice-irrigated",
    }
    assert identities["plantain"]["history_selectable"] is True
    assert identities["plantain"]["recommendation_candidate"] is False
    assert identities["sorghum"]["recommendation_candidate"] is False
    assert "beans" not in identities

    candidate_keys = {seed["crop_key"] for seed in PRODUCT_CROP_PARAMETER_SEEDS}
    assert candidate_keys == {
        "maize",
        "cowpea",
        "groundnut",
        "cassava",
        "yam",
        "rice-upland",
        "rice-rain-fed-lowland",
        "rice-irrigated",
    }
    for seed in PRODUCT_CROP_PARAMETER_SEEDS:
        for field in (
            "water_resilience",
            "soil_effect",
            "maturity_days_min",
            "maturity_days_max",
            "growth_speed",
            "labour",
        ):
            assert seed[field] is not None
        assert set(seed["parameter_evidence"]) == {
            "water_resilience",
            "soil_effect",
            "maturity",
            "growth_speed",
            "labour",
        }
        for evidence in seed["parameter_evidence"].values():
            assert evidence["urls"]
            assert evidence["note"]


def test_seeded_calendars_are_active_scoped_examples_with_provisional_evidence() -> None:
    assert all(seed["source_note"] for seed in REGIONAL_CALENDAR_SEEDS)
    assert all(seed["evidence_status"] == "provisional" for seed in REGIONAL_CALENDAR_SEEDS)
    assert {seed["location_key"] for seed in REGIONAL_CALENDAR_SEEDS} == {"ejura", "anyinasu"}
    assert not any(
        seed["crop_key"] in {"groundnut", "cassava", "rice"} for seed in REGIONAL_CALENDAR_SEEDS
    )
    assert {seed["kind"] for seed in REFERENCE_OPTION_SEEDS} == {
        "soil_texture",
        "irrigation_access",
        "labour_capacity",
        "farmer_priority",
        "rice_production_system",
    }
    assert all("source_note" in seed for seed in REGIONAL_CALENDAR_SEEDS)
