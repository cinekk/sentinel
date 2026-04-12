"""
Attribute metadata catalog for all layers.

Each layer has a list of AttributeMeta entries that describe its properties:
human-friendly labels, types, descriptions, and whether they can serve as
a critical (color/size) attribute on the map.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AttributeMeta:
    key: str
    label: str
    type: str  # "string" | "int" | "float" | "bool"
    description: str = ""
    critical_candidate: bool = False


@dataclass
class LayerSchema:
    layer_id: str
    label: str
    description: str
    attributes: list[AttributeMeta] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "layer_id": self.layer_id,
            "label": self.label,
            "description": self.description,
            "attributes": [
                {
                    "key": a.key,
                    "label": a.label,
                    "type": a.type,
                    "description": a.description,
                    "critical_candidate": a.critical_candidate,
                }
                for a in self.attributes
            ],
        }

    @property
    def label_map(self) -> dict[str, str]:
        """key -> human-friendly label for popup rendering."""
        return {a.key: a.label for a in self.attributes}


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

_HOSPITAL_ATTRS = [
    AttributeMeta("name", "Nazwa", "string"),
    AttributeMeta("short_name", "Skrót nazwy", "string"),
    AttributeMeta("facility_id", "ID placówki", "string"),
    AttributeMeta("hospital_type", "Typ szpitala", "string"),
    AttributeMeta("operator", "Podmiot prowadzący", "string"),
    AttributeMeta("street", "Ulica", "string"),
    AttributeMeta("city", "Miasto", "string"),
    AttributeMeta("postal_code", "Kod pocztowy", "string"),
    AttributeMeta("gmina", "Gmina", "string"),
    AttributeMeta("powiat", "Powiat", "string"),
    AttributeMeta("nfz_contract", "Kontrakt NFZ", "bool"),
    AttributeMeta("has_sor", "Posiada SOR", "bool", "Szpitalny Oddział Ratunkowy"),
    AttributeMeta("has_pediatric_sor", "Pediatryczny SOR", "bool"),
    AttributeMeta("has_izba_przyjec", "Izba przyjęć", "bool"),
    AttributeMeta("sor_throughput_per_day", "Przepustowość SOR/dobę", "int",
                  "Szacowana liczba pacjentów na dobę", True),
    AttributeMeta("decontamination_entry", "Wejście dekontaminacyjne", "bool",
                  "Śluza do dekontaminacji CBRN"),
    AttributeMeta("isolation_rooms", "Izolatki", "int",
                  "Liczba pokoi izolacyjnych", True),
    AttributeMeta("negative_pressure_rooms", "Pokoje podciśnieniowe", "int", "", True),
    AttributeMeta("beds_total_physical", "Łóżka ogółem", "int",
                  "Całkowita liczba łóżek fizycznych", True),
    AttributeMeta("beds_available_estimate", "Dostępne łóżka (szacunek)", "int",
                  "Szacowana liczba wolnych łóżek", True),
    AttributeMeta("beds_occupied_pct", "Obłożenie łóżek (%)", "float",
                  "Procent zajętych łóżek", True),
    AttributeMeta("icu_oiom_beds", "Łóżka OIT/OIOM", "int",
                  "Oddział intensywnej terapii", True),
    AttributeMeta("ventilator_capable_beds", "Łóżka z respiratorem", "int", "", True),
    AttributeMeta("ecmo_available", "ECMO dostępne", "bool",
                  "Pozaustrojowe natlenianie membranowe"),
    AttributeMeta("dialysis_stations", "Stanowiska dializy", "int", "", True),
    AttributeMeta("burn_unit", "Oddział oparzeniowy", "bool"),
    AttributeMeta("neonatal_icu", "OIT neonatologiczny", "bool"),
    AttributeMeta("operating_rooms", "Sale operacyjne", "int", "", True),
    AttributeMeta("polytrauma_capable", "Politrauma", "bool",
                  "Zdolność do leczenia urazów wielonarządowych"),
    AttributeMeta("ct_24_7", "CT 24/7", "bool", "Tomografia komputerowa całodobowo"),
    AttributeMeta("mri_available", "MRI dostępne", "bool"),
    AttributeMeta("helipad", "Lądowisko", "bool", "Lądowisko dla helikopterów"),
    AttributeMeta("helipad_type", "Typ lądowiska", "string"),
    AttributeMeta("backup_power", "Zasilanie awaryjne", "bool"),
    AttributeMeta("backup_power_fuel_hours", "Zasilanie awaryjne (h)", "float",
                  "Czas pracy na zasilaniu awaryjnym", True),
    AttributeMeta("phone_24h_sor", "Telefon SOR 24h", "string"),
    AttributeMeta("email", "Email", "string"),
    AttributeMeta("specializations", "Specjalizacje", "string"),
    AttributeMeta("display_type", "Typ obiektu", "string"),
]

_SCHOOL_ATTRS = [
    AttributeMeta("name", "Nazwa", "string"),
    AttributeMeta("school_type", "Typ szkoły", "string"),
    AttributeMeta("operator", "Organ prowadzący", "string"),
    AttributeMeta("capacity", "Pojemność", "int", "Liczba uczniów", True),
    AttributeMeta("display_type", "Typ obiektu", "string"),
]

_SOCIAL_ATTRS = [
    AttributeMeta("name", "Nazwa", "string"),
    AttributeMeta("facility_type", "Typ placówki", "string"),
    AttributeMeta("operator", "Organ prowadzący", "string"),
    AttributeMeta("capacity", "Pojemność", "int", "Liczba miejsc", True),
    AttributeMeta("beds", "Łóżka", "int", "", True),
    AttributeMeta("display_type", "Typ obiektu", "string"),
]

_FIRE_STATION_ATTRS = [
    AttributeMeta("name", "Nazwa", "string"),
    AttributeMeta("unit", "Typ jednostki", "string", "PSP (państwowa) / OSP (ochotnicza)"),
    AttributeMeta("display_type", "Typ obiektu", "string"),
]

_AIR_QUALITY_ATTRS = [
    AttributeMeta("name", "Stacja", "string"),
    AttributeMeta("overall_index", "Indeks ogólny", "int",
                  "Wartość indeksu GIOŚ 0-5 (0=bardzo dobry, 5=bardzo zły)", True),
    AttributeMeta("overall_category", "Kategoria", "string"),
    AttributeMeta("pm25_index", "PM2.5 indeks", "int", "", True),
    AttributeMeta("pm25_category", "PM2.5 kategoria", "string"),
    AttributeMeta("pm10_index", "PM10 indeks", "int", "", True),
    AttributeMeta("pm10_category", "PM10 kategoria", "string"),
    AttributeMeta("so2_index", "SO2 indeks", "int", "", True),
    AttributeMeta("no2_index", "NO2 indeks", "int", "", True),
    AttributeMeta("o3_index", "O3 indeks", "int", "", True),
    AttributeMeta("critical_pollutant", "Zanieczyszczenie krytyczne", "string"),
    AttributeMeta("measurement_time", "Czas pomiaru", "string"),
    AttributeMeta("source", "Źródło danych", "string"),
]

_BOUNDARY_ATTRS = [
    AttributeMeta("name", "Nazwa", "string"),
]

_SIMULATION_ATTRS = [
    AttributeMeta("tick", "Krok symulacji", "int", "", True),
    AttributeMeta("semi_major_km", "Półoś duża (km)", "float",
                  "Zasięg strefy w kierunku wiatru", True),
    AttributeMeta("semi_minor_km", "Półoś mała (km)", "float",
                  "Zasięg strefy prostopadły do wiatru", True),
    AttributeMeta("bearing_deg", "Kierunek (°)", "float",
                  "Kierunek wiatru w stopniach"),
    AttributeMeta("elapsed_min", "Czas (min)", "float",
                  "Czas od rozpoczęcia symulacji", True),
    AttributeMeta("pm25", "PM2.5 (µg/m³)", "float",
                  "Stężenie pyłu PM2.5", True),
    AttributeMeta("pm10", "PM10 (µg/m³)", "float",
                  "Stężenie pyłu PM10", True),
    AttributeMeta("name", "Nazwa", "string"),
]

LAYER_SCHEMAS: dict[str, LayerSchema] = {
    "hospitals": LayerSchema(
        layer_id="hospitals",
        label="Szpitale",
        description="Szpitale i podmioty lecznicze z danymi o łóżkach, SOR, specjalizacjach i wyposażeniu kryzysowym",
        attributes=_HOSPITAL_ATTRS,
    ),
    "schools": LayerSchema(
        layer_id="schools",
        label="Szkoły",
        description="Szkoły i placówki oświatowe — lokalizacja, typ, pojemność",
        attributes=_SCHOOL_ATTRS,
    ),
    "social": LayerSchema(
        layer_id="social",
        label="Placówki Społeczne (DPS)",
        description="Domy Pomocy Społecznej i placówki opiekuńcze — miejsca, łóżka",
        attributes=_SOCIAL_ATTRS,
    ),
    "fire_stations": LayerSchema(
        layer_id="fire_stations",
        label="Jednostki PSP/OSP",
        description="Straż Pożarna — jednostki państwowe i ochotnicze",
        attributes=_FIRE_STATION_ATTRS,
    ),
    "lublin_boundary": LayerSchema(
        layer_id="lublin_boundary",
        label="Granica województwa",
        description="Granica woj. lubelskiego i centroidy powiatów",
        attributes=_BOUNDARY_ATTRS,
    ),
    "air_quality": LayerSchema(
        layer_id="air_quality",
        label="Jakość powietrza (GIOŚ)",
        description="Stacje GIOŚ — indeks jakości powietrza, PM2.5, PM10, SO2, NO2, O3",
        attributes=_AIR_QUALITY_ATTRS,
    ),
    "events": LayerSchema(
        layer_id="events",
        label="Zdarzenia kryzysowe",
        description="Bieżące zdarzenia kryzysowe z bazy danych",
        attributes=[],
    ),
    "simulation_threat": LayerSchema(
        layer_id="simulation_threat",
        label="Strefa zagrożenia (symulacja)",
        description="Symulowana strefa zagrożenia chemicznego — pluma, czujniki PM2.5/PM10",
        attributes=_SIMULATION_ATTRS,
    ),
    "transport_units": LayerSchema(
        layer_id="transport_units",
        label="Transport Sanitarny",
        description="Jednostki transportu sanitarnego (T/N/P/S) — lokalizacje i dostępność",
        attributes=[
            AttributeMeta("unit_type",       "Typ jednostki",  "string"),
            AttributeMeta("unit_type_label", "Nazwa typu",     "string"),
            AttributeMeta("status_label",    "Status",         "string"),
        ],
    ),
}


def get_schema(layer_id: str) -> LayerSchema | None:
    return LAYER_SCHEMAS.get(layer_id)


def get_all_schemas() -> list[LayerSchema]:
    return list(LAYER_SCHEMAS.values())


def get_label_map(layer_id: str) -> dict[str, str]:
    schema = LAYER_SCHEMAS.get(layer_id)
    return schema.label_map if schema else {}
