MVP tech stack
Client: Chrome Extension (MV3)

TypeScript

React

Vite (MV3-friendly bundling)

three.js (renders lightweight 3D avatar GLB + proxy garment shell)

idb (IndexedDB caching: avatar GLB, product extracts, fit results)

zod (validate API responses + contracts)

(Optional) Sentry for extension errors

Core Platform (Coolify)

API (Node/TS)

Node.js + TypeScript

Fastify (fast, minimal)

Prisma (DB ORM + migrations)

PostgreSQL (Coolify service)

Redis (Coolify service; caching + queues)

BullMQ (job queue backed by Redis)

MinIO (Coolify service; S3-compatible storage for photos + GLBs + screenshots)

OpenAI API (used only for product-page extraction fallback: HTML+screenshots → strict JSON)

Infra

Docker everywhere

Docker Compose for local dev

Coolify deploy for API + Postgres + Redis + MinIO

CDN (optional but recommended) in front of MinIO public downloads for fast GLB delivery

GPU Worker (RunPod)

Python

PyTorch

A parametric 3D avatar pipeline (front+side photos + height → lightweight GLB)

gltfpack (meshoptimizer) for GLB compression + mesh optimization

Worker runs as a container on RunPod, consumes jobs from Redis (Coolify) or via API polling

Monorepo structure (final)
tryfitted/
├─ apps/
│  ├─ extension/                       # Chrome MV3 extension
│  │  ├─ src/
│  │  │  ├─ background/                # MV3 service worker
│  │  │  ├─ content/                   # DOM detection + injection + extraction
│  │  │  │  ├─ detectors/              # PDP detection + platform heuristics
│  │  │  │  ├─ extractors/             # JSON-LD/OG/DOM candidate extraction
│  │  │  │  └─ inject/                 # "Try fitted" button + modal mount
│  │  │  ├─ ui/                        # React UI (popup + modal)
│  │  │  ├─ viewer/                    # three.js scene + loaders + proxy garment mesh
│  │  │  ├─ api/                       # typed client + zod response guards
│  │  │  ├─ storage/                   # token store + IndexedDB cache
│  │  │  └─ utils/
│  │  ├─ public/
│  │  ├─ manifest.template.json
│  │  ├─ vite.config.ts
│  │  └─ package.json
│  │
│  ├─ api/                             # Platform backend (Coolify deploy)
│  │  ├─ src/
│  │  │  ├─ server.ts
│  │  │  ├─ routes.ts
│  │  │  ├─ modules/
│  │  │  │  ├─ auth/                   # JWT, refresh
│  │  │  │  ├─ uploads/                # presign URLs (photos/screenshots)
│  │  │  │  ├─ avatars/                # avatar jobs + current avatar
│  │  │  │  ├─ products/               # resolve + extract-ai + cache
│  │  │  │  ├─ tryon/                  # fit endpoint + caching
│  │  │  │  └─ events/                 # optional telemetry
│  │  │  ├─ lib/
│  │  │  │  ├─ db/                     # Prisma client
│  │  │  │  ├─ cache/                  # Redis helpers
│  │  │  │  ├─ queue/                  # BullMQ setup + processors
│  │  │  │  ├─ storage/                # MinIO client
│  │  │  │  ├─ openai/                 # prompts + schema enforcement
│  │  │  │  └─ validators/             # zod schemas
│  │  │  └─ config/
│  │  ├─ prisma/
│  │  │  ├─ schema.prisma
│  │  │  └─ migrations/
│  │  ├─ Dockerfile
│  │  └─ package.json
│  │
│  └─ web/                             # Optional onboarding web app (recommended)
│     ├─ src/                          # upload photos + avatar status
│     ├─ Dockerfile
│     └─ package.json
│
├─ services/
│  └─ avatar-worker/                   # RunPod GPU worker (container)
│     ├─ src/
│     │  ├─ worker.py                  # queue consumer (BullMQ/Redis) or API polling
│     │  ├─ pipeline/
│     │  │  ├─ preprocess.py           # crop, background removal, normalize
│     │  │  ├─ fit_body.py             # parametric fit -> mesh
│     │  │  ├─ measure.py              # measurement extraction
│     │  │  ├─ optimize_glb.py         # gltfpack compression + LOD
│     │  │  └─ export_upload.py        # upload GLB + metadata to MinIO
│     │  ├─ clients/
│     │  │  ├─ redis_client.py
│     │  │  ├─ minio_client.py
│     │  │  └─ api_client.py           # callback update job status
│     │  └─ config.py
│     ├─ requirements.txt
│     ├─ Dockerfile
│     └─ README.md
│
├─ packages/
│  └─ shared/                          # shared contracts (single source of truth)
│     ├─ src/
│     │  ├─ contracts/                 # zod schemas for requests/responses
│     │  ├─ types/
│     │  └─ index.ts
│     └─ package.json
│
├─ infra/
│  ├─ docker-compose.yml               # local dev: api, db, redis, minio
│  ├─ coolify/                         # optional: coolify notes + env templates
│  └─ runpod/                          # runpod deploy notes + worker env templates
│
├─ scripts/
│  ├─ dev.sh
│  ├─ seed.ts
│  └─ release-extension.sh
│
├─ .env.example
├─ package.json                        # workspace root (pnpm recommended)
└─ pnpm-workspace.yaml

Notes that make this “MVP practical”

Extension does rendering + caching only (fast)

OpenAI is only used for extraction fallback (not every page)

GPU work is isolated on RunPod (cheap + scalable)

Everything is Dockerized (Coolify deploy is straightforward)