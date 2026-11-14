"""Tests for the app-local API v1 routes under Product Direction v1."""

import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings
from app.main import create_app

TEST_CSRF_SECRET = "csrf-secret-for-tests-that-is-long-enough"
TEST_LOCATION_HASH_SECRET = "location-hash-test-secret-that-is-long-enough"


def make_settings() -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        csrf_secret=SecretStr(TEST_CSRF_SECRET),
        location_hash_secret=SecretStr(TEST_LOCATION_HASH_SECRET),
    )


def test_create_app_composes_new_versioned_feature_routes() -> None:
    first_app = create_app(make_settings())
    second_app = create_app(make_settings())
    first_paths = first_app.openapi()["paths"]
    second_paths = second_app.openapi()["paths"]

    expected_paths = {
        "/api/v1/crops",
        "/api/v1/farms/reference-options",
        "/api/v1/farms/locations",
        "/api/v1/farms",
        "/api/v1/farms/{farm_id}",
        "/api/v1/farms/{farm_id}/rotation-results",
        "/api/v1/farms/{farm_id}/rotation-results/{result_id}",
        "/api/v1/farms/{farm_id}/environment",
        "/api/v1/farms/{farm_id}/recommendations",
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/logout",
    }
    assert expected_paths <= first_paths.keys()
    assert first_paths.keys() == second_paths.keys()
    assert set(first_paths["/api/v1/farms"]) == {"get", "post"}
    assert set(first_paths["/api/v1/farms/{farm_id}"]) == {"get", "patch"}
    assert set(first_paths["/api/v1/farms/{farm_id}/rotation-results"]) == {"get"}

    environment = first_paths["/api/v1/farms/{farm_id}/environment"]["get"]
    assert environment["security"]
    assert {"200", "401", "404", "409", "503"} <= environment["responses"].keys()
    recommendation = first_paths["/api/v1/farms/{farm_id}/recommendations"]["post"]
    assert recommendation["security"]
    assert recommendation["responses"]["201"]["content"]["application/json"]["schema"][
        "$ref"
    ].endswith("/ProductDirectionRecommendationResponse")
    request_body = recommendation["requestBody"]["content"]["application/json"]["schema"]
    request_refs = {schema.get("$ref", "") for schema in request_body.get("anyOf", [request_body])}
    assert any(
        reference.endswith("/ProductDirectionRecommendationRequest") for reference in request_refs
    )
    request_schema = first_app.openapi()["components"]["schemas"][
        "ProductDirectionRecommendationRequest"
    ]
    assert set(request_schema["properties"]) == {"priority"}


def test_location_hash_secret_requires_at_least_32_bytes() -> None:
    with pytest.raises(ValidationError, match="at least 32 bytes"):
        Settings(
            _env_file=None,
            csrf_secret=SecretStr(TEST_CSRF_SECRET),
            location_hash_secret=SecretStr("too-short"),
        )
