import json
from datetime import datetime, timezone
from pathlib import Path

from plugins.base import BasePlugin

_DATA_PATH = Path(__file__).parent.parent / "data.json"

# ~15 realistic PSP/OSP stations in Lublin voivodeship
_FIRE_STATIONS = [
    {"name": "JRG PSP Puławy", "lat": 51.4162, "lon": 21.9698, "unit": "PSP"},
    {"name": "KM PSP Lublin", "lat": 51.2490, "lon": 22.5665, "unit": "PSP"},
    {"name": "KM PSP Chełm", "lat": 51.1431, "lon": 23.4722, "unit": "PSP"},
    {"name": "KM PSP Zamość", "lat": 50.7231, "lon": 23.2519, "unit": "PSP"},
    {"name": "KP PSP Biała Podlaska", "lat": 52.0333, "lon": 23.1167, "unit": "PSP"},
    {"name": "KP PSP Hrubieszów", "lat": 50.8044, "lon": 23.8939, "unit": "PSP"},
    {"name": "KP PSP Biłgoraj", "lat": 50.5431, "lon": 22.7219, "unit": "PSP"},
    {"name": "KP PSP Kraśnik", "lat": 50.9167, "lon": 22.2167, "unit": "PSP"},
    {"name": "KP PSP Włodawa", "lat": 51.5500, "lon": 23.5333, "unit": "PSP"},
    {"name": "KP PSP Łuków", "lat": 51.9333, "lon": 22.3833, "unit": "PSP"},
    {"name": "KP PSP Radzyń Podlaski", "lat": 51.7833, "lon": 22.6167, "unit": "PSP"},
    {"name": "KP PSP Tomaszów Lubelski", "lat": 50.4500, "lon": 23.4167, "unit": "PSP"},
    {"name": "KP PSP Lubartów", "lat": 51.4667, "lon": 22.6167, "unit": "PSP"},
    {"name": "OSP Nałęczów", "lat": 51.2840, "lon": 22.2110, "unit": "OSP"},
    {"name": "OSP Kazimierz Dolny", "lat": 51.3180, "lon": 21.9470, "unit": "OSP"},
]


def _load_data() -> dict:
    with open(_DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


_DISPLAY_TYPES = {
    "hospital": "Szpital",
    "school": "Szkoła",
    "social": "DPS/Placówka",
    "fire_station": "Straż Pożarna",
}


def _make_feature(record: dict, resource_type: str, idx: int) -> dict:
    props = {k: v for k, v in record.items() if k not in ("lat", "lon")}
    props["type"] = resource_type
    props["id"] = f"{resource_type}_{idx}"
    props["display_type"] = _DISPLAY_TYPES.get(resource_type, resource_type)
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [record["lon"], record["lat"]],
        },
        "properties": props,
    }


class HospitalsPlugin(BasePlugin):
    layer_id = "hospitals"
    layer_name = "Szpitale"
    data_type = "resources"

    async def fetch(self) -> dict:
        self._last_updated = datetime.now(timezone.utc)
        data = _load_data()
        features = [
            _make_feature(r, "hospital", i)
            for i, r in enumerate(data["hospitals"])
        ]
        return {"type": "FeatureCollection", "features": features}


class SocialPlugin(BasePlugin):
    layer_id = "social"
    layer_name = "Placówki Społeczne (DPS)"
    data_type = "resources"

    async def fetch(self) -> dict:
        self._last_updated = datetime.now(timezone.utc)
        data = _load_data()
        features = [
            _make_feature(r, "social", i)
            for i, r in enumerate(data["social_facilities"])
        ]
        return {"type": "FeatureCollection", "features": features}


class SchoolsPlugin(BasePlugin):
    layer_id = "schools"
    layer_name = "Szkoły"
    data_type = "resources"

    async def fetch(self) -> dict:
        self._last_updated = datetime.now(timezone.utc)
        data = _load_data()
        features = [
            _make_feature(r, "school", i)
            for i, r in enumerate(data["schools"])
        ]
        return {"type": "FeatureCollection", "features": features}


class FireStationsPlugin(BasePlugin):
    layer_id = "fire_stations"
    layer_name = "Jednostki PSP/OSP"
    data_type = "resources"

    async def fetch(self) -> dict:
        self._last_updated = datetime.now(timezone.utc)
        features = [
            _make_feature(
                {"lat": s["lat"], "lon": s["lon"], "name": s["name"], "unit": s["unit"]},
                "fire_station",
                i,
            )
            for i, s in enumerate(_FIRE_STATIONS)
        ]
        return {"type": "FeatureCollection", "features": features}
