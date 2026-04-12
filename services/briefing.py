"""Template-based crisis briefing text generator.

Deterministic (no LLM) — numbers, names, distances come straight from API data.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from models import CrisisEvent
from services.spatial import haversine


@dataclass
class BriefingContext:
    active_crises: list[CrisisEvent] = field(default_factory=list)
    affected: list[dict] = field(default_factory=list)
    sim_state: dict | None = None
    flood_scenario_state: dict | None = None
    flood_hospitals: list[dict] = field(default_factory=list)
    air_quality: list[dict] = field(default_factory=list)
    weather: list[dict] = field(default_factory=list)


def _nearest_station(stations: list[dict], lat: float, lon: float) -> dict | None:
    if not stations:
        return None
    return min(stations, key=lambda s: haversine(lat, lon, s["lat"], s["lon"]))


def _count_by_type(affected: list[dict], facility_type: str) -> int:
    return sum(1 for f in affected if f.get("type") == facility_type)


def _count_evac(affected: list[dict]) -> int:
    return sum(1 for f in affected if f.get("action") == "EWAKUACJA")


def _nearest_evac(affected: list[dict]) -> dict | None:
    evac = [f for f in affected if f.get("action") == "EWAKUACJA"]
    if not evac:
        return None
    return min(evac, key=lambda f: f.get("distance_km", 999))


def generate_briefing_text(ctx: BriefingContext) -> str:
    now = datetime.now(ZoneInfo("Europe/Warsaw"))
    hh_mm = now.strftime("%H:%M")
    parts: list[str] = [f"Briefing sytuacyjny, godzina {hh_mm}."]

    if ctx.active_crises:
        for crisis in ctx.active_crises:
            parts.append(f"Aktywne zagrożenie: {crisis.name}.")
            parts.append(
                f"Lokalizacja: {crisis.lat:.2f} stopni północ, "
                f"{crisis.lon:.2f} stopni wschód."
            )
            parts.append(
                f"Strefa ewakuacji: {crisis.evac_radius_km:.0f} kilometrów. "
                f"Strefa ostrzeżenia: {crisis.warn_radius_km:.0f} kilometrów."
            )

            crisis_affected = [
                f for f in ctx.affected if f.get("crisis_id") == crisis.id
            ]
            total = len(crisis_affected)
            hospitals = _count_by_type(crisis_affected, "hospital")
            schools = _count_by_type(crisis_affected, "school")
            social = _count_by_type(crisis_affected, "social")

            if total:
                parts.append(
                    f"W strefie zagrożenia znajduje się {total} obiektów wrażliwych, "
                    f"w tym {hospitals} szpitali, {schools} szkół "
                    f"i {social} placówek opieki społecznej."
                )

            evac_count = _count_evac(crisis_affected)
            if evac_count:
                nearest = _nearest_evac(crisis_affected)
                evac_line = f"{evac_count} obiektów wymaga natychmiastowej ewakuacji."
                if nearest:
                    evac_line += (
                        f" Najbliższy: {nearest['name']}, "
                        f"{nearest['distance_km']:.1f} kilometrów od źródła."
                    )
                parts.append(evac_line)

            air = _nearest_station(ctx.air_quality, crisis.lat, crisis.lon)
            if air:
                parts.append(
                    f"Jakość powietrza w rejonie zagrożenia: "
                    f"PM2.5 {air['pm25']} mikrogramów na metr sześcienny. "
                    f"Norma: 25. Status: {air['status']}."
                )

            wx = _nearest_station(ctx.weather, crisis.lat, crisis.lon)
            if wx:
                parts.append(
                    f"Kierunek wiatru: {wx['wind_dir']}, "
                    f"prędkość {wx['wind_speed_kmh']} kilometrów na godzinę."
                )
    # Flood scenario section
    flood_running = (ctx.flood_scenario_state or {}).get("running", False)
    if flood_running:
        t_min = (ctx.flood_scenario_state or {}).get("narrative_time_min", 0)
        parts.append(
            f"Jednocześnie aktywna symulacja powodzi — "
            f"czas narracyjny plus {t_min:.0f} minut."
        )
        evacuate = [h for h in ctx.flood_hospitals if h.get("status") == "evacuate"]
        at_risk   = [h for h in ctx.flood_hospitals if h.get("status") == "at_risk"]
        if evacuate:
            names = ", ".join(h["name"] for h in evacuate[:3])
            parts.append(f"Szpitale wymagające natychmiastowej ewakuacji: {names}.")
        if at_risk:
            names = ", ".join(h["name"] for h in at_risk[:3])
            parts.append(f"Szpitale w podwyższonej gotowości: {names}.")
        if not evacuate and not at_risk:
            parts.append("Szpitale w regionie powodzi pozostają operacyjne.")

    if not ctx.active_crises and not flood_running:
        parts.append("Brak aktywnych zagrożeń. System monitoringu w trybie czuwania.")

    parts.append("Koniec briefingu.")
    return "\n\n".join(parts)
