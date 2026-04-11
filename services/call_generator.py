"""
Synthetic 112 emergency call generator.

Writes EventRow records directly to the DB, tagged with source="simulation"
so they can be bulk-deleted after the demo.  The generator runs an async
tick loop (30 s per tick) and advances through 6 scenario phases that mirror
a flood crisis unfolding over ~6 hours.
"""
import asyncio
import random
from datetime import datetime, timezone

from database import EventRow, SessionLocal

# ---------------------------------------------------------------------------
# Flood-prone locations in Lublin voivodeship
# (lat, lon, area_name, phase_min)  — phase_min = first phase where used
# ---------------------------------------------------------------------------
_LOCATIONS: list[tuple[float, float, str, int]] = [
    (51.2465, 22.5684, "Lublin centrum",          0),
    (51.4000, 22.6000, "Lublin północ",            0),
    (51.0900, 22.4000, "Świdnik",                  0),
    (51.3833, 22.0000, "Puławy",                   1),
    (51.4158, 21.9698, "Puławy – nabrzeże Wisły",  1),
    (51.3200, 21.9500, "Kazimierz Dolny",          2),
    (51.5600, 21.8700, "Dęblin – ujście Wieprza",  2),
    (50.8900, 21.8400, "Annopol – prawy brzeg",    3),
    (51.1300, 23.4700, "Chełm niziny",             3),
    (51.1431, 23.4722, "Chełm miasto",             4),
    (51.5500, 23.5333, "Włodawa – Bug",            5),
    (50.8044, 23.8939, "Hrubieszów – Bug",         5),
]

# ---------------------------------------------------------------------------
# Call templates per phase
# ---------------------------------------------------------------------------
_PHASE_TEMPLATES: list[list[dict]] = [
    # Phase 0 — normal scattered calls
    [
        {"category": "medical",  "severity": "high",     "status": "active",
         "desc": "Zawał serca · ZRM {zrm} wysłany · czas dojazdu ~8 min"},
        {"category": "medical",  "severity": "medium",   "status": "active",
         "desc": "Uraz kończyny · ZRM {zrm} wysłany"},
        {"category": "medical",  "severity": "high",     "status": "active",
         "desc": "Udar mózgu · ZRM {zrm} wysłany"},
        {"category": "other",    "severity": "low",      "status": "resolved",
         "desc": "Incydent drogowy – drobny · ZRM {zrm} na miejscu"},
    ],
    # Phase 1 — first riverside calls
    [
        {"category": "medical",  "severity": "high",     "status": "active",
         "desc": "Zawał serca · drogi utrudnione · ZRM {zrm} wysłany"},
        {"category": "flood",    "severity": "medium",   "status": "active",
         "desc": "Podtopienie piwnicy · ewakuacja dobrowolna · ZRM {zrm} w drodze"},
        {"category": "medical",  "severity": "critical", "status": "active",
         "desc": "Utonięcie – wyciągnięty z wody · resuscytacja · ZRM {zrm}"},
    ],
    # Phase 2 — cluster near Puławy/Wisła, blocked roads
    [
        {"category": "medical",  "severity": "critical", "status": "active",
         "desc": "Zawał serca · drogi zablokowane · ZRM {zrm} objazdem ~25 min"},
        {"category": "medical",  "severity": "critical", "status": "active",
         "desc": "Hipotermia · osoba wyciągnięta z wody · ZRM {zrm}"},
        {"category": "flood",    "severity": "high",     "status": "active",
         "desc": "Osoba uwięziona w budynku · woda do 1p. · ZRM {zrm} + straż"},
        {"category": "medical",  "severity": "high",     "status": "active",
         "desc": "Udar · drogi częściowo zablokowane · ZRM {zrm}"},
    ],
    # Phase 3 — evacuation requests, dialysis/oxygen patients
    [
        {"category": "flood",    "severity": "critical", "status": "active",
         "desc": "Ewakuacja medyczna · pacjent dializowany · ZRM {zrm} + transport specj."},
        {"category": "flood",    "severity": "critical", "status": "active",
         "desc": "Ewakuacja medyczna · pacjent tlenowy · ZRM {zrm}"},
        {"category": "medical",  "severity": "critical", "status": "active",
         "desc": "Utonięcie · brak oddechu · ZRM {zrm} – droga zablokowana"},
        {"category": "flood",    "severity": "high",     "status": "active",
         "desc": "Dom starców – 12 osób niesamodzielnych · wniosek o ewakuację · ZRM {zrm}"},
    ],
    # Phase 4 — calls from hospital flood zone vicinity, ZRM slowing
    [
        {"category": "medical",  "severity": "critical", "status": "active",
         "desc": "Zawał · okolica zalanego szpitala · ZRM {zrm} – czas dojazdu nieznany"},
        {"category": "flood",    "severity": "critical", "status": "active",
         "desc": "Pacjent po operacji – wymaga transportu · szpital zalany · ZRM {zrm}"},
        {"category": "medical",  "severity": "high",     "status": "investigating",
         "desc": "Udar · zgłoszenie przyjęte · brak dostępnego ZRM w sektorze"},
        {"category": "flood",    "severity": "high",     "status": "active",
         "desc": "Ewakuacja szpitala pediatrycznego · ZRM {zrm} + autobus"},
    ],
    # Phase 5 — sectors Włodawa/Hrubieszów: no ZRM response
    [
        {"category": "medical",  "severity": "critical", "status": "investigating",
         "desc": "Zawał serca · zgłoszenie przyjęte · brak ZRM w sektorze – drogi odcięte"},
        {"category": "flood",    "severity": "critical", "status": "investigating",
         "desc": "Osoba uwięziona · woda powyżej okien · brak odpowiedzi ZRM"},
        {"category": "medical",  "severity": "critical", "status": "investigating",
         "desc": "Hipotermia · zgłoszenie przyjęte · sektor bez łączności z ZRM"},
        {"category": "flood",    "severity": "critical", "status": "investigating",
         "desc": "Ewakuacja niemożliwa · drogi odcięte · brak dostępnych służb"},
    ],
]

