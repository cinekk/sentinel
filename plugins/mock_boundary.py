from datetime import datetime, timezone

from plugins.base import BasePlugin

# Simplified polygon for Lublin voivodeship boundary (WGS84)
# Key vertices approximating the administrative boundary
LUBLIN_VOIVODESHIP_COORDS = [
    [22.0031, 51.9847],
    [22.3500, 52.0500],
    [22.7000, 52.0800],
    [23.0500, 52.0300],
    [23.3000, 51.9500],
    [23.6000, 51.8500],
    [23.9000, 51.7000],
    [24.1500, 51.5000],
    [24.1000, 51.2000],
    [23.9000, 50.9500],
    [23.6500, 50.7000],
    [23.4000, 50.4500],
    [23.1000, 50.3500],
    [22.8000, 50.3000],
    [22.5000, 50.3500],
    [22.2000, 50.4500],
    [21.8500, 50.5500],
    [21.5000, 50.7500],
    [21.3000, 51.0000],
    [21.4000, 51.3000],
    [21.5500, 51.6000],
    [21.7000, 51.8500],
    [22.0031, 51.9847],
]

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
        features = [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [LUBLIN_VOIVODESHIP_COORDS],
                },
                "properties": {
                    "name": "Województwo Lubelskie",
                    "type": "voivodeship",
                },
            }
        ]
        for name, lon, lat in POWIATY:
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    "properties": {"name": name, "type": "powiat"},
                }
            )
        return {"type": "FeatureCollection", "features": features}


class MockEventsPlugin(BasePlugin):
    layer_id = "events"
    layer_name = "Crisis Events"
    data_type = "events"

    async def fetch(self) -> dict:
        self._last_updated = datetime.now(timezone.utc)
        # Phase 2: empty layer — events come from DB in Phase 3+
        return {"type": "FeatureCollection", "features": []}
