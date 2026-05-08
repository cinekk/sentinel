# Sentinel — UI Design Decisions

> Design reasoning for Stage 4 output plugins. Not a wireframe spec — the reasoning behind key layout and architecture choices.

---

## 1. Design Principles

Six decision rules for all Stage 4 UI work. When debating a feature or layout choice, apply these first.

1. **Resources, not threats.** Every KPI measures availability, not severity. "Available ZRM: 8/12" — not "active fires: 2."
2. **Map reacts, never drives.** The map answers "where is this resource?" It does not auto-refresh, pulse, or initiate interaction. It responds to user selection.
3. **One domain at a time.** The coordinator thinks in domains (Medical, Transport, Environment, Infrastructure). The interface reflects that mental model — it does not flatten everything onto one screen.
4. **Demand queue is resource requests, not incident reports.** Incoming items are "PSP Annopol requesting 2 ZRM" — not "fire at coordinates X." This distinction drives every design decision in that panel.
5. **Peacetime and crisis are the same screen.** The dual-use story is told by the data changing, not by a mode switch. Same layout, same mental model — the numbers change color.
6. **Never auto-rerender.** No component replaces itself unprompted. Incremental updates only: changed rows update, unchanged rows stay. The operator's attention should never be pulled away from what they are looking at.

---

## 2. Architecture Decision: Domain Switcher + KPI-First + Demand Queue

### What was chosen

Three proposals combined into one layout:

**Domain Switcher (navigation)** — the coordinator thinks in domains, not incident types. Four domains:

| Domain | Question it answers |
|---|---|
| Medical | How many ZRM units are free? Which hospitals have capacity and what specializations? |
| Transport | Which routes are passable? Which transport companies have vehicles available? |
| Environment | Are conditions creating resource demand? (river levels, air quality affecting deployment zones) |
| Infrastructure | Are utilities, bridges, shelters operational and accessible? |

**KPI-First (default view per domain)** — a strip of 3–4 numbers at the top of each domain view. Every KPI measures resource availability, not threat count. The strip surfaces the numbers the coordinator needs at a glance without requiring any interaction.

**Demand Queue (right panel)** — a queue of incoming resource requests, not an incident feed. Each item represents an external actor requesting a specific resource. Two actions: Assign (pick a specific resource) and Defer (logged, not lost).

### Single-domain layout

```
┌──────────────────────────────────────────────────────────────────┐
│ SENTINEL  [MEDICAL]        ● NORMALNY      13 Apr 2026   Jerzy ▾ │
├──────────────────────────────────────────────────────────────────┤
│  ZRM wolne: 8/12  │  Łóżka wolne: 340  │  Centra urazowe: 3/3   │
├─────────────────┬───────────────────────┬────────────────────────┤
│  ZASOBY         │                       │  ŻĄDANIA ZASOBÓW       │
│  ─────────────  │   MAPA                │  ────────────────────  │
│  ● ZRM Puławy   │   (shows resource     │  🟠 PSP Annopol:       │
│    dostępny     │    locations,         │     2 ZRM, ASAP        │
│  ● ZRM Lublin   │    not incidents)     │  🟡 Szpital Radom:     │
│    zajęty       │                       │     transfer 3 pacj.   │
│  ○ ZRM Kozien.  │   Click resource →    │  🟢 Ćwiczenia Płock:  │
│    niedostępny  │   highlights on map   │     1 ZRM, 14:00       │
│                 │   + demand context    │                        │
│  [+ Dodaj zasób]│                       │  [PRZYDZIEL] [ODROCZ] │
└─────────────────┴───────────────────────┴────────────────────────┘
```

**Left panel — Resource Inventory:** Resources in this domain with status (available / deployed / unavailable) and location. Clicking a resource highlights it on the map and shows any pending demand nearby.

**Center — Map:** Shows where resources are, not where incidents are. Passive — reacts to selections, never auto-refreshes.

**Right panel — Demand Queue:** Incoming resource requests. Each item shows who is requesting what, at what urgency. Two actions per item: PRZYDZIEL (assign a specific resource from the inventory) and ODROCZ (defer — logged, not dropped).

---

## 3. What Was Rejected and Why

| Rejected | Reason |
|---|---|
| AI chatbot as primary interface | Felt forced at hackathon; judge right to call it out. If reintroduced, it should be a briefer (speaks first, summarizes status) — not a chatbot (waits for questions). For now: hidden or collapsed. |
| Auto-refreshing map | Causes re-render flicker; pulls attention unprompted; violates Principle 2. |
| Multi-user role system | 2-year roadmap, not near-term. The `/director` read-only route captures the concept at near-zero cost. |
| Full-screen map as primary view | Map is one panel among three — not the primary UI element. The coordinator manages resources, not geography. |
| A+B merge as originally proposed | A non-decision. Merging proposals avoids commitment. |

---

## 4. The Dual-Use Story