_ZRM_UNITS = [
    "ZRM-LBL-01", "ZRM-LBL-03", "ZRM-LBL-07",
    "ZRM-PUL-02", "ZRM-PUL-05",
    "ZRM-CHE-04", "ZRM-ZAM-06",
]


def _phase(tick: int) -> int:
    if tick < 4:
        return 0
    if tick < 8:
        return 1
    if tick < 12:
        return 2
    if tick < 16:
        return 3
    if tick < 20:
        return 4
    return 5


def _calls_for_tick(tick: int) -> list[EventRow]:
    phase = _phase(tick)
    templates = _PHASE_TEMPLATES[phase]
    locs = [l for l in _LOCATIONS if l[3] <= phase]

    count = random.randint(2, 4)
    rows: list[EventRow] = []
    for _ in range(count):
        tmpl = random.choice(templates)
        lat, lon, _area, _ = random.choice(locs)
        # jitter ±0.015° (~1.5 km)
        lat += random.uniform(-0.015, 0.015)
        lon += random.uniform(-0.015, 0.015)
        zrm = random.choice(_ZRM_UNITS) if tmpl["status"] == "active" else "–"
        rows.append(EventRow(
            time=datetime.now(timezone.utc),
            latitude=round(lat, 5),
            longitude=round(lon, 5),
            category=tmpl["category"],
            severity=tmpl["severity"],
            status=tmpl["status"],
            description=tmpl["desc"].format(zrm=zrm),
            source="simulation",
            model="112_sim",
        ))
    return rows


class CallGenerator:
    def __init__(self) -> None:
        self._running: bool = False
        self._paused: bool = False
        self._tick: int = 0
        self._task: asyncio.Task | None = None
        self._tick_interval: int = 30  # seconds

    # ── control ──────────────────────────────────────────────────────────────

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._paused = False
        self._tick = 0
        self._task = asyncio.create_task(self._loop())

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        if not self._running:
            self.start()
            return
        self._paused = False

    def reset(self) -> None:
        self._running = False
        self._paused = False
        if self._task:
            self._task.cancel()
            self._task = None
        self._tick = 0
        # DB cleanup scheduled as a fire-and-forget coroutine
        asyncio.create_task(self._delete_sim_events())

    @property
    def state(self) -> dict:
        return {
            "running": self._running,
            "paused": self._paused,
            "tick": self._tick,
            "phase": _phase(self._tick),
        }

    # ── internal ─────────────────────────────────────────────────────────────

    async def _loop(self) -> None:
        while self._running:
            await asyncio.sleep(self._tick_interval)
            if not self._running:
                break
            if self._paused:
                continue
            self._tick += 1
            rows = _calls_for_tick(self._tick)
            async with SessionLocal() as session:
                session.add_all(rows)
                await session.commit()

    @staticmethod
    async def _delete_sim_events() -> None:
        from sqlalchemy import delete as sa_delete
        async with SessionLocal() as session:
            await session.execute(
                sa_delete(EventRow).where(EventRow.source == "simulation")
            )
            await session.commit()


generator = CallGenerator()
