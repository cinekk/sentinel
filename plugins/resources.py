import json
from collections import defaultdict
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


def _is_school_umbrella_name(name: str) -> bool:
    """True if the name suggests an umbrella org (Zespół Szkół, Centrum Kształcenia, …)."""
    n = name.casefold()
    return (
        "zespół" in n
        or "zespol" in n
        or "centrum kształcenia" in n
        or "centrum ksztalcenia" in n
    )


def _pick_school_representative(entries: list[dict]) -> dict:
    for e in entries:
        if _is_school_umbrella_name(e.get("name", "")):
            return e
    return max(entries, key=lambda x: len(x.get("name", "")))


def _deduplicate_schools(schools: list[dict]) -> list[dict]:
    """Merge schools that share the same ~100 m grid cell into one record with sub_schools."""
    grid: dict[tuple[float, float], list[dict]] = defaultdict(list)
    for s in schools:
        key = (round(float(s["lat"]), 3), round(float(s["lon"]), 3))
        grid[key].append(s)

    result: list[dict] = []
    for entries in grid.values():
        if len(entries) == 1:
            result.append(entries[0])
            continue
        rep = _pick_school_representative(entries)
        avg_lat = sum(float(e["lat"]) for e in entries) / len(entries)
        avg_lon = sum(float(e["lon"]) for e in entries) / len(entries)
        subs = [
            {"name": e["name"], "school_type": e.get("school_type")}
            for e in entries
            if e is not rep
        ]
        merged = {
            **rep,
            "lat": avg_lat,
            "lon": avg_lon,
            "sub_schools": subs,
            "sub_count": len(subs),
        }
        result.append(merged)
    return result


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
        deduped = _deduplicate_schools(data["schools"])
        features = [
            _make_feature(r, "school", i)
            for i, r in enumerate(deduped)
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


_BASE_HOSPITAL_FIELDS = (
    "short_name", "hospital_type", "operator", "nfz_contract",
    "street", "city", "postal_code",
    "has_sor", "has_izba_przyjec", "sor_throughput_per_day",
    "beds_total_physical", "icu_oiom_beds", "operating_rooms",
    "ct_24_7", "helipad", "backup_power", "backup_power_fuel_hours",
    "phone_24h_sor", "specializations",
)


class HospitalStatusPlugin(BasePlugin):
    """
    Hospital flood assessment layer.
    Calls FloodAssessmentService and returns color-coded GeoJSON markers
    enriched with base hospital detail so the popup contains everything.
    """
    layer_id = "hospitals-status"
    layer_name = "Szpitale — status powodziowy"
    data_type = "hospital_status"

    async def fetch(self) -> dict:
        from services.flood_assessment import assess_hospitals
        from services.transfer import get_transfer_recommendations
        from sqlalchemy import select

        self._last_updated = datetime.now(timezone.utc)
        statuses = await assess_hospitals()

        # Load base hospital rows for enrichment
        async with SessionLocal() as session:
            result = await session.execute(select(HospitalRow))
            rows = result.scalars().all()
        row_by_id: dict = {(r.facility_id or str(r.id)): r for r in rows}

        # Build transfer_targets lookup: hospital_id → list of short names
        recommendations = await get_transfer_recommendations()
        transfer_by_id: dict = {
            rec.from_hospital_id: [t.short_name for t in rec.targets]
            for rec in recommendations
        }

        features = []
        for s in statuses:
            color = _STATUS_COLOR.get(s.status, "#6b7280")
            row = row_by_id.get(s.hospital_id)

            props: dict = {
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
                "transfer_targets": transfer_by_id.get(s.hospital_id, []),
            }

            # Enrich with base hospital fields when available
            if row:
                for field in _BASE_HOSPITAL_FIELDS:
                    value = getattr(row, field, None)
                    if value is not None:
                        props[field] = value

            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [s.lon, s.lat]},
                "properties": props,
            })

        return {"type": "FeatureCollection", "features": features}


_UNIT_TYPE_LABELS = {
    "S": "Specjalistyczny ZRM",
    "N": "Neonatologiczny",
    "P": "Podstawowy ZRM",
    "T": "Transport sanitarny",
}

_UNIT_TYPE_COLORS = {
    "S": "#ef4444",
    "N": "#a855f7",
    "P": "#f59e0b",
    "T": "#6e92b4",
}


class TransportUnitsPlugin(BasePlugin):
    """
    Map layer showing all available transport sanitarny units
    (T / N / P / S) generated from hospital base locations.
    Uses the same deterministic pool as the evacuation dispatch service.
    """
    layer_id = "transport_units"
    layer_name = "Transport Sanitarny"
    data_type = "resources"

    async def fetch(self) -> dict:
        from services.evacuation import generate_unit_pool

        async with SessionLocal() as session:
            result = await session.execute(select(HospitalRow))
            rows = result.scalars().all()

        bases = [
            {"lat": r.latitude, "lon": r.longitude, "sor": bool(r.has_sor)}
            for r in rows
        ]
        pool = generate_unit_pool(bases)

        features = []
        for u in pool:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [u["lon"], u["lat"]]},
                "properties": {
                    "id": u["unit_id"],
                    "name": u["call_sign"],
                    "type": "transport_unit",
                    "unit_type": u["unit_type"],
                    "unit_type_label": _UNIT_TYPE_LABELS.get(u["unit_type"], u["unit_type"]),
                    "status": u["status"],
                    "status_label": "Dostępna" if u["status"] == "available" else "Niedostępna",
                    "color": _UNIT_TYPE_COLORS.get(u["unit_type"], "#6e92b4"),
                },
            })

        return {"type": "FeatureCollection", "features": features}
