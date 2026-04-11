from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


EventCategory = Literal["fire", "flood", "medical", "hazmat", "security", "infrastructure", "other"]
EventSeverity = Literal["low", "medium", "high", "critical"]
EventStatus = Literal["active", "resolved", "investigating"]
EventSource = Literal["human", "sensor", "radio", "api"]


class EventOut(BaseModel):
    id: int
    time: datetime
    latitude: float
    longitude: float
    category: EventCategory
    severity: EventSeverity
    status: EventStatus
    description: str
    source: EventSource
    model: str  # which LLM classified this


class EventCreate(BaseModel):
    time: datetime | None = None
    latitude: float
    longitude: float
    category: EventCategory
    severity: EventSeverity
    status: EventStatus = "active"
    description: str
    source: EventSource
    model: str = "manual"


class IngestRequest(BaseModel):
    source: EventSource
    payload: str
    lat: float = Field(default=0.0)
    lon: float = Field(default=0.0)


class IngestResponse(BaseModel):
    event_id: int
    category: EventCategory
    severity: EventSeverity
    summary: str
    model: str


class ResourceOut(BaseModel):
    id: str
    name: str
    type: Literal["hospital", "school", "social", "fire_station"]
    layer: str
    latitude: float
    longitude: float
    beds: int | None = None
    emergency: bool | None = None
    capacity: int | None = None
    operator: str | None = None
    facility_type: str | None = None
    school_type: str | None = None
    unit: str | None = None  # PSP / OSP


class LayerMeta(BaseModel):
    layer_id: str
    name: str
    data_type: str
    last_updated: datetime | None = None


class SimulationConfig(BaseModel):
    source_lat: float = Field(default=51.4158, description="Fire source latitude (Puławy default)")
    source_lon: float = Field(default=21.9698, description="Fire source longitude (Puławy default)")
    wind_speed_kmh: float = Field(default=15.0)
    wind_direction_deg: float = Field(default=45.0, description="Wind direction in degrees (0=N, 90=E)")
    fire_intensity: float = Field(default=1.0, ge=0.1, le=5.0)
    tick_interval_seconds: int = Field(default=10)


class ThreatZone(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: dict
    properties: dict


# --- Crisis Event models ---

class CrisisEvent(BaseModel):
    id: str
    type: str
    lat: float
    lon: float
    name: str
    evac_radius_km: float = 5.0
    warn_radius_km: float = 12.0
    zone_shape: Literal["circle", "ellipse"] = "circle"
    semi_major_km: float | None = None   # ellipse only — downwind extent
    semi_minor_km: float | None = None   # ellipse only — crosswind extent
    bearing_deg: float | None = None     # ellipse only — wind direction (0=N)
    status: str = "active"
    source: str = "operator"
    created_at: float


class CrisisEventCreate(BaseModel):
    type: str = "fire"
    lat: float
    lon: float
    name: str = "Pożar"
    evac_radius_km: float = 5.0
    warn_radius_km: float = 12.0
    zone_shape: Literal["circle", "ellipse"] = "circle"
    semi_major_km: float | None = None
    semi_minor_km: float | None = None
    bearing_deg: float | None = None
    status: str = "active"
    source: str = "operator"


class CrisisEventPatch(BaseModel):
    name: str | None = None
    evac_radius_km: float | None = None
    warn_radius_km: float | None = None
    zone_shape: str | None = None
    semi_major_km: float | None = None
    semi_minor_km: float | None = None
    bearing_deg: float | None = None
    status: str | None = None
