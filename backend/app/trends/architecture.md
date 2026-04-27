┌──────────────────────────────────────────────────┐
│  EVERY 30 MIN (background)                       │
│  Celery Beat ──▶ trends_ingest task              │
│                       │                           │
│                       ▼                           │
│              source_client.py (fetch)            │
│                       │                           │
│                       ▼                           │
│              ingest.py (dedupe, score)           │
│                       │                           │
│                       ▼                           │
│              trending_articles table             │
└──────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────┐
│  USER REQUEST (foreground, <300ms)               │
│  GET /api/v1/trends/news                         │
│         │                                         │
│         ▼                                         │
│   router (trends.py)                             │
│         │                                         │
│         ▼                                         │
│   service.py — Redis check ─▶ HIT? return        │
│         │ (miss)                                  │
│         ▼                                         │
│   ranker.py — query DB, personalize top 9        │
│         │                                         │
│         ▼                                         │
│   write Redis cache, return                      │
└──────────────────────────────────────────────────┘