# Stage 1 — Sources

Stage 1 is where external data enters the system. Every data source — live APIs, static files, in-memory simulations, and derived computations — is wrapped in a plugin that extends `BasePlugin`. The plugin abstraction exists so that adding a new data source requires no changes to routing, caching, or the health endpoint: create a file in `plugins/`, implement `fetch()`, call `registry.register()` once in `main.py`. The output of each plugin is GeoJSON served by `GET /api/layers/{layer_id}/geojson` and consumed by the map frontend. Stage 2 (Observations) will add a second entry path — `poll()` — that writes time-series readings to a persistent table instead of discarding them after serving the HTTP response.

---

## BasePlugin interface

> **Current state:**

```python
class BasePlugin(ABC):
    layer_id: str        # unique identifier, used as the URL segment
    layer_name: str      # display name
    data_type: str       # e.g. "air_quality", "resources", "events", "threat_zone"

    @abstractmethod
    async def fetch(self) -> dict:
        """Return a GeoJSON FeatureCollection."""
        ...

    @property
    def last_updated(self) -> datetime | None:
        return self._last_updated
```

`fetch()` is called on every HTTP request to `/api/layers/{layer_id}/geojson`. Plugins that hit external APIs cache results internally (IMGW: 5 min, GIOŚ: 15 min, ISOK flood zones: 60 min). No data is persisted between requests.

> **Target design (not yet implemented):**

```python
class BasePlugin(ABC):
    layer_id: str
    layer_name: str
    data_type: str

    @abstractmethod
    async def fetch(self) -> dict:
        """Return a GeoJSON FeatureCollection. Called on HTTP request."""
        ...

    async def poll(self) -> None:
        """Called by APScheduler on a timer. Writes readings to the observations
        table (Stage 2) via data_writer.write_observation(). Default: no-op.
        Override only in data-source plugins (IMGW, GIOŚ). Computed plugins
        (HospitalStatusPlugin, TransportUnitsPlugin) do not need this."""
        pass
```

The distinction between the two methods:

| Method | Trigger | Output | Persisted? |
|--------|---------|--------|------------|
| `fetch()` | HTTP GET request | GeoJSON FeatureCollection | No — discarded after response |
| `poll()` | APScheduler (e.g. every 30 min) | rows in `observations` table | Yes — Stage 2 history |

---

## Current plugin inventory

All 13 plugins registered in `main.py` lifespan, in registration order:

| Plugin class | `layer_id` | Data source | Scope | Notes |
|---|---|---|---|---|
| `MockBoundaryPlugin` | `lublin_boundary` | Static GeoJSON file (`frontend/geojson/lublin_voivodeship.geojson`) + hardcoded powiat centroids | Lublin voivodeship | Boundary polygon + 24 powiat point markers |
| `EventsPlugin` | `events` | SQLite (`EventRow` table) | Lublin demo | Reads all classified incidents from DB; hackathon remnant |
| `FloodZonesPlugin` | `flood_zones` | Live WFS — ISOK/RZGW (`wody.isok.gov.pl`), 60-min cache | Lublin voivodeship (bbox filter) | Official statutory flood risk zones from MZPMRP |
| `SimulationPlugin` | `simulation` (varies) | In-memory state machine with background asyncio task | Puławy, Lublin demo | Industrial fire + PM2.5 plume; spreads on each tick; writes `EventRow` entries to DB |
| `HospitalsPlugin` | `hospitals` | SQLite (`HospitalRow` table, seeded from `seed_hospitals.py`) | Lublin voivodeship | Base hospital data — no flood status; used as reference layer |
| `SocialPlugin` | `social` | Static file (`data.json`) | Lublin voivodeship | Social care facilities (DPS); no live API |
| `SchoolsPlugin` | `schools` | Static file (`data.json`) | Lublin voivodeship | Schools; deduplication of co-located entries |
| `FireStationsPlugin` | `fire_stations` | Hardcoded Python list (15 entries) | Lublin voivodeship | PSP/OSP stations; not from any live API |
| `GIOSPlugin` | `gios` | Live API — GIOŚ v1 (`api.gios.gov.pl/pjp-api/v1/rest`), 15-min cache | **Hardcoded `"LUBELSKIE"`** | Air quality index; falls back to mock data on API failure |
| `IMGWHydroPlugin` | `imgw_hydro` | Live API — IMGW public hydro + river-statuses JSON, 5-min cache | **Hardcoded `"lubelskie"`** | River gauge levels + alert status (normal/warning/alarm); supports demo overrides |
| `HospitalStatusPlugin` | `hospitals-status` | Derived — calls `FloodAssessmentService` | Lublin voivodeship | Fuses IMGW gauges, ISOK zones, 112 call density; result is ephemeral, recomputed every request |
| `TransportUnitsPlugin` | `transport_units` | Derived — generated from `HospitalRow` DB via `generate_unit_pool()` | Lublin voivodeship | ZRM/transport unit pool positions; deterministic from hospital locations |
| `FloodScenarioPlugin` | `flood_scenario` | In-memory scripted state machine, controlled via `POST /api/flood-scenario/start\|stop\|reset` | Puławy/Dęblin, Lublin demo | Scripted flood arc; writes gauge overrides, hospital overrides, crisis events, and `EventRow` entries |

