# Phase 13 — Auto-Demo / Cinematic Tour

## Problem statement

The app will be evaluated by judges without a live presenter.
A static UI with no running simulation communicates nothing.

The goal: judges open the link → the app introduces itself, starts the flood simulation,
narrates what is happening via TTS, and highlights key panels — all without any clicks.
It should feel like a crisis unfolding in real time, not a product walkthrough.

---

## Demo sequence

Total runtime: ~90 seconds.

| # | Delay | Action | TTS? |
|---|-------|--------|------|
| 0 | `t=0` | Page loads normally; after 3 s show countdown overlay | — |
| 1 | `t=3` | Countdown overlay: "Demo uruchomi się za 8 s… [Pomiń]" | — |
| 2 | `t=11` | **Fire**: overlay fades; TTS fires alert #1 | ✅ |
| 3 | `t=13` | Switch to **Powódź** tab automatically | — |
| 4 | `t=14` | POST `/api/flood/simulation/start` | — |
| 5 | `t=16` | Map pans + zooms to Lublin (flood origin area) | — |
| 6 | `t=18` | Callout appears on **gauges panel**: explains water levels | — |
| 7 | `t=26` | Callout moves to **hospital status table**: TTS alert #2 | ✅ |
| 8 | `t=34` | Callout moves to **transfer map lines** | — |
| 9 | `t=42` | Switch to **Ewakuacja** sub-tab; callout on dispatch panel; TTS alert #3 | ✅ |
| 10 | `t=52` | All callouts fade; overlay: "Eksploruj samodzielnie" + skip button gone | — |

"Pomiń demo" button available throughout steps 1–9.

---

## TTS scripts (Polish, ElevenLabs)

**Alert #1** — triggers at step 2, before tab switch:
> *„Uwaga! Poziom wody na Wieprzu przekroczył stan alarmowy. Uruchamiam procedurę
> monitorowania zagrożenia powodziowego w województwie lubelskim."*

**Alert #2** — triggers at step 7, when hospital table callout appears:
> *„Wykryto krytyczne zagrożenie. Szpital Jana Bożego w Lublinie wymaga natychmiastowej
> ewakuacji. Dostępne łóżka: niewystarczające. Zalecam uruchomienie transportu sanitarnego."*

**Alert #3** — triggers at step 9, on evacuation panel:
> *„Inicjuję protokół ewakuacji medycznej. Przydział jednostek: dwanaście zespołów
> specjalistycznych, dziewięćdziesiąt podstawowych. Oczekiwany czas ewakuacji: czterdzieści
> pięć minut."*

---

## Backend changes

### `routers/tts.py` — new endpoint (or extend `routers/voice.py`)

```
POST /api/tts/speak
Body: { "text": "...", "voice_id": "optional" }
Returns: audio/mpeg stream  OR  { "audio_b64": "..." }
```

Uses existing `services/tts.py` (`ElevenLabsTTSService`).
If ElevenLabs key is absent → returns 204 (frontend silently skips audio).

This endpoint already exists in spirit via `voice.py` — wire it or add a lightweight
`/api/tts/speak` alias that accepts plain text and streams back MP3.

---

## Frontend changes

### Demo controller (`frontend/app.js`)

**`DemoController`** — self-contained object:

```js
const DemoController = {
  _step: 0,
  _skipped: false,
  _timers: [],

  start() { … },
  skip()  { this._skipped = true; this._clearTimers(); this._hideAll(); },

  async _speak(text) {
    try {
      const res = await fetch(`${API}/api/tts/speak`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });
      if (!res.ok) return;
      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.play();
    } catch { /* silent — demo continues without audio */ }
  },

  _showCallout(targetSelector, text, position) { … },
  _hideCallout() { … },
  _clearTimers() { this._timers.forEach(clearTimeout); this._timers = []; },
  _hideAll() { /* hide overlay, callout */ },
};
```

Auto-trigger on page load:
```js
// Wait 3s after DOM ready, then show countdown
window.addEventListener('load', () => {
  // Check ?nodemo query param to allow disabling (for dev)
  if (new URLSearchParams(location.search).has('nodemo')) return;
  setTimeout(() => DemoController.showCountdown(), 3000);
});
```

Also exposed as `window._sentinel_demo = DemoController` for manual trigger from console.

