# Briefing głosowy — ElevenLabs TTS z synchronizowaną transkrypcją

**Version:** 1.0  
**Date:** 2026-04-12  
**Status:** Plan  
**Side quest:** ElevenLabs  
**Bonus:** +10 pkt za voice assistant

---

## 1. Problem

Jury ocenia zdeployowane rozwiązanie pod linkiem — nie ma gwarancji że mają włączone głośniki. Czysty TTS (audio-only) jest ryzykowny: jeśli jury nie słyszy, feature jest niewidoczny.

Potrzebujemy rozwiązania które działa **wizualnie** (transkrypcja live) i **dźwiękowo** (audio TTS) jednocześnie. Jury z głośnikiem dostaje pełne doświadczenie; jury bez głośnika widzi animowaną transkrypcję i rozumie co system robi.

---

## 2. Koncept: Karaoke Briefing

Operator klika przycisk "📢 Briefing sytuacyjny" w UI. System:

1. Generuje tekst briefingu na podstawie aktualnego stanu kryzysu
2. Wysyła tekst do ElevenLabs TTS z `with-timestamps`
3. Otrzymuje audio + timestampy per-character
4. Agreguje timestampy do słów
5. Frontend odtwarza audio i jednocześnie podświetla słowa w synchronizacji

**Efekt:** Tekst pojawia się słowo po słowie, zsynchronizowany z audio. Jak teleprompter / karaoke.

---

## 3. ElevenLabs API — endpoint z timestampami

### Request

```
POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps
Content-Type: application/json
xi-api-key: {ELEVENLABS_API_KEY}

{
  "text": "Uwaga. Strefa zagrożenia objęła trzy placówki...",
  "model_id": "eleven_multilingual_v2",
  "voice_settings": {
    "stability": 0.7,
    "similarity_boost": 0.8
  },
  "output_format": "mp3_44100_128"
}
```

### Response

```json
{
  "audio_base64": "//uQx...",
  "alignment": {
    "characters": ["U", "w", "a", "g", "a", ".", " ", "S", "t", "r", ...],
    "character_start_times_seconds": [0.0, 0.08, 0.12, 0.18, 0.24, 0.30, 0.35, 0.40, ...],
    "character_end_times_seconds":   [0.08, 0.12, 0.18, 0.24, 0.30, 0.35, 0.40, 0.48, ...]
  }
}
```

Timestampy są **per-character**. Agregacja do słów: łączymy znaki do spacji/interpunkcji, bierzemy `start` pierwszego znaku i `end` ostatniego.

### Wybór głosu

Rekomendacja: głos z kategorii "News" lub "Narration" — autorytatywny, spokojny, wyraźna dykcja. Model `eleven_multilingual_v2` obsługuje polski. Konkretny `voice_id` do wybrania z biblioteki ElevenLabs (np. "Antoni" lub custom voice).

Alternatywa: `eleven_turbo_v2_5` — szybszy (niższa latencja), ale potencjalnie gorsza jakość polskiego.

---

## 4. Architektura

### Nowe komponenty

```
services/tts.py           — Wrapper ElevenLabs: synthesize_with_timestamps(text) → {audio, words}
services/briefing.py      — Generuje tekst briefingu z aktualnego stanu kryzysu
routers/voice.py          — POST /api/voice/briefing → audio + synchronized words
frontend/app.js           — Karaoke player: Audio + synchronized word highlighting
```

### Przepływ danych

```
[Operator klika "Briefing"]
        │
        ▼
[Frontend] POST /api/voice/briefing
        │
        ▼
[routers/voice.py]
        │
        ├── 1. Pobierz stan kryzysu ──► GET /api/simulation/state
        │                               GET /api/v1/crisis/affected
        │                               GET /api/v1/crisis/state
        │
        ├── 2. Wygeneruj tekst ──► services/briefing.py
        │      (template-based, NIE LLM — deterministic + szybki)
        │
        ├── 3. TTS + timestamps ──► services/tts.py ──► ElevenLabs API
        │
        └── 4. Agreguj words ──► [{word, start, end}, ...]
        │
        ▼
[Response JSON]
{
  "audio_base64": "...",
  "words": [
    {"word": "Uwaga.", "start": 0.0, "end": 0.35},
    {"word": "Strefa", "start": 0.40, "end": 0.72},
    {"word": "zagrożenia", "start": 0.75, "end": 1.21},
    ...
  ],
  "text": "Uwaga. Strefa zagrożenia...",
  "duration_seconds": 28.5
}
```

