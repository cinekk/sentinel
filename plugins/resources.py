import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from database import HospitalRow, SessionLocal
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


_HOSPITAL_SKIP_COLS = {"id", "latitude", "longitude"}


def _hospital_row_to_dict(row: HospitalRow) -> dict:
    return {
        k: v for k, v in {
            "lat": row.latitude,
            "lon": row.longitude,
            "facility_id": row.facility_id,
            "name": row.name,
            "short_name": row.short_name,
            "hospital_type": row.type,
            "operator": row.operator,
            "nfz_contract": row.nfz_contract,
            "street": row.street,
            "city": row.city,
            "postal_code": row.postal_code,
            "gmina": row.gmina,
            "powiat": row.powiat,
            "has_sor": row.has_sor,
            "has_pediatric_sor": row.has_pediatric_sor,
            "has_izba_przyjec": row.has_izba_przyjec,
            "sor_throughput_per_day": row.sor_throughput_per_day,
            "decontamination_entry": row.decontamination_entry,
            "isolation_rooms": row.isolation_rooms,
            "negative_pressure_rooms": row.negative_pressure_rooms,
            "beds_total_physical": row.beds_total_physical,
            "beds_available_estimate": row.beds_available_estimate,
            "beds_occupied_pct": row.beds_occupied_pct,
            "icu_oiom_beds": row.icu_oiom_beds,
            "ventilator_capable_beds": row.ventilator_capable_beds,
            "ecmo_available": row.ecmo_available,
            "dialysis_stations": row.dialysis_stations,
            "burn_unit": row.burn_unit,
            "neonatal_icu": row.neonatal_icu,
            "operating_rooms": row.operating_rooms,
            "polytrauma_capable": row.polytrauma_capable,
            "ct_24_7": row.ct_24_7,
            "mri_available": row.mri_available,
            "helipad": row.helipad,
            "helipad_type": row.helipad_type,
            "backup_power": row.backup_power,
            "backup_power_fuel_hours": row.backup_power_fuel_hours,
            "phone_24h_sor": row.phone_24h_sor,
            "email": row.email,
            "specializations": row.specializations,
            "beds": row.beds_total_physical,
            "emergency": row.has_sor,
        }.items()
    }


class HospitalsPlugin(BasePlugin):
    layer_id = "hospitals"
    layer_name = "Szpitale"
    data_type = "resources"

    async def fetch(self) -> dict:
        self._last_updated = datetime.now(timezone.utc)
        async with SessionLocal() as session:
            result = await session.execute(select(HospitalRow))
            rows = result.scalars().all()
        features = [
            _make_feature(_hospital_row_to_dict(r), "hospital", i)
            for i, r in enumerate(rows)
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


_STATUS_COLOR = {
    "operational": "#22c55e",
    "at_risk": "#f59e0b",
    "evacuate": "#ef4444",
}
_STATUS_LABEL = {
    "operational": "Sprawny",
    "at_risk": "Zagrożony",
    "evacuate": "Ewakuacja",
}


class HospitalStatusPlugin(BasePlugin):
    """
    Hospital flood assessment layer.
    Calls FloodAssessmentService and returns color-coded GeoJSON markers.
    """
    layer_id = "hospitals-status"
    layer_name = "Szpitale — status powodziowy"
    data_type = "hospital_status"

    async def fetch(self) -> dict:
        from services.flood_assessment import assess_hospitals

        self._last_updated = datetime.now(timezone.utc)
        statuses = await assess_hospitals()

        features = []
        for s in statuses:
            color = _STATUS_COLOR.get(s.status, "#6b7280")
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [s.lon, s.lat]},
                "properties": {
                    "id": s.hospital_id,
                    "name": s.name,
                    "type": "hospital_status",
                    "status": s.status,
                    "status_label": _STATUS_LABEL.get(s.status, s.status),
                    "beds": s.beds,
                    "sor": s.sor,
                    "generator_state": s.generator_state,
                    "personnel_pct": s.personnel_pct,
                    "nearest_gauge": s.nearest_gauge,
                    "nearest_gauge_level": s.nearest_gauge_level,
                    "demand_112": s.demand_112,
                    "can_receive": s.can_receive,
                    "risk_factors": s.risk_factors,
                    "marker_color": color,
                },
            })

        return {"type": "FeatureCollection", "features": features}
