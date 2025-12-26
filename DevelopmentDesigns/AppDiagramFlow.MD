┌──────────────────────────────────────────────────────────────────────────────┐
│                           MVP FLOW (NO RETAILER INTEGRATION)                 │
└──────────────────────────────────────────────────────────────────────────────┘

   1) USER ONBOARDING (ONE TIME)                         2) BROWSING + TRY FITTED
┌───────────────────────────────┐               ┌───────────────────────────────┐
│ Web Onboarding Page (optional) │               │ Chrome Extension (MV3)         │
│ or Extension Onboarding UI     │               │ - detects clothing product page│
│ - take/upload front+side photos│               │ - injects "Try fitted" button  │
│ - enter height (required)      │               │ - three.js viewer overlay      │
└───────────────┬───────────────┘               └───────────────┬───────────────┘
                │                                               │
                │ 1a) request presigned upload URLs             │ 2a) page detected (background)
                v                                               │     extract candidates:
      ┌───────────────────────────┐                             │     - URL, JSON-LD Product
      │ Platform API (Coolify)     │                             │     - og:image + DOM images
      │ Fastify + TS               │                             │     - size options text
      └───────────────┬───────────┘                             │
                      │                                         │
                      │ 1b) upload photos                        │ 2b) prefetch product resolve (non-blocking)
                      v                                         v
            ┌──────────────────────┐                   ┌───────────────────────────┐
            │ Object Storage        │                   │ Platform API               │
            │ MinIO (Coolify)       │                   │ /v1/products/resolve       │
            │ - raw photos          │                   │ - heuristic parse           │
            │ - screenshots (opt)   │                   │ - cache per URL/domain      │
            └──────────────┬───────┘                   └───────────────┬───────────┘
                           │                                           │
                           │ 1c) enqueue avatar job                    │ (fallback if low confidence)
                           v                                           v
                 ┌──────────────────────┐                   ┌───────────────────────────┐
                 │ Redis + BullMQ       │                   │ OpenAI (3rd party)          │
                 │ (Coolify)            │                   │ - parse HTML/snaps           │
                 │ - avatar jobs        │                   │ - return strict JSON         │
                 └───────────┬──────────┘                   └───────────────┬───────────┘
                             │                                           │
                             │ 1d) worker consumes job (GPU)             │ result cached
                             v                                           v
                 ┌────────────────────────────┐                ┌───────────────────────────┐
                 │ GPU Avatar Worker (RunPod)  │                │ Postgres + Redis Cache      │
                 │ - build lightweight 3D body │                │ - users, avatar metadata     │
                 │ - measure extraction        │                │ - product extracts           │
                 │ - compress GLB (gltfpack)   │                │ - fit results                │
                 └──────────────┬─────────────┘                └───────────────┬───────────┘
                                │                                              │
                                │ 1e) upload GLB + metadata                    │
                                v                                              │
                      ┌──────────────────────┐                                  │
                      │ MinIO / CDN          │                                  │
                      │ - avatar.glb         │                                  │
                      └──────────────┬───────┘                                  │
                                     │                                          │
                                     │ 1f) extension polls avatar ready         │
                                     v                                          │
                          ┌──────────────────────┐                               │
                          │ Extension stores      │                               │
                          │ avatar GLB in IndexedDB│                               │
                          └──────────────────────┘                               │

   3) TRY FITTED (ON ANY PRODUCT PAGE)
┌──────────────────────────────────────────────────────────────────────────────┐
│ User clicks "Try fitted"                                                     │
└──────────────────────────────────────────────────────────────────────────────┘
                │
                │ 3a) Extension opens overlay immediately (shows avatar)
                │     - loads avatar GLB from IndexedDB (warm) or CDN (cold)
                v
      ┌───────────────────────────┐
      │ Extension 3D Viewer        │
      │ (three.js)                 │
      └───────────────┬───────────┘
                      │
                      │ 3b) Request fit + render directives
                      v
      ┌───────────────────────────┐
      │ Platform API               │
      │ POST /v1/tryon/fit         │
      │ - avatarId                 │
      │ - productKey/url/image     │
      │ - chosen size              │
      └───────────────┬───────────┘
                      │
                      │ 3c) Backend returns:
                      │ - fit report (tight/ok/loose zones)
                      │ - renderDirectives (proxy shell offsets + tension)
                      v
      ┌───────────────────────────┐
      │ Extension 3D Viewer        │
      │ - builds garment proxy mesh │
      │ - applies heatmap/tension   │
      │ - shows fit + confidence    │
      └───────────────────────────┘

KEY MVP PROPERTIES
- No retailer scripts, no retailer dashboard.
- Works by extracting data from the product page (heuristics + OpenAI fallback).
- Heavy 3D avatar generation runs on RunPod once; extension only renders.
