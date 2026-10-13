"""Typed contracts shared by MCP tools and source adapters."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]


class BoundingBox(BaseModel):
    """WGS84 west, south, east, north spatial extent."""

    west: Longitude
    south: Latitude
    east: Longitude
    north: Latitude

    @model_validator(mode="after")
    def validate_order(self) -> BoundingBox:
        if self.west >= self.east:
            raise ValueError("west must be less than east; antimeridian boxes are unsupported")
        if self.south >= self.north:
            raise ValueError("south must be less than north")
        return self

    def wqp_value(self) -> str:
        return f"{self.west},{self.south},{self.east},{self.north}"


class PointRadius(BaseModel):
    latitude: Latitude
    longitude: Longitude
    within_miles: Annotated[float, Field(gt=0, le=100)] = 10


class Provenance(BaseModel):
    source: str
    source_version: str
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    query_url: str
    caveat: str


class WaterbodyCandidate(BaseModel):
    name: str
    reachcode: str | None = None
    nhdplusid: str | None = None
    geometry_type: str | None = None
    bounding_box: BoundingBox | None = None
    state: str | None = None


class WaterbodyResolution(BaseModel):
    query: str
    candidates: list[WaterbodyCandidate]
    ambiguity_warning: str | None = None
    provenance: Provenance


class QueryScope(BaseModel):
    """Exactly one bounded WQP geographic selector or explicit station IDs."""

    station_ids: list[str] | None = Field(default=None, max_length=100)
    bounding_box: BoundingBox | None = None
    point_radius: PointRadius | None = None
    huc8: Annotated[str | None, Field(pattern=r"^\d{8}$")] = None

    @model_validator(mode="after")
    def exactly_one_selector(self) -> QueryScope:
        selectors = [self.station_ids, self.bounding_box, self.point_radius, self.huc8]
        if sum(value is not None for value in selectors) != 1:
            raise ValueError(
                "provide exactly one of station_ids, bounding_box, point_radius, or huc8"
            )
        return self


class WqpQuery(BaseModel):
    scope: QueryScope
    characteristic_names: list[str] = Field(min_length=1, max_length=10)
    start_date: date
    end_date: date
    sample_media: Literal["Water", "Sediment", "Biological", "Soil", "Tissue", "Other"] = "Water"
    result_limit: Annotated[int, Field(ge=1, le=10_000)] = 1_000

    @model_validator(mode="after")
    def valid_dates(self) -> WqpQuery:
        if self.start_date > self.end_date:
            raise ValueError("start_date must not be after end_date")
        return self