### Dlaczego template zamiast LLM do tekstu briefingu?

Tekst alertu kryzysowego MUSI być deterministyczny — nie może halucynować liczb, nazw placówek, odległości. Template z parametrami z API jest szybszy (~0ms vs ~3s LLM) i wiarygodniejszy. LLM (Qwen3) zostaje przy zarządzaniu widokiem (Faza A) — jego siła.

---

## 5. Format tekstu briefingu

### Template (polski, formalny, zwięzły)

```
Briefing sytuacyjny, godzina {time}.

{if active_fires > 0}
Aktywne zagrożenie: {fire_name}.
Lokalizacja: {lat}°N, {lon}°E.
Strefa ewakuacji: {evac_radius} kilometrów. Strefa ostrzeżenia: {warn_radius} kilometrów.

W strefie zagrożenia znajduje się {affected_count} obiektów wrażliwych,
w tym {hospitals_count} szpitali, {schools_count} szkół i {dps_count} placówek opieki społecznej.

{if evac_count > 0}
{evac_count} obiektów wymaga natychmiastowej ewakuacji.
Najbliższy: {nearest_evac_name}, {nearest_evac_distance} kilometrów od źródła.
{endif}

Jakość powietrza w rejonie zagrożenia: PM2.5 {pm25} mikrogramów na metr sześcienny.
Norma: 25. Status: {air_status}.

Kierunek wiatru: {wind_dir}, prędkość {wind_speed} kilometrów na godzinę.
{else}
Brak aktywnych zagrożeń. System monitoringu w trybie czuwania.
Województwo lubelskie: {total_hospitals} szpitali, {total_schools} szkół,
{total_dps} placówek opieki społecznej pod monitoringiem.
{endif}

Koniec briefingu.
```

**Szacowany czas audio:** 20-35 sekund (przy normalnym tempie mowy).  
**Szacowany koszt ElevenLabs:** ~0.01-0.02 USD per briefing (multilingual v2).

---

## 6. Frontend — Karaoke Player

### Komponent UI

```
┌─────────────────────────────────────────────────────────┐
│  📢 BRIEFING SYTUACYJNY                    ▶ Play  ⏸   │
│─────────────────────────────────────────────────────────│
│                                                         │
│  Briefing sytuacyjny, godzina czternasta trzydzieści.   │
│                                                         │
│  Aktywne zagrożenie: ███████████████████████████████    │
│  ██████████████████. Lokalizacja: pięćdziesiąt jeden    │
│  stopni północ, dwadzieścia dwa stopnie wschód.         │
│                                                         │
│  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │
│                                                         │
│  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░  12.4s / 28.5s      │
└─────────────────────────────────────────────────────────┘

█ = wypowiedziane słowo (podświetlone, np. amber/gold)
░ = słowo jeszcze nie wypowiedziane (przyciemnione)
▓ = pasek postępu audio
```

### Mechanizm synchronizacji (JS)

```javascript
// Pseudokod — główna pętla synchronizacji
const audio = new Audio(`data:audio/mpeg;base64,${response.audio_base64}`);
const words = response.words; // [{word, start, end}, ...]

audio.play();

function sync() {
  const t = audio.currentTime;
  words.forEach((w, i) => {
    const el = wordElements[i];
    if (t >= w.start && t <= w.end) {
      el.classList.add('speaking');    // aktualnie mówione — pulsujące podświetlenie
    } else if (t > w.end) {
      el.classList.add('spoken');      // już powiedziane — pełna jasność
      el.classList.remove('speaking');
    } else {
      el.classList.remove('spoken', 'speaking'); // jeszcze nie — przyciemnione
    }
  });
  if (!audio.paused) requestAnimationFrame(sync);
}

audio.addEventListener('play', sync);
```

### Stylizacja (pasująca do ops-center aesthetic)

```css
.briefing-word          { color: rgba(255,255,255,0.3); transition: color 0.15s; }
.briefing-word.spoken   { color: rgba(255,255,255,0.9); }
.briefing-word.speaking { color: #f59e0b; text-shadow: 0 0 8px rgba(245,158,11,0.5); }
```

Kolory spójne z design tokens z `style.css` (amber = `--clr-accent`).