---

## Voivodeship config (needed fix)

Both live-data plugins have hardcoded voivodeship strings:

- `plugins/imgw_hydro.py` — `"lubelskie"` literal in `_fetch_all_stations()` station filter
- `plugins/gios.py` — `"LUBELSKIE"` literal in `_fetch_lubelskie_stations()`

The fix is two config vars in `config.py`:

```python
# config.py (pydantic-settings)
imgw_voivodeship: str = "lubelskie"
gios_voivodeship: str = "lubelskie"
```

Both plugins then read from `settings.imgw_voivodeship` / `settings.gios_voivodeship`. This is a prerequisite for WCZK deployment to any voivodeship other than Lubelskie. The fix is trivial — it just has not been done yet.

---

## How to add a new source plugin

1. Create `plugins/my_source.py`.
2. Extend `BasePlugin`, implement `fetch()`.
3. Add one line to `main.py` lifespan.

Minimal skeleton:

```python
# plugins/my_source.py
from datetime import datetime, timezone
import httpx
from plugins.base import BasePlugin

class MySourcePlugin(BasePlugin):
    layer_id = "my_source"
    layer_name = "My Source"
    data_type = "my_type"

    async def fetch(self) -> dict:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get("https://example.com/api/data")
        r.raise_for_status()
        raw = r.json()

        features = [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [item["lon"], item["lat"]]},
                "properties": {"name": item["name"], "value": item["value"]},
            }
            for item in raw["items"]
        ]
        self._last_updated = datetime.now(timezone.utc)
        return {"type": "FeatureCollection", "features": features}
```

```python
# main.py lifespan — add one line
from plugins.my_source import MySourcePlugin

registry.register(MySourcePlugin())
```

The plugin is immediately available at `GET /api/layers/my_source/geojson` and appears in `GET /api/health`.

---

## What poll() will look like

> **Target design (not yet implemented):** Stage 2 (DataWriter service + `observations` table) must exist before this is wired up.

Once `services/data_writer.py` is in place, `IMGWHydroPlugin.poll()` will look like this:

```python
# plugins/imgw_hydro.py
async def poll(self) -> None:
    """Called by APScheduler every 30 minutes. Persists gauge readings to
    the observations table so Stage 3 hooks can detect trends."""
    from services.data_writer import write_observation
    from config import settings

    stations = await _fetch_all_stations()
    for s in stations:
        await write_observation(
            station_id=s["id"],
            station_name=s["name"],
            source="imgw_hydro",
            metric="river_level_cm",
            value=s["level_cm"],
            metadata={"river": s["river"], "voivodeship": settings.imgw_voivodeship},
        )
        await write_observation(
            station_id=s["id"],
            station_name=s["name"],
            source="imgw_hydro",
            metric="alert_level",
            text_value=s["alert_level"],   # "normal" | "warning" | "alarm"
            metadata={"river": s["river"]},
        )
```

`write_observation()` inserts the row and then fires registered Stage 3 hooks (e.g. `TrendDetectorHook`) asynchronously. The `poll()` call itself does not block — hook failures are caught and logged by `HookRegistry._safe_call()`.

The APScheduler registration in `main.py` lifespan:

```python
scheduler.add_job(imgw_plugin.poll, "interval", minutes=30, id="imgw_poll")
```
