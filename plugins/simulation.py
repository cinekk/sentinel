"""
SimulationPlugin — industrial fire scenario with spreading plume.

State is held in-memory (reset on restart is fine for hackathon).
On start, writes a CrisisEvent to crisis_store with zone_shape="ellipse".
Each tick patches the event's ellipse geometry — alerts flow through
/api/v1/crisis/affected, not through this plugin's state.
"""
import asyncio
import math
import random
from datetime import datetime, timezone

import services.crisis_store as crisis_store
from database import SessionLocal, EventRow
from models import CrisisEventCreate, CrisisEventPatch, SimulationConfig
from plugins.base import BasePlugin


_PRESET = SimulationConfig(
    source_lat=51.4158,
    source_lon=21.9698,
    wind_speed_kmh=15.0,
    wind_direction_deg=45.0,  # NE
    fire_intensity=1.0,
    tick_interval_seconds=10,
)


class SimulationPlugin(BasePlugin):
    layer_id = "simulation_threat"
    layer_name = "Strefa Zagrożenia (symulacja)"
    data_type = "threat_zone"

    def __init__(self) -> None:
        self._running = False
        self._tick = 0
        self._config: SimulationConfig = _PRESET
        self._crisis_id: str | None = None
        self._task: asyncio.Task | None = None

    # ── Public control ───────────────────────────────────────────────────────

    def start(self, config: SimulationConfig | None = None) -> None:
        if self._running:
            return
        self._config = config or _PRESET
        self._tick = 0
        self._running = True

        event = crisis_store.add(CrisisEventCreate(
            type="fire",
            lat=self._config.source_lat,
            lon=self._config.source_lon,
            name="Pożar Zakładów Azotowych Puławy",
            zone_shape="ellipse",
            semi_major_km=0.1,
            semi_minor_km=0.05,
            bearing_deg=self._config.wind_direction_deg,
            source="simulation",
        ))
        self._crisis_id = event.id
        self._task = asyncio.create_task(self._loop())

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        if self._crisis_id:
            crisis_store.patch(self._crisis_id, CrisisEventPatch(status="resolved"))

    def reset(self) -> None:
        self.stop()
        if self._crisis_id:
            crisis_store.delete(self._crisis_id)
            self._crisis_id = None
        self._tick = 0

    @property
    def running(self) -> bool:
        return self._running

    @property
    def tick(self) -> int:
        return self._tick

    @property
    def state(self) -> dict:
        return {
            "running": self._running,
            "tick": self._tick,
            "config": self._config.model_dump(),
            "crisis_id": self._crisis_id,
        }

    # ── BasePlugin ───────────────────────────────────────────────────────────

    async def fetch(self) -> dict:
        """Return current threat zone ellipse + synthetic sensor readings as GeoJSON."""
        features = []

        # Reconstruct visual ellipse from crisis store
        if self._crisis_id:
            event = crisis_store.get(self._crisis_id)
            if event and event.status == "active" and event.semi_major_km:
                elapsed_hours = (self._tick * self._config.tick_interval_seconds) / 3600.0
                drift_km = self._config.wind_speed_kmh * elapsed_hours * 0.5
                bearing_rad = math.radians(self._config.wind_direction_deg)
                center_lat = self._config.source_lat + (drift_km / 111.0) * math.cos(bearing_rad)
                center_lon = self._config.source_lon + (drift_km / (111.0 * math.cos(math.radians(self._config.source_lat)))) * math.sin(bearing_rad)
                features.append({
                    "type": "Feature",
                    "geometry": _ellipse_polygon(
                        center_lat, center_lon,
                        event.semi_major_km, event.semi_minor_km or event.semi_major_km * 0.45,
                        event.bearing_deg or 0.0,
                    ),
                    "properties": {
                        "type": "threat_zone",
                        "tick": self._tick,
                        "semi_major_km": round(event.semi_major_km, 2),
                        "semi_minor_km": round(event.semi_minor_km or 0, 2),
                        "center_lat": center_lat,
                        "center_lon": center_lon,
                        "bearing_deg": event.bearing_deg,
                        "elapsed_min": round(self._tick * self._config.tick_interval_seconds / 60, 1),
                    },
                })

        # Synthetic sensor readings around source
        if self._running and self._tick > 0:
            for i in range(5):
                angle = (i / 5) * 2 * math.pi
                dist = 0.02 + random.uniform(0, 0.01)
                lat = self._config.source_lat + dist * math.sin(angle)
                lon = self._config.source_lon + dist * math.cos(angle)
                elapsed = self._tick * self._config.tick_interval_seconds
                pm25 = _pm25_at_distance(dist * 111, elapsed, self._config)
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    "properties": {
                        "type": "sensor",
                        "pm25": round(pm25, 1),
                        "pm10": round(pm25 * 1.6, 1),
                        "tick": self._tick,
                        "name": f"Czujnik {i+1}",
                    },
                })

        self._last_updated = datetime.now(timezone.utc)
        return {"type": "FeatureCollection", "features": features}

    # ── Tick loop ────────────────────────────────────────────────────────────

    async def _loop(self) -> None:
        while self._running:
            await asyncio.sleep(self._config.tick_interval_seconds)
            if not self._running:
                break
            self._tick += 1
            self._advance()
            await self._persist_event()

    def _advance(self) -> None:
        elapsed_hours = (self._tick * self._config.tick_interval_seconds) / 3600.0
        intensity = self._config.fire_intensity

        semi_major_km = self._config.wind_speed_kmh * elapsed_hours * intensity + 0.3
        semi_minor_km = semi_major_km * 0.45

        if self._crisis_id:
            crisis_store.patch(self._crisis_id, CrisisEventPatch(
                semi_major_km=semi_major_km,
                semi_minor_km=semi_minor_km,
                bearing_deg=self._config.wind_direction_deg,
            ))

    async def _persist_event(self) -> None:
        elapsed_min = self._tick * self._config.tick_interval_seconds / 60
        pm25 = _pm25_at_distance(0, self._tick * self._config.tick_interval_seconds, self._config)
        desc = (
            f"[SIM tick {self._tick}] Pożar przemysłowy Puławy — "
            f"czas: {elapsed_min:.0f}min, PM2.5 ~{pm25:.0f} µg/m³"
        )
        async with SessionLocal() as session:
            row = EventRow(
                latitude=self._config.source_lat,
                longitude=self._config.source_lon,
                category="fire",
                severity=_severity_for_tick(self._tick),
                status="active",
                description=desc,
                source="sensor",
                model="simulation",
            )
            session.add(row)
            await session.commit()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _pm25_at_distance(dist_km: float, elapsed_s: float, cfg: SimulationConfig) -> float:
    """Rough Gaussian plume — higher intensity / more time = higher readings."""
    base = 300.0 * cfg.fire_intensity * (1 + elapsed_s / 3600)
    decay = math.exp(-dist_km / (2.0 * cfg.fire_intensity))
    return max(base * decay, 5.0)


def _severity_for_tick(tick: int) -> str:
    if tick <= 3:
        return "medium"
    if tick <= 8:
        return "high"
    return "critical"


def _ellipse_polygon(
    center_lat: float, center_lon: float,
    semi_major_km: float, semi_minor_km: float,
    bearing_deg: float,
    n_points: int = 64,
) -> dict:
    """Build a GeoJSON Polygon approximating a rotated ellipse."""
    lat_per_km = 1.0 / 111.0
    lon_per_km = 1.0 / (111.0 * math.cos(math.radians(center_lat)))
    angle_rad = math.radians(90.0 - bearing_deg)  # convert bearing to math angle

    coords = []
    for i in range(n_points + 1):
        theta = 2 * math.pi * i / n_points
        ex = semi_major_km * math.cos(theta)
        ey = semi_minor_km * math.sin(theta)
        rx = ex * math.cos(angle_rad) - ey * math.sin(angle_rad)
        ry = ex * math.sin(angle_rad) + ey * math.cos(angle_rad)
        coords.append([
            center_lon + rx * lon_per_km,
            center_lat + ry * lat_per_km,
        ])

    return {"type": "Polygon", "coordinates": [coords]}
