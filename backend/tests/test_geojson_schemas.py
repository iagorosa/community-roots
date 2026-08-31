"""Tests for the typed GeoJSON schemas (backend/app/schemas/geojson.py, region.py).

Issue #10's "critério de pronto" is that `/docs` shows the real response
shape instead of a generic `dict` — the same guarantee `model_json_schema()`
gives, since that's what FastAPI uses to build the OpenAPI document.
"""

import pytest
from pydantic import ValidationError

from app.schemas.region import (
    RegionCreate,
    RegionFeature,
    RegionFeatureCollection,
    RegionUpdate,
)

_ARCHITECTURE_DOC_EXAMPLE = {
    "type": "Feature",
    "id": "0f1c1234-5678-90ab-cdef-1234567890ab",
    "geometry": {
        "type": "Polygon",
        "coordinates": [[[-43.3129, -21.8843], [-43.3125, -21.8843], [-43.3125, -21.8840]]],
    },
    "properties": {
        "slug": "canteiro-do-ipe",
        "name": "Canteiro do Ipê",
        "description": "...",
        "status": "active",
        "qr_token": "k3Zq8xR2mNvA",
        "planting_count": 12,
        "created_at": "2026-08-01T10:00:00Z",
        "updated_at": "2026-08-24T14:03:11Z",
    },
}


def _schema_property(json_schema: dict, model_name: str, property_name: str) -> dict:
    """Resolve a property's schema, following a single `$ref` into `$defs` if needed."""
    prop = json_schema["$defs"][model_name]["properties"][property_name]
    if "$ref" in prop:
        ref_name = prop["$ref"].removeprefix("#/$defs/")
        return json_schema["$defs"][ref_name]
    return prop


def test_region_feature_schema_types_geometry_and_properties() -> None:
    json_schema = RegionFeatureCollection.model_json_schema()

    geometry_schema = _schema_property(json_schema, "RegionFeature", "geometry")
    properties_schema = _schema_property(json_schema, "RegionFeature", "properties")

    # A generic `dict`/untyped object schema is just `{"type": "object"}`,
    # with no `properties`/`oneOf`/`anyOf` of its own — that's what `/docs`
    # would show if these fields were left as `dict` instead of typed models.
    assert properties_schema.keys() & {"properties", "oneOf", "anyOf"}
    assert geometry_schema.keys() & {"properties", "oneOf", "anyOf"}
    # The geometry union is discriminated on GeoJSON's own `type` field, so
    # `/docs` renders it as an explicit `oneOf` (Point/Polygon/MultiPolygon)
    # rather than pydantic's looser "try each member" `anyOf`.
    assert "oneOf" in geometry_schema
    assert geometry_schema["discriminator"]["propertyName"] == "type"


def test_region_feature_round_trips_the_architecture_doc_example() -> None:
    feature = RegionFeature.model_validate(_ARCHITECTURE_DOC_EXAMPLE)

    assert feature.properties.slug == "canteiro-do-ipe"
    assert feature.properties.planting_count == 12
    assert feature.geometry.type == "Polygon"


def test_region_create_requires_geometry() -> None:
    with pytest.raises(ValidationError):
        RegionCreate.model_validate({"name": "Canteiro Novo"})


def test_region_update_accepts_a_partial_payload() -> None:
    update = RegionUpdate.model_validate({"name": "Novo nome"})

    assert update.name == "Novo nome"
    assert update.description is None
    assert update.geometry is None
    assert update.status is None


def test_region_create_rejects_unknown_fields() -> None:
    # `slug`/`qr_token` are server-generated (region_service, issue #12) —
    # a client that thinks it's setting them should get a loud error, not
    # have them silently dropped.
    payload = {
        "name": "Canteiro Novo",
        "geometry": {"type": "Point", "coordinates": [-43.31, -21.88]},
        "slug": "canteiro-novo",
    }

    with pytest.raises(ValidationError):
        RegionCreate.model_validate(payload)


def test_region_update_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        RegionUpdate.model_validate({"qr_token": "attempted-override"})
