"""Typed contracts shared by MCP tools and source adapters."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]


CompatibilityMode = Literal["wqx2", "wqx3"]


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

    @classmethod
    def from_corners(cls, a: GeoPoint, b: GeoPoint) -> BoundingBox:
        """Two opposite corners in any order, as produced by dragging a box on a map."""
        if a.latitude == b.latitude or a.longitude == b.longitude:
            raise ValueError("corners must differ in both latitude and longitude")
        return cls(
            west=min(a.longitude, b.longitude),
            south=min(a.latitude, b.latitude),
            east=max(a.longitude, b.longitude),
            north=max(a.latitude, b.latitude),
        )


class GeoPoint(BaseModel):
    """One WGS84 corner of a drawn box."""

    latitude: Latitude
    longitude: Longitude


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
    # First 8 digits of the 14-digit NHD reachcode: the containing subbasin, not the reach.
    huc8: Annotated[str | None, Field(pattern=r"^\d{8}$")] = None
    nhdplusid: str | None = None
    geometry_type: str | None = None
    bounding_box: BoundingBox | None = None
    state: str | None = None


class WaterbodyResolution(BaseModel):
    query: str
    candidates: list[WaterbodyCandidate]
    ambiguity_warning: str | None = None
    provenance: Provenance


HucLevel = Literal["huc8", "huc12"]


class WatershedCandidate(BaseModel):
    # Fits QueryScope.huc8 / AssessmentContextQuery.huc12 directly.
    huc: Annotated[str, Field(pattern=r"^(\d{8}|\d{12})$")]
    name: str | None = None
    area_sq_km: float | None = None
    states: str | None = None  # raw upstream string, e.g. "OH,IN"


class WatershedResolution(BaseModel):
    query_box: BoundingBox
    level: HucLevel
    candidates: list[WatershedCandidate]
    truncated: bool = False
    warning: str | None = None
    provenance: Provenance


class QueryScope(BaseModel):
    """Exactly one bounded WQP geographic selector or explicit station IDs."""

    station_ids: list[str] | None = Field(default=None, min_length=1, max_length=100)
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


class AssessmentContextQuery(BaseModel):
    """One exact ATTAINS assessment-unit selector or a HUC12 resolution step."""

    huc12: Annotated[str | None, Field(pattern=r"^\d{12}$")] = None
    assessment_unit_id: str | None = None
    reporting_cycle: Annotated[str | None, Field(pattern=r"^\d{4}$")] = None

    @model_validator(mode="after")
    def validate_selector(self) -> AssessmentContextQuery:
        selectors = [self.huc12, self.assessment_unit_id]
        if sum(value is not None for value in selectors) != 1:
            raise ValueError("provide exactly one of huc12 or assessment_unit_id")
        if self.assessment_unit_id is not None and not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}", self.assessment_unit_id
        ):
            raise ValueError("invalid assessment_unit_id")
        return self


class WqpQuery(BaseModel):
    scope: QueryScope
    characteristic_names: list[str] = Field(min_length=1, max_length=10)
    start_date: date
    end_date: date
    sample_media: Literal["Water", "Sediment", "Biological", "Soil", "Tissue", "Other"] = "Water"
    result_limit: Annotated[int, Field(ge=1, le=10_000)] = 1_000
    compatibility_mode: CompatibilityMode = "wqx3"

    @model_validator(mode="after")
    def valid_dates(self) -> WqpQuery:
        if self.start_date > self.end_date:
            raise ValueError("start_date must not be after end_date")
        return self
