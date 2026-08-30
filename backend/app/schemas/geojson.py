"""Generic GeoJSON `Feature`/`FeatureCollection` schemas, plus the concrete
geometry types this project stores — see docs/architecture.md §5.1 for the
wire format and §4.1 for why regions are restricted to these three shapes.

Generic over geometry and properties so each domain (`app/schemas/region.py`
today, photos later) plugs in its own typed shape instead of a bare `dict` —
that's what keeps `/docs` showing the real response instead of a generic
object (issue #10).
"""

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel

Position = tuple[float, float]


class Point(BaseModel):
    type: Literal["Point"] = "Point"
    coordinates: Position


class Polygon(BaseModel):
    type: Literal["Polygon"] = "Polygon"
    coordinates: list[list[Position]]


class MultiPolygon(BaseModel):
    type: Literal["MultiPolygon"] = "MultiPolygon"
    coordinates: list[list[list[Position]]]


GeometryT = TypeVar("GeometryT")
PropertiesT = TypeVar("PropertiesT")


class Feature(BaseModel, Generic[GeometryT, PropertiesT]):
    type: Literal["Feature"] = "Feature"
    id: str
    geometry: GeometryT
    properties: PropertiesT


class FeatureCollection(BaseModel, Generic[GeometryT, PropertiesT]):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[Feature[GeometryT, PropertiesT]]
