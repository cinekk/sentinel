"""
Flood demo seed script (Phase 9).

Injects synthetic medical 112 events near at-risk hospitals,
sets hospital overrides (degraded generator, road cut),
and sets a Wisła gauge to alarm level.

Run: python scripts/seed_flood_demo.py [--base-url http://localhost:8000]
"""
from __future__ import annotations

import asyncio
import argparse
import random

import httpx

BASE = "http://localhost:8000"

# Medical events — clustered near Puławy-area hospitals that will be marked at_risk
MEDICAL_EVENTS = [
    # Near Puławy (flood-prone Wisła area)
    {"lat": 51.418, "lon": 21.972, "desc": "Wypadek drogowy — zatopiona droga, 2 poszkodowanych"},
    {"lat": 51.412, "lon": 21.965, "desc": "Nagłe zatrzymanie krążenia, utrudniony dojazd karetki"},
    {"lat": 51.425, "lon": 21.980, "desc": "Uraz kończyny podczas ewakuacji przed powodzią"},
    {"lat": 51.420, "lon": 21.958, "desc": "Hipotermia — 3 osoby z obszaru zalanego"},
    {"lat": 51.408, "lon": 21.970, "desc": "Wypadek z udziałem łodzi ewakuacyjnej"},
    {"lat": 51.435, "lon": 21.990, "desc": "Zasłabnięcie starszej osoby podczas ewakuacji"},
    {"lat": 51.400, "lon": 21.950, "desc": "Utonięcie — wyciągnięty z wody, resuscytacja w toku"},
    {"lat": 51.430, "lon": 21.985, "desc": "Zatrucie wodą powodziową — 4 osoby"},
    {"lat": 51.416, "lon": 21.975, "desc": "Złamanie — schody zalane, poślizgnięcie"},
    {"lat": 51.422, "lon": 21.963, "desc": "Atak astmy — wzrost wilgotności po powodzi"},
    {"lat": 51.410, "lon": 21.968, "desc": "Wypadek podczas prac ratowniczych"},
    {"lat": 51.438, "lon": 21.995, "desc": "Uraz głowy — ewakuacja łodzią w silnym prądzie"},
    # Dęblin area (Wisła/Wieprz confluence)
    {"lat": 51.572, "lon": 21.870, "desc": "Przesiąkanie wałów — evacuacja wsi, 5 rannych"},
    {"lat": 51.565, "lon": 21.860, "desc": "Wypadek podczas transportu sanitarnego"},
    {"lat": 51.580, "lon": 21.880, "desc": "Tonięcie w Wiśle — wyciągnięty, hipotermia"},
]

# Hospital overrides to apply
HOSPITAL_OVERRIDES = [
    # These IDs will be determined by looking up hospitals in Puławy/Dęblin
    # Using partial name match via assessment endpoint then override
    {"search_city": "Puławy",    "patch": {"generator_state": "degraded", "personnel_pct": 62}},
    {"search_city": "Dęblin",    "patch": {"generator_state": "offline",  "personnel_pct": 40, "road_cut": True}},
]

# Gauge override — set Wisła gauge near Puławy to alarm
# We'll find it by river name from the gauges layer
GAUGE_RIVER_TARGET = "Wisła"
GAUGE_ALERT_LEVEL  = "alarm"


async def seed(base: str) -> None:
    async with httpx.AsyncClient(base_url=base, timeout=30) as client:

        # 1. Inject medical 112 events
        print("Injecting medical events...")
        for evt in MEDICAL_EVENTS:
            jitter_lat = evt["lat"] + random.uniform(-0.005, 0.005)
            jitter_lon = evt["lon"] + random.uniform(-0.005, 0.005)
            r = await client.post("/api/ingest", json={
                "source": "radio",
                "payload": evt["desc"],
                "lat": jitter_lat,
                "lon": jitter_lon,
            })
            if r.status_code == 200:
                print(f"  ✓ {evt['desc'][:60]}")
            else:
                # Fallback: create event directly
                r2 = await client.post("/api/events", json={
                    "latitude": jitter_lat,
                    "longitude": jitter_lon,
                    "category": "medical",
                    "severity": "high",
                    "description": evt["desc"],
                    "source": "radio",
                    "status": "active",
                })
                if r2.status_code in (200, 201):
                    print(f"  ✓ (direct) {evt['desc'][:60]}")
                else:
                    print(f"  ✗ {r2.status_code}: {evt['desc'][:40]}")

        # 2. Set hospital overrides
        print("\nSetting hospital overrides...")
        assess_r = await client.get("/api/flood/assessment")
        if assess_r.status_code == 200:
            hospitals = assess_r.json()
            for override in HOSPITAL_OVERRIDES:
                city = override["search_city"].lower()
                matches = [h for h in hospitals if city in h["name"].lower()]
                if matches:
                    h = matches[0]
                    hid = h["hospital_id"]
                    r = await client.post(f"/api/hospitals/{hid}/override", json=override["patch"])
                    print(f"  ✓ {h['name']} → {override['patch']}")
                else:
                    print(f"  ✗ No hospital found matching city: {override['search_city']}")
        else:
            print(f"  ✗ Assessment endpoint error: {assess_r.status_code}")

        # 3. Set gauge override
        print("\nSetting gauge override (Wisła → alarm)...")
        gauges_r = await client.get("/api/layers/gauges/geojson")
        if gauges_r.status_code == 200:
            features = gauges_r.json().get("features", [])
            wisla_gauges = [
                f for f in features
                if GAUGE_RIVER_TARGET.lower() in (f.get("properties", {}).get("river") or "").lower()
            ]
            if wisla_gauges:
                # Pick the gauge closest to Puławy (lat=51.42, lon=21.97)
                def dist_pulawy(f: dict) -> float:
                    c = f["geometry"]["coordinates"]
                    return ((c[1] - 51.42) ** 2 + (c[0] - 21.97) ** 2) ** 0.5
                best = min(wisla_gauges, key=dist_pulawy)
                gid = best["properties"]["id"]
                r = await client.post(f"/api/gauges/{gid}/override", json={"alert_level": GAUGE_ALERT_LEVEL})
                print(f"  ✓ Gauge {best['properties']['station_name']} → alarm")
            else:
                print(f"  ✗ No Wisła gauges found in layer")
        else:
            print(f"  ✗ Gauges layer error: {gauges_r.status_code}")

        # 4. Verify assessment
        print("\nVerifying assessment...")
        r = await client.get("/api/flood/assessment")
        if r.status_code == 200:
            data = r.json()
            evac = [h for h in data if h["status"] == "evacuate"]
            risk = [h for h in data if h["status"] == "at_risk"]
            print(f"  Total hospitals: {len(data)}")
            print(f"  Evacuate: {len(evac)} — {[h['name'] for h in evac[:3]]}")
            print(f"  At risk:  {len(risk)} — {[h['name'] for h in risk[:3]]}")
        else:
            print(f"  ✗ Assessment error: {r.status_code}")

        print("\nDone. Refresh the SENTINEL frontend → Zestaw A tab.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=BASE)
    args = parser.parse_args()
    asyncio.run(seed(args.base_url))