### Countdown overlay (`frontend/index.html`)

```html
<div id="demo-countdown-overlay" class="demo-overlay" style="display:none">
  <div class="demo-countdown-panel">
    <div class="demo-countdown-title">⚡ SENTINEL — Demo sytuacji kryzysowej</div>
    <div class="demo-countdown-subtitle">Automatyczna demonstracja uruchomi się za</div>
    <div class="demo-countdown-number" id="demo-countdown-num">8</div>
    <button id="demo-skip-btn" class="sim-btn">Pomiń demo</button>
  </div>
</div>
```

### Callout tooltip (`frontend/index.html`)

```html
<div id="demo-callout" class="demo-callout" style="display:none">
  <div class="demo-callout-arrow"></div>
  <div class="demo-callout-text" id="demo-callout-text"></div>
</div>
```

Callout is absolutely positioned; `_showCallout()` reads `targetEl.getBoundingClientRect()`
and places the callout to the left or right depending on available space.
Target element gets a temporary `.demo-highlight` ring (CSS `outline` pulse animation).

### `frontend/style.css`

```css
/* Countdown overlay */
.demo-overlay { position:fixed; inset:0; z-index:10000; background:rgba(0,0,0,.7);
                display:flex; align-items:center; justify-content:center; }
.demo-countdown-panel { … dark card, centered … }
.demo-countdown-number { font-size:4rem; font-family:var(--font-mono); color:var(--amber); }

/* Callout */
.demo-callout { position:fixed; z-index:9999; max-width:260px;
                background:var(--bg-card); border:1px solid var(--amber);
                border-radius:6px; padding:10px 14px; box-shadow:0 8px 32px rgba(0,0,0,.6); }
.demo-callout-text { font-size:.75rem; color:var(--text-hi); line-height:1.5; }
.demo-callout-arrow { … CSS triangle pointing at target … }

/* Highlight ring on demo target element */
@keyframes demo-ring { 0%,100%{outline-color:rgba(245,158,11,.4)} 50%{outline-color:var(--amber)} }
.demo-highlight { outline:2px solid var(--amber); outline-offset:4px;
                  animation:demo-ring 1.2s ease infinite; border-radius:4px; }
```

---

## Callout texts (Polish)

| Step | Target | Text |
|------|--------|------|
| gauges panel | `#flood-gauges` | *„Czujniki IMGW — poziomy wód rzecznych w czasie rzeczywistym. Kolor czerwony = przekroczony stan alarmowy."* |
| hospital table | `#flood-hospital-table` | *„Status szpitali po zestawieniu z zasięgiem powodzi. Ikona ▲ = ewakuacja wymagana."* |
| transfer lines | `#map` | *„Trasy rekomendowanego przekierowania pacjentów — wygenerowane automatycznie na podstawie pojemności łóżkowej."* |
| evac panel | `#flood-evac-list` | *„Panel dowodzenia ewakuacją — przydział jednostek transportu sanitarnego (S/P/N/T) do każdego szpitala."* |

---

## URL parameter

`?nodemo` — disables auto-start entirely (for development and manual demos).
`?demo` — forces immediate start (skip the 3 s idle wait; useful for manual trigger).

---

## Implementation order

1. `routers/tts.py` (or extend `voice.py`) — `POST /api/tts/speak` endpoint
2. `frontend/index.html` — countdown overlay + callout elements
3. `frontend/style.css` — demo overlay, callout, highlight ring animations
4. `frontend/app.js` — `DemoController` object + auto-trigger on load

## Files touched

```
routers/tts.py          NEW (or voice.py extended) — POST /api/tts/speak
frontend/index.html     countdown overlay + callout DOM
frontend/style.css      demo overlay, callout, highlight ring
frontend/app.js         DemoController, auto-trigger, _speak(), _showCallout()
```

## Observable output (done criteria)

- Page loads → 3 s → countdown overlay appears with 8 s timer.
- Countdown hits 0 → overlay fades → TTS plays alert #1 → Powódź tab activates.
- Flood simulation starts automatically; map pans to Lublin area.
- Callouts appear and auto-advance highlighting gauges → hospital table → evac panel.
- TTS plays at steps 7 and 9.
- "Pomiń demo" cancels at any point and leaves the app in normal interactive state.
- `?nodemo` URL param suppresses auto-start.