The interface is the same in peacetime and crisis. That is the dual-use story. The data changes; the numbers change color; no mode switch is needed.

Demo narration that makes this concrete:

> "This is what the coordinator sees on a Tuesday morning. ZRM: 8/12, green. Hospital beds: 340 free. All transport routes clear. Demand queue is empty. Ninety seconds, no decisions needed.
>
> Now — a flood hits. Same screen, same coordinator, same mental model. ZRM: 2/12, red. Routes: 3 blocked. Demand queue: 11 requests, top 3 urgent. This is the system working."

No redesign needed. The visual language shifts because the data shifts — not because a button was pressed.

---

## 5. Domain Events Model

These are the events that Stage 3 hooks fire and Stage 4 UIs consume via SSE. The data model and KPIs follow from these events — not the other way around.

### Resource lifecycle

- `ResourceRegistered` — a new resource enters the system (ZRM unit, hospital, transport company)
- `ResourceStatusChanged` — a resource becomes available / deployed / unavailable
- `ResourceLocationUpdated` — a resource moves (vehicle in transit)

### Demand lifecycle

- `ResourceRequested` — an external actor requests a resource ("PSP Annopol: 2 ZRM, ASAP")
- `ResourceAssigned` — coordinator assigns a specific resource to a request
- `ResourceDeferred` — coordinator defers a request (logged, not lost)
- `AssignmentCompleted` — resource returns to available pool

### Environmental signals

- `ThresholdBreached` — a monitored value crosses an alert level (river stage, PM2.5, temperature)
- `ThresholdCleared` — value returns to normal range
- `RouteStatusChanged` — a road or transport route becomes blocked / cleared

### Operational

- `DomainStatusChanged` — aggregate status of a domain shifts (NORMAL → WARNING → CRISIS)
- `BriefingGenerated` — system produces a situational summary (deterministic template, not LLM)

`ThresholdBreached` aligns directly with `TrendDetectorHook` in Stage 3. When the hook fires, the Environment domain tile changes state and a demand queue item may appear — both reactions consume the same event.

---

## 6. Frontend Technology

### SSE over WebSockets

SENTINEL needs unidirectional streaming — the server pushes state changes to connected clients; clients do not push data back via the stream. SSE is the right fit: simpler to implement, native browser reconnection, standard HTTP. WebSockets add bidirectional complexity without benefit here.

Event envelope: `{ id, type, ts, domain, payload, version }`. Svelte stores subscribe to the SSE stream; `Last-Event-ID` enables replay on reconnect.

### Why Svelte

The current frontend is approximately 2000 lines of vanilla JS in a single file. It works but makes granular DOM updates difficult and is not maintainable at scale. Svelte compiles to vanilla JS, has reactivity built into the language rather than as a runtime library, and integrates naturally with SSE streams via stores. It is the lowest-friction path from the current state to a maintainable component architecture.

### Migration approach

New Svelte UI is served at `/svelte`. Legacy map remains at `/` and is unchanged during migration. The Svelte app subscribes to SSE for incremental updates; initial state is loaded via REST on first open (SSE alone is not sufficient to populate the dashboard — it handles updates, not bootstrap).

Milestones:
1. SSE infrastructure — event envelope defined, stream endpoint live, Svelte store proven end-to-end including reconnect
2. Dashboard UI — domain switcher, KPI strip, demand queue wired to SSE stores
3. Legacy UX stabilization — fix re-render pressure points in legacy frontend without a rewrite
4. Feature parity — map panel, action flows (Assign/Defer), then retire legacy as fallback

---

## 7. The /director Route

A simple read-only view at `/dashboard/director`. No auth required — just a separate route. Costs one afternoon, delivers the "Houston" demo story.

Fed by `escalated=true` flag on resource requests. Shows aggregate domain status (RAG tiles per domain) and escalated items only. No allocation actions — this is an observer view.

```
┌─────────────────────────────────────────────────────┐
│ SENTINEL — WIDOK DYREKTORA                          │
├──────────────┬──────────────┬───────────────────────┤
│  MEDYCZNY    │  TRANSPORT   │  ŚRODOWISKO / INFRA   │
│  ● NORMALNY  │  ⚠ UWAGA     │  ● NORMALNY           │
│  ZRM 8/12    │  3 trasy zab │  Rzeki: OK            │
├──────────────┴──────────────┴───────────────────────┤
│  ESKALACJE                                          │
│  🟠 Transport — PSP Annopol: 2 ZRM (Jerzy: pending) │
│  🟢 Medical — transfer Radom (Jerzy: assigned)      │
└─────────────────────────────────────────────────────┘
```

The RAG tiles per domain show `DomainStatusChanged` events. The escalations list shows resource requests with `escalated=true` and their current assignment state. The director does not need to act — they need to see whether things are being handled.

This view captures the multi-user role concept at near-zero implementation cost: no auth system, no role state machine, no session management. A separate URL is sufficient for the demo.
