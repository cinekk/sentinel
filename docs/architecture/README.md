# Architecture Documentation

Documents in this directory cover the structural design of the Sentinel platform — how data flows, what needs to change, and why.

## Documents

- [de-facto-analysis.md](de-facto-analysis.md) — What actually exists in the codebase today, traced from first principles. The gap between the documented pipeline and what runs in production.
- [pipeline-redesign.md](pipeline-redesign.md) — The four-stage pipeline design (Sources → Observations → Reactions → Outputs), the `observations` table schema, hook registry design, and phased implementation order.

## TL;DR

The plugin abstraction and all existing components are keepers. What's missing is the **connective tissue**:

1. An `observations` table to persist sensor readings (IMGW gauges, GIOŚ air quality) — currently discarded after a 5-min cache window.
2. A `HookRegistry` so that new data automatically triggers reactions (trend detection, alert dispatch).
3. `APScheduler` in the FastAPI lifespan to run background polling and scheduled reports.
4. `ReportPlugin` and `AlertPlugin` base classes to standardize push-based outputs (PDF, email, Telegram).

The existing map endpoints, demo scenarios, voice briefing, and flood assessment logic survive intact throughout the migration.
