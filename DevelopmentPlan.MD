## Robust phased development plan (build + test phase-by-phase)

This plan is optimized to ship a “real” MVP quickly by (1) proving the UX and the fit engine with fixtures early, (2) isolating GPU complexity behind an async job system, and (3) treating contracts + performance budgets as hard exit gates.

### Product scope (MVP)
- Chrome desktop extension that injects a “Try fitted” experience on product pages without retailer integration (`DevelopmentDesigns/AppSummary.MD:1`, `DevelopmentDesigns/MVPRequirements.MD:1`)
- One-time avatar creation from front+side photos + height → optimized GLB + measurements (`DevelopmentDesigns/AppSummary.MD:9`, `DevelopmentDesigns/AppDiagramFlow.MD:5`)
- Tops-only fit analysis + proxy garment visualization (`DevelopmentDesigns/AppSummary.MD:13`, `DevelopmentDesigns/AppDiagramFlow.MD:83`)
- Product-page detection + heuristic extraction, with OpenAI fallback only when needed (`DevelopmentDesigns/AppSummary.MD:17`, `DevelopmentDesigns/AppDiagramFlow.MD:94`)

### Non-goals (explicitly excluded from MVP)
- No retailer dashboard, retailer widget, or retailer onboarding (`DevelopmentDesigns/MVPRequirements.MD:25`)

### Global engineering rules (MVP)
- Contract-first: all API <-> extension payloads come from `packages/shared` contracts (`DevelopmentDesigns/TechStack.MD:129`)
- GPU isolation: avatar generation is always async and offloaded to the worker (`DevelopmentDesigns/AppDiagramFlow.MD:37`)
- Cache-first UX: extension opens immediately and fetches/warms data in the background (`DevelopmentDesigns/AppDiagramFlow.MD:20`)
- Heuristics-first extraction: OpenAI is strictly a fallback path (`DevelopmentDesigns/TechStack.MD:36`)

### Testing strategy (applies to every phase)
- Unit tests: fit rules, extractors, schema validators, viewer math (fast, deterministic)
- Contract tests: reject any payloads that don’t match zod schemas (`DevelopmentDesigns/TechStack.MD:14`)
- Integration tests: API routes against local Postgres/Redis/MinIO (`DevelopmentDesigns/TechStack.MD:42`)
- Extension smoke/E2E: install → detect PDP → inject → overlay → try-on request (`DevelopmentDesigns/AppDiagramFlow.MD:7`)
- Performance regression: budgets and curated “50+ product pages” list tracked over time (`DevelopmentDesigns/AppSummary.MD:25`)

---

## Phase 0 — Foundations: repo, contracts, local infra, staging (2–4 days)
**Goal:** every dev can run end-to-end locally; staging is continuously deployable.

**References:** `DevelopmentDesigns/TechStack.MD:1`, `DevelopmentDesigns/AppDiagramFlow.MD:16`

**Deliverables**
- Monorepo layout aligned with the target structure (`DevelopmentDesigns/TechStack.MD:60`)
- `packages/shared` request/response contracts (zod) used by both API + extension (`DevelopmentDesigns/TechStack.MD:129`)
- Local `docker-compose` with Postgres + Redis + MinIO + API (`DevelopmentDesigns/TechStack.MD:137`)
- Staging deployment on Coolify for API + services (`DevelopmentDesigns/TechStack.MD:44`)

**Work items**
- Repo/tooling: pnpm workspace, TypeScript project refs (or equivalent), lint/format, basic CI (build + unit tests + contract checks)
- API scaffold: Fastify server, `/health`, request logging and correlation IDs
- Storage scaffold: MinIO client + presigned upload flow (photos/screenshots) (`DevelopmentDesigns/AppDiagramFlow.MD:13`)
- Queue scaffold: Redis + BullMQ baseline, one “no-op” job processor end-to-end (`DevelopmentDesigns/TechStack.MD:30`)

**Tests / exit gate**
- Contract tests: zod schemas compile + API responses validated at runtime
- Integration test: “presign → upload → fetch metadata” against local MinIO
- Exit gate: `pnpm dev` brings up infra + API; staging has `/health`; browser can upload via presigned URL

---

## Phase 0.5 — Fast vertical slice with fixtures (2–4 days)
**Goal:** validate UX + viewer + fit reporting without waiting on GPU avatar generation.

**References:** `DevelopmentDesigns/AppDiagramFlow.MD:60`, `DevelopmentDesigns/AppDiagramFlow.MD:75`

**Deliverables**
- “Fit Lab” internal page that loads a sample avatar GLB + fixture size charts and renders proxy fit heatmap
- `POST /v1/tryon/fit` implemented against fixture charts (no product extraction yet)

**Work items**
- Add a small set of garment fixtures (10–20) and expected outcomes for deterministic testing
- Implement proxy garment shell + heatmap rendering in three.js (standalone page first, then reused by extension) (`DevelopmentDesigns/TechStack.MD:10`)

**Tests / exit gate**
- Unit tests: fit rules engine deterministic on fixtures
- Performance check: proxy update is instant on size changes; render <1s typical laptop
- Exit gate: non-technical tester can pick garment+size and see stable, performant results

---

## Phase 1 — Avatar system v1: photos → GLB + measurements (1–3 weeks)
**Goal:** upload photos + height → async GPU job → optimized GLB + measurements available to extension.

**References:** `DevelopmentDesigns/AppSummary.MD:9`, `DevelopmentDesigns/AppDiagramFlow.MD:13`, `DevelopmentDesigns/TechStack.MD:48`

**Deliverables**
- API: photo uploads + avatar job lifecycle + “current avatar” retrieval (`DevelopmentDesigns/AppDiagramFlow.MD:13`, `DevelopmentDesigns/AppDiagramFlow.MD:53`)
- Worker: GPU pipeline v1 produces `avatar.glb`, `measurements.json`, `quality_report.json` (`DevelopmentDesigns/AppDiagramFlow.MD:40`)
- “Avatar Lab” internal page for uploading, job status, GLB viewing, measurement review

**Work items (API)**
- Data model: `users`, `uploads`, `avatar_jobs`, `avatars`
- Endpoints:
  - `POST /v1/uploads/presign`
  - `POST /v1/avatar/jobs`, `GET /v1/avatar/jobs/:id`, `GET /v1/avatar/current`
- Queue: `avatar_build` jobs with retry + idempotency; store job status transitions

**Work items (Worker)**
- Consume BullMQ/Redis (or API polling initially) (`DevelopmentDesigns/TechStack.MD:58`)
- Pipeline: preprocess → parametric fit → measurement extraction → `gltfpack` optimization → upload outputs (`DevelopmentDesigns/TechStack.MD:56`)
- Callback/status update to API; ensure worker survives restarts

**Tests / exit gate**
- Regression dataset: 20–50 photo pairs with automated checks (GLB size/tri budget, measurement stability)
- API integration tests: job lifecycle queued→running→succeeded/failed; output URLs fetchable in browser
- Exit gate: ≥80% success rate on dataset; measurements repeatability ±1–3cm; GLB loads smoothly in Chrome

---

## Phase 2 — Fit engine v1 + proxy visualization (tops-only) (1–2 weeks)
**Goal:** given `avatar measurements + garment chart` produce fit report + render directives, then visualize.

**References:** `DevelopmentDesigns/AppSummary.MD:13`, `DevelopmentDesigns/AppDiagramFlow.MD:75`

**Deliverables**
- `POST /v1/tryon/fit` endpoint with confidence scoring + render directives (`DevelopmentDesigns/AppDiagramFlow.MD:75`)
- Fit rules engine (ease rules + stretch allowance) and zone outputs (chest/waist/hip/shoulder/sleeve/length)
- Fit Lab uses real avatars from Phase 1, not just fixtures

**Work items**
- Define/lock contract schemas for:
  - `FitRequest` (category=top, sizeLabel, sizeChart, materialProfile)
  - `FitResponse` (zones, overall, confidence, renderDirectives)
- Implement confidence rules: missing chart fields → “low confidence”

**Tests / exit gate**
- Unit tests: deterministic outputs on fixtures; schema validation in API + client
- End-to-end check: load real avatar → fit request → viewer renders correct zones
- Exit gate: fit outputs match expected fixtures; proxy visualization stable and performant

---

## Phase 3 — Chrome extension MVP: detection, injection, extraction, caching (1–3 weeks)
**Goal:** run the proven avatar + fit flow on real product pages with “no retailer integration”.

**References:** `DevelopmentDesigns/AppSummary.MD:7`, `DevelopmentDesigns/AppDiagramFlow.MD:7`, `DevelopmentDesigns/MVPRequirements.MD:1`

**Deliverables**
- MV3 extension: PDP detection → inject “Try fitted” button → overlay viewer (`DevelopmentDesigns/AppSummary.MD:3`)
- Background prefetch: resolve/extract product info before user clicks to keep click-to-result fast (`DevelopmentDesigns/AppDiagramFlow.MD:20`)
- IndexedDB caching for avatar GLB, product extracts, and fit results (`DevelopmentDesigns/TechStack.MD:12`)

**Work items**
- Product-page detection + injection:
  - Content script detectors + React modal mount (`DevelopmentDesigns/TechStack.MD:66`)
  - Error handling: unsupported page, missing size chart, no avatar yet
- Product data extraction pipeline:
  - Heuristics first: JSON-LD, og:image, DOM selectors (`DevelopmentDesigns/AppDiagramFlow.MD:15`)
  - Cache product resolves per URL/domain (`DevelopmentDesigns/AppDiagramFlow.MD:24`)
  - OpenAI fallback only on low-confidence pages (`DevelopmentDesigns/TechStack.MD:36`, `DevelopmentDesigns/AppDiagramFlow.MD:31`)
- Try-on UX:
  - Start with manual size selection in overlay (`DevelopmentDesigns/AppDiagramFlow.MD:60`)
  - Call `/v1/tryon/fit` and render zones + confidence (`DevelopmentDesigns/AppDiagramFlow.MD:83`)

**Tests / exit gate**
- Curated compatibility list: 50+ real product pages used for manual + automated regression
- Extension smoke tests: install → detect → open overlay → render avatar → request fit
- Performance budgets: median click-to-result <1s on warm cache; no crashes

---

## Phase 4 — Ship readiness: privacy, reliability, release (3–7 days)
**Goal:** be safe to ship to real users and iterate without breaking them.

**References:** `DevelopmentDesigns/AppSummary.MD:25`, `DevelopmentDesigns/TechStack.MD:16`

**Deliverables**
- Privacy endpoints: delete avatar/photos + associated storage objects
- Observability: error tracking for extension + API (optional Sentry)
- Release pipeline: build + sign + publish extension; staging always deployable from `main`

**Tests / exit gate**
- Negative testing: missing data, timeouts, worker failures, retries, partial uploads
- Load/perf smoke: API p95 latency targets for `resolve` and `fit`; viewer FPS check on mid-tier laptop
- Exit gate: release checklist complete; staged rollout possible; rollback plan documented

---

## Post-MVP (explicitly deferred)
- Retailer integration module + JS embed + dashboard (`DevelopmentDesigns/MVPRequirements.MD:41`)