---

## 7. Integracja z istniejącym systemem

### Źródła danych do briefingu

| Dane | Źródło w Sentinel | Endpoint |
|------|-------------------|----------|
| Aktywne pożary/zagrożenia | SimulationPlugin state | `GET /api/simulation/state` |
| Zagrożone obiekty | CrisisStore / spatial.py | `GET /api/v1/crisis/affected` |
| Liczba obiektów per typ | ResourcePlugins | `GET /api/resources?type=...` |
| Jakość powietrza | GIOŚ plugin (Phase 5) lub mock | `GET /api/layers/air_quality/data` |
| Pogoda/wiatr | SimulationConfig lub IMGW | `GET /api/simulation/state` → config |

### Gdzie w UI?

Dwie opcje:

**A) Przycisk w panelu czatu AI (rekomendowane)**  
Obok inputa czatu, przycisk "📢 Briefing". Tekst i audio pojawiają się w oknie czatu jako wiadomość systemu. Spójne z istniejącym UX czatu AI.

**B) Osobna sekcja w sidebar**  
Dedykowany panel "Voice Briefing" pod czatem. Bardziej widoczny, ale dodaje kolejny element do i tak zatłoczonego sidebara.

---

## 8. Estymacja pracochłonności

| Komponent | Szacunek | Trudność |
|-----------|----------|----------|
| `services/tts.py` (ElevenLabs wrapper + word aggregation) | 60 linii | Niska |
| `services/briefing.py` (template + dane z API) | 80 linii | Niska |
| `routers/voice.py` (endpoint) | 40 linii | Niska |
| Frontend: karaoke player JS | 80 linii | Średnia |
| Frontend: CSS styling | 30 linii | Niska |
| Frontend: integracja z chat panelem | 20 linii | Niska |
| **Łącznie** | **~310 linii** | **~2-3h** |

### Zależności

- `ELEVENLABS_API_KEY` w `.env` (już jest w `.env.example`)
- Żadne nowe pakiety pip (ElevenLabs API przez istniejący `httpx`)
- Voice ID do wybrania z biblioteki ElevenLabs

### Ryzyka

| Ryzyko | Mitygacja |
|--------|-----------|
| Latencja ElevenLabs (>5s) | Spinner "Generowanie briefingu..." + cache briefingu jeśli stan się nie zmienił |
| Słaba jakość polskiego TTS | Test z 2-3 głosami, wybór najlepszego. Multilingual v2 radzi sobie dobrze z polskim |
| Autoplay zablokowany przez przeglądarkę | Przycisk Play wymaga kliknięcia (user gesture) — to załatwia autoplay policy |
| Jury nie widzi feature'u | Briefing widget widoczny domyślnie w sidebar — nawet bez kliknięcia widać że istnieje |

---

## 9. Rozszerzenia (jeśli starczy czasu)

### 9a. Voice Command (STT → action)

Odwrotny flow: operator mówi do mikrofonu → ElevenLabs STT → transkrypcja → Qwen3 parsuje intent → wykonanie + TTS odpowiedź. Wymaga `POST /api/voice/command` + nagrywanie audio w przeglądarce (`MediaRecorder`). Estymacja: +2-3h.

### 9b. Briefing automatyczny przy eskalacji

Gdy `spatial.check_intersections()` wykryje nowy obiekt w strefie zagrożenia → automatycznie generuj i wyświetl briefing. Nie wymaga kliknięcia. Estymacja: +30 min (event listener w frontend).

### 9c. Koncepcja: Broadcasting telefoniczny

Endpoint `POST /api/voice/broadcast` generuje audio per-placówka (spersonalizowane: "Placówko X, zalecana ewakuacja") + listę numerów. Na demo: pokazujemy wygenerowane audio + listę odbiorców, bez faktycznego dzwonienia. Narracja: "W produkcji podpięlibyśmy bramę telefoniczną Twilio/SMSAPI." Estymacja: +1h (generowanie listy + audio per-obiekt).

---

## 10. Metryki sukcesu

| Metryka | Target |
|---------|--------|
| Czas od kliknięcia "Briefing" do początku audio | < 5 sekund |
| Synchronizacja transkrypcji z audio | ± 100ms (niezauważalne) |
| Czytelność transkrypcji bez audio | 100% — pełny tekst widoczny |
| Koszt per briefing | < $0.05 |
