# Sentinel Documentation

All documentation is organized around the pluggable pipeline:

```
Stage 1: Sources → Stage 2: Observations → Stage 3: Reactions → Stage 4: Outputs
```

---

## Pipeline

Stage-by-stage implementation docs. Each covers current state and target design.

| File | What it covers |
|---|---|
| [pipeline/1-sources.md](pipeline/1-sources.md) | Plugin system, BasePlugin interface, all current plugins, how to add new ones |
| [pipeline/2-observations.md](pipeline/2-observations.md) | Current EventRow paths (broken), target observations table + DataWriter |
| [pipeline/3-reactions.md](pipeline/3-reactions.md) | Hook registry, TrendDetectorHook, AlertDispatchHook, APScheduler — all target design |
| [pipeline/4-outputs.md](pipeline/4-outputs.md) | Map layers, voice briefing, AI configurator (existing); reports, alerts, operator panel (target) |

## Architecture

Investigation findings and high-level design decisions.

| File | What it covers |
|---|---|
| [architecture/de-facto-analysis.md](architecture/de-facto-analysis.md) | What actually runs today — two disconnected data paths, ephemeral flood assessment, in-memory crisis store |
| [architecture/pipeline-redesign.md](architecture/pipeline-redesign.md) | Full 4-stage redesign: observations table, hook registry, output plugin types, phased implementation order |

## Product

Who the system is built for and how the UI should work.

| File | What it covers |
|---|---|
| [product/user-personas.md](product/user-personas.md) | Client A (Resource Coordinator) and Client B (Flood Duty Officer) — same pipeline, different Stage 4 configurations |
| [product/ui-design.md](product/ui-design.md) | Design principles, domain switcher architecture, domain events model, SSE + Svelte rationale |

## Features

Existing subsystem documentation. These describe what is built and running today.

| File | What it covers |
|---|---|
| [features/flood-assessment.md](features/flood-assessment.md) | 3-source rule engine (gauge + ISOK + 112 calls), EVACUATE/AT_RISK conditions, override system |
| [features/voice-briefing.md](features/voice-briefing.md) | Briefing assembly, ElevenLabs TTS, word alignment, fallback paths |
| [features/evacuation-dispatch.md](features/evacuation-dispatch.md) | Unit pool, priority classification, greedy dispatch algorithm |
| [features/simulation-demo.md](features/simulation-demo.md) | Zestaw A (flood) and Zestaw D (fire/smog) demo sequences, control systems |

## API

Contracts for external consumers of the Sentinel API.

| File | What it covers |
|---|---|
| [api/external-consumers.md](api/external-consumers.md) | Grafana + Usemaps API contract — all endpoints Grafana depends on, field names, ordering requirements |

## Client

Deployment-specific analysis for a specific client engagement.

| File | What it covers |
|---|---|
| [wczk-analysis/README.md](wczk-analysis/README.md) | Overview of the WCZK engagement |
| [wczk-analysis/gap-analysis.md](wczk-analysis/gap-analysis.md) | Client requirements vs. current Sentinel capabilities, coverage scores |
| [wczk-analysis/implementation-plan.md](wczk-analysis/implementation-plan.md) | 5-phase delivery plan with risk register and effort estimates |
