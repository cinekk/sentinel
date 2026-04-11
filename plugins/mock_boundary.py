import json
from datetime import datetime, timezone
from pathlib import Path

from plugins.base import BasePlugin

_BOUNDARY_PATH = Path(__file__).parent.parent / "frontend" / "geojson" / "lublin_voivodeship.geojson"

# Rough powiaty centroids for Lublin voivodeship (name, lon, lat)
POWIATY = [
    ("Lublin (miasto)", 22.5684, 51.2465),
    ("Biała Podlaska (miasto)", 23.1167, 52.0333),
    ("Chełm (miasto)", 23.4722, 51.1431),
    ("Zamość (miasto)", 23.2519, 50.7231),
    ("Bialski", 23.1167, 51.8000),
    ("Biłgorajski", 22.7219, 50.5431),
    ("Chełmski", 23.4722, 51.0000),
    ("Hrubieszowski", 23.8939, 50.8044),
    ("Janowski", 22.4000, 50.7200),
    ("Krasnostawski", 23.1733, 50.9833),
    ("Kraśnicki", 22.2167, 50.9167),
    ("Lubartowski", 22.6167, 51.4667),
    ("Lubelski", 22.5684, 51.0000),
    ("Łęczyński", 22.8833, 51.3000),
    ("Łukowski", 22.3833, 51.9333),
    ("Opolski", 22.0667, 51.1500),
    ("Parczewski", 22.9000, 51.6333),
    ("Puławski", 21.9698, 51.4158),
    ("Radzyński", 22.6167, 51.7833),
    ("Rycki", 21.9333, 51.5000),
    ("Świdnicki", 22.4333, 51.0500),
    ("Tomaszowski", 23.4167, 50.4500),
    ("Włodawski", 23.5333, 51.5500),
    ("Zamojski", 23.2519, 50.5500),
]


class MockBoundaryPlugin(BasePlugin):
    layer_id = "lublin_boundary"
    layer_name = "Lublin Voivodeship"
    data_type = "boundary"

    async def fetch(self) -> dict:
        self._last_updated = datetime.now(timezone.utc)
        fc = json.loads(_BOUNDARY_PATH.read_text(encoding="utf-8"))
        for name, lon, lat in POWIATY:
            fc["features"].append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    "properties": {"name": name, "type": "powiat"},
                }
            )
        return fc


def _event_to_feature(row: object) -> dict:
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [row.longitude, row.latitude],  # type: ignore[attr-defined]
        },
        "properties": {
            "type": "event",
            "id": row.id,  # type: ignore[attr-defined]
            "time": row.time.isoformat(),  # type: ignore[attr-defined]
            "category": row.category,  # type: ignore[attr-defined]
            "severity": row.severity,  # type: ignore[attr-defined]
            "status": row.status,  # type: ignore[attr-defined]
            "description": row.description,  # type: ignore[attr-defined]
            "source": row.source,  # type: ignore[attr-defined]
            "model": row.model,  # type: ignore[attr-defined]
        },
    }


class EventsPlugin(BasePlugin):
    layer_id = "events"
    layer_name = "Crisis Events"
    data_type = "events"

    async def fetch(self) -> dict:
        from sqlalchemy import select
        from database import EventRow, SessionLocal

        self._last_updated = datetime.now(timezone.utc)
        async with SessionLocal() as session:
            result = await session.execute(select(EventRow).order_by(EventRow.time.desc()))
            rows = result.scalars().all()
        return {
            "type": "FeatureCollection",
            "features": [_event_to_feature(r) for r in rows],
        }
