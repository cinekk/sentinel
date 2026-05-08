# WCZK Analysis — Warmińsko-Mazurskie

Documents in this directory cover the requirements and implementation plan for adapting Sentinel to the needs of the Warmińsko-Mazurskie voivodeship's Crisis Management Center (WCZK).

**Source document:** `MONITORING POWODZIOWY.pdf` (authored by Krzysztof Kuriata, Dyrektor Wydziału Bezpieczeństwa i Zarządzania Kryzysowego)

## Documents

- [gap-analysis.md](gap-analysis.md) — What the client needs vs what Sentinel already has. Table-format, covers all functional areas.
- [implementation-plan.md](implementation-plan.md) — 5-phase delivery plan with technical decisions, effort estimates, and risk register.

## TL;DR

Sentinel's architecture matches the client's requirements perfectly. The structural gaps are:
1. Wrong voivodeship scope (Lublin → Warmińsko-Mazurskie) — trivial fix
2. No time-series persistence for gauge readings — needed for trends and charts
3. No scheduled reports (06:30/18:30) or PDF generation
4. No alert delivery (email/Telegram)
5. No WCZK operator panel for duty officers
6. No media monitoring
7. No +12h ML prediction (largest gap, needs data first)

Phases 1-4 (full spec minus ML) are achievable in ~3.5 weeks.
Phase 5 (ML prediction) needs 2 weeks of data maturation before development starts.
