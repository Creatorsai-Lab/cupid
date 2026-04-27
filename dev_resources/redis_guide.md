# Redis Guide — Cupid Project

A reference for understanding Redis, how Cupid uses it, and how to debug it.
Read top to bottom the first time. Skim back to specific sections later.

---

## Table of Contents

1. [What Redis Is](#1-what-redis-is)
2. [Why Cupid Uses Redis](#2-why-cupid-uses-redis)
3. [Where Redis Fits in Cupid's Architecture](#3-where-redis-fits-in-cupids-architecture)
4. [The Cache-Aside Pattern (Cupid's Strategy)](#4-the-cache-aside-pattern-cupids-strategy)
5. [Step-by-Step Request Flow](#5-step-by-step-request-flow)
6. [Cache Keys, Values, and TTLs in Cupid](#6-cache-keys-values-and-ttls-in-cupid)
7. [Connecting to Redis](#7-connecting-to-redis)
8. [The Redis Command Reference (What Pros Use)](#8-the-redis-command-reference-what-pros-use)
9. [Debugging Workflows](#9-debugging-workflows)
10. [Common Pitfalls and Anti-Patterns](#10-common-pitfalls-and-anti-patterns)
11. [Future Use Cases for Redis in Cupid](#11-future-use-cases-for-redis-in-cupid)

---

## 1. What Redis Is

**Redis is a giant Python-dict-like data store that lives in RAM on a separate process.**

Think of it as `{}` but:
- Lives outside your application process
- Shared between many app instances and workers
- Survives application restarts (with persistence enabled)
- Has built-in time-to-live (TTL) for automatic cleanup
- Is accessed over TCP (slightly slower than a Python dict, much faster than a database)

### Comparison Table

| Aspect | Python `dict` | Redis | PostgreSQL |
|---|---|---|---|
| Lives where? | Inside app process | Separate process | Separate process |
| Survives restart? | No | Yes (with persistence) | Yes |
| Shared between processes? | No | Yes | Yes |
| Built-in expiration? | No | Yes (TTL) | No |
| Speed (single read) | ~100 nanoseconds | ~1 millisecond | ~50–200 milliseconds |
| Storage capacity | Limited by RAM | Limited by RAM | Limited by disk |
| Designed for | In-app temporary state | Cache, sessions, queues | Source of truth |

**The single most important property:** Redis is fast because it lives in RAM. Your database is slow because it lives on disk. Redis is the bouncer in front of your database — it answers easy questions on its own and only lets the database be bothered for hard ones.

### Data Types Redis Supports

Redis isn't just a key-value store — it has rich data types:

| Type | Use Case | Example |
|---|---|---|
| **String** | Cache values, counters | `GET trends:user:abc` |
| **Hash** | Object-like records | User profiles, session data |
| **List** | Queues, streams | Background job queues |
| **Set** | Unique collections | Online users, tags |
| **Sorted Set** | Leaderboards, time-ordered data | Trending rankings |
| **Stream** | Event logs, message bus | Pub/sub, audit trails |

**Cupid currently uses only Strings.** That's fine — strings cover 80% of cache use cases. The rest are tools you reach for as the project grows.

---

## 2. Why Cupid Uses Redis

The trends serving layer hits a fundamental performance wall:

### Without Cache

Every user request runs the full pipeline:

```
GET /api/v1/trends/news
  ├─ DB query: 60 articles in user's niche       (~50ms)
  ├─ BM25 ranking against persona vocabulary     (~30ms)
  ├─ Compose response object                      (~5ms)
  └─ Total: ~85ms per request
```

If 1,000 users hit this endpoint, the database runs 1,000 identical queries. CPU melts. Pages get slow under load.

### With Redis Cache

```
First request (cache MISS):
  ├─ Check Redis: empty                           (~1ms)
  ├─ DB query + BM25 + compose                   (~85ms)
  ├─ Write to Redis with 10-min TTL              (~1ms)
  └─ Total: ~87ms

Subsequent requests within 10 minutes (cache HIT):
  ├─ Check Redis: found                           (~1ms)
  ├─ Deserialize JSON                             (~2ms)
  └─ Total: ~3ms — 28× faster
```

**The cache makes the second-to-Nth request nearly free.** This is the entire reason Redis exists in your project.

### The Trade-Off

Caching trades **freshness** for **speed**. A user might see slightly stale data (up to 10 minutes old) in exchange for a 28× faster response. For trending news, this trade-off is correct: news that's 10 minutes "old" is still useful. For something like account balance, the trade-off would be wrong.

---

## 3. Where Redis Fits in Cupid's Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CUPID STACK                               │
└─────────────────────────────────────────────────────────────────┘

  ┌──────────────────┐
  │  Next.js         │   Frontend
  │  (port 3000)     │
  └────────┬─────────┘
           │ HTTP
           ▼
  ┌──────────────────┐
  │  FastAPI         │   API layer (port 8000)
  │  ┌─────────┐     │
  │  │routers/ │     │   ◀── HTTP entry points
  │  └─────────┘     │
  │  ┌─────────┐     │
  │  │trends/  │     │   ◀── Business logic
  │  │service  │     │
  │  └────┬────┘     │
  └───────┼──────────┘
          │
    ┌─────┴─────┬───────────────┐
    ▼           ▼               ▼
  ┌─────┐   ┌──────┐       ┌─────────┐
  │Redis│   │Postgres│     │ChromaDB │
  └─────┘   └──────┘       └─────────┘
   Cache    Source of      Vector store
   (RAM)    truth          (future use)
   port     port 5432      port 8001
   6379

  ┌──────────────────┐
  │  Celery Worker   │   Background jobs
  │  + Celery Beat   │   (also talks to Redis as broker, but
  │                  │    that's a different use of Redis)
  └──────────────────┘
```

### Redis Has Two Roles in Cupid

This is important to understand because it confuses people:

1. **Cache role** — what we've been discussing. Stores serving-layer responses.
2. **Celery broker role** — Celery uses Redis to pass tasks between the API and the worker. When you call `task.delay()`, the task is pushed onto a Redis list. The worker pops from that list to execute jobs.

These are the **same Redis server** but **different keys**:
- Cache keys: `trends:user:*`
- Celery keys: `celery-task-meta-*`, `_kombu.binding.*`, `unacked*`

You'll see both when you `KEYS *`. Don't confuse them.

---

## 4. The Cache-Aside Pattern (Cupid's Strategy)

Cupid uses the **cache-aside pattern**, also called **lazy loading**. It's the most common cache strategy and works for ~95% of caching needs.

### The Algorithm

```
GIVEN: a user's trends request
WANTED: the personalized feed

1. Build the cache key from the user's identity
2. Try to read the cache:
   ├─ HIT  → deserialize, return immediately
   └─ MISS → continue
3. Compute the result by querying the database and ranking
4. Write the result to the cache with a TTL
5. Return the result
```

### Why "Lazy" Loading?

The cache only fills when someone actually asks for the data. We never pre-populate it — that would waste memory on data nobody requested. The cache shape automatically tracks the actual usage pattern.

### Why "Cache-Aside" and not "Write-Through"?

There's an alternative pattern called **write-through caching** where every database update *also* updates the cache. Cupid doesn't use this because:

- The data we cache (BM25-ranked output) is computed, not stored. There's no "DB write" to hook into.
- Cache-aside has simpler invalidation — just let the TTL expire.
- Write-through requires every write path to know about every cache key. Bug-prone.

### The Critical Property: Graceful Degradation

**If Redis goes down, Cupid still works** — just slower. Every Redis call in the codebase is wrapped in try/except:

```python
async def _read_cache(redis: Redis, user_id: str) -> TrendsResponse | None:
    try:
        raw = await redis.get(_cache_key(user_id))
        if not raw:
            return None
        return TrendsResponse.model_validate(json.loads(raw))
    except Exception as exc:
        logger.warning("[trends.cache] read miss/error: %s", exc)
        return None    # ← falls through to DB path
```

A Redis outage causes a slowdown, not an outage. This principle — **caches are hints, not sources of truth** — is the foundation of all production caching.

---

## 5. Step-by-Step Request Flow

Walk through what happens when a user opens the Trends page in Cupid.

### Step 1: Frontend Makes Request

```http
GET /api/v1/trends/news
Authorization: Bearer eyJhbGc...
```

### Step 2: FastAPI Router Authenticates

The `get_current_user` dependency decodes the JWT and loads the User model. Result: `current_user.id = "user_abc123"`.

### Step 3: Service Builds the Cache Key

```python
key = f"trends:user:{user_id}"
# → "trends:user:user_abc123"
```

The `trends:user:` prefix is namespacing. If you ever cache something else, the prefix prevents key collisions and makes debugging easier.

### Step 4: Try the Cache

```python
raw = await redis.get("trends:user:user_abc123")
```

Two possible outcomes:

**HIT path** (subsequent requests within 10 min):
```python
data = json.loads(raw)
return TrendsResponse.model_validate(data)
# Total time: ~3ms. Done.
```

**MISS path** (first request, or expired):
```python
return None
# Continue to step 5.
```

### Step 5: Compute the Expensive Result

```python
# Map persona's free-text niche → category list
categories = _resolve_categories(persona["content_niche"])

# Pull pool of recent articles from DB
stmt = (
    select(TrendingArticle)
    .where(TrendingArticle.category.in_(categories))
    .where(TrendingArticle.published_at >= cutoff)
    .order_by(TrendingArticle.published_at.desc())
    .limit(60)
)
pool = list(await session.execute(stmt).scalars().all())

# Run personalized ranking — BM25 + recency + velocity
top = rank_articles(pool, persona, top_k=9)
```

Total time: ~85ms.

### Step 6: Build Response

```python
response = TrendsResponse(
    articles=[TrendArticle(...) for row in top],
    niche=niche,
    total_pool=len(pool),
    cached=False,
    generated_at=datetime.now(timezone.utc),
)
```

### Step 7: Write to Cache

```python
await redis.set(
    "trends:user:user_abc123",
    response.model_dump_json(),
    ex=600,    # ← TTL: expires in 600 seconds (10 minutes)
)
```

The `ex=600` is the magic. Redis automatically deletes this key after 10 minutes. **No cleanup job, no cron — Redis handles it.**

### Step 8: Return to Frontend

The frontend renders the 9 trending articles. Done.

### What Happens on the Second Request

Same user hits the endpoint 2 minutes later:

```
Step 1-3: same
Step 4: HIT — cached value returned in ~3ms
Step 5-7: SKIPPED entirely
Step 8: response returned 28× faster
```

That's the win.

---

## 6. Cache Keys, Values, and TTLs in Cupid

### Current Cache Entries

| Key Pattern | Value | TTL | Purpose |
|---|---|---|---|
| `trends:user:{user_id}` | `TrendsResponse` JSON | 600s (10 min) | Personalized news feed |

### Why These Specific Choices?

**Why per-user, not per-niche?**

Two users with the same `content_niche="ai/ml"` may have different `bio` or `usp` text. The BM25 ranker uses all of those signals, so identical-niche users get *different* article orderings. Caching by niche would let User A see User B's ranking. Per-user keys are correct at the cost of more entries (acceptable trade-off — RAM is cheap).

**Why a 10-minute TTL specifically?**

Three constraints lock this number in:
- **Ingestion runs every 30 minutes.** New articles can take up to 30 min to reach the DB.
- **A cached entry can be at most 10 min old by the end of its TTL.**
- **Worst-case staleness = ingestion lag + cache age = 30 + 10 = 40 minutes.**

For a "trending news" feature, 40 minutes of staleness is acceptable. If you reduced cache TTL to 60 seconds, freshness barely improves (still bottlenecked by 30-min ingestion) but DB load multiplies 10×.

### Why JSON Serialization?

```python
response.model_dump_json()    # → '{"articles": [...], "niche": "ai/ml", ...}'
```

Alternatives considered and rejected:

| Format | Pros | Cons | Verdict |
|---|---|---|---|
| **JSON** | Human-readable, debuggable | Slightly larger, slightly slower | ✅ **Cupid uses this** |
| Pickle | Faster, smaller | Binary, opaque, security risks | ❌ |
| MessagePack | Faster, smaller, language-neutral | Not human-readable | ❌ for now |

Always prefer **transparency over micro-optimization** for caches. When debugging, you'll thank yourself for being able to `GET key` and read the value directly.

---

## 7. Connecting to Redis

### Connection Settings

```env
# In backend/.env
REDIS_URL=redis://localhost:6379/0
```

The URL format breaks down as:
- `redis://` — protocol
- `localhost` — host (the Redis server)
- `6379` — port (Redis default)
- `/0` — database number (Redis has 16 numbered databases by default; we use #0)

### How Cupid Connects

In `app/core/redis.py`:

```python
from redis.asyncio import Redis

redis_client = Redis.from_url(
    settings.redis_url,
    decode_responses=True,    # auto-decode bytes → str
    encoding="utf-8",
)

async def get_redis() -> Redis:
    return redis_client
```

The `decode_responses=True` is important — without it, every Redis read returns `bytes` objects, and you'd need to manually `.decode("utf-8")` everywhere.

### The Docker Connection

Cupid runs Redis in Docker (see `docker-compose.yml`). The container is named `cupid_redis` and exposes port 6379 to localhost. Your app talks to it as if it were a local service.

To verify Redis is running:

```powershell
docker compose ps
```

You should see `cupid_redis` with status `running`.

---

## 8. The Redis Command Reference (What Pros Use)

### Three Ways to Talk to Redis

**Option A — `redis-cli` inside Docker (most common):**
```powershell
docker exec -it cupid_redis redis-cli
```

You're now inside the Redis shell. Type commands, hit Enter.

**Option B — One-shot commands without the shell:**
```powershell
docker exec cupid_redis redis-cli KEYS "trends:user:*"
docker exec cupid_redis redis-cli GET "trends:user:abc"
```

**Option C — RedisInsight GUI (best for exploration):**
- Download: https://redis.io/docs/latest/operate/redisinsight/
- Connect to `localhost:6379`
- Browse keys visually, see TTLs in real-time, run queries with autocompletion

For day-to-day debugging, mix all three. CLI for quick checks, GUI for exploration, one-shots for scripts.

### Essential Commands

#### Reading

```
GET key                      # read a string value
TYPE key                     # what type is this key (string, hash, list, ...)
EXISTS key                   # 1 if exists, 0 otherwise
TTL key                      # seconds until expiration. -1 = no TTL. -2 = doesn't exist
PTTL key                     # same as TTL but in milliseconds
```

#### Listing Keys

```
KEYS pattern                 # find all keys matching glob pattern
                             # e.g. KEYS trends:user:*
                             # ⚠️ AVOID in production with millions of keys
                             # — it blocks Redis. Use SCAN instead.

SCAN 0 MATCH pattern COUNT 100
                             # production-safe iteration
                             # returns a cursor + batch of keys
                             # call repeatedly until cursor returns 0

DBSIZE                       # total number of keys
```

#### Writing

```
SET key value                # write
SET key value EX seconds     # write with TTL
SETEX key seconds value      # alternate syntax for SET with TTL
EXPIRE key seconds           # add TTL to existing key
PERSIST key                  # remove TTL (key stays forever)
```

#### Deleting

```
DEL key1 key2 ...            # delete one or more keys
UNLINK key                   # async delete (better for huge values)
FLUSHDB                      # ⚠️ delete EVERYTHING in current DB
FLUSHALL                     # ⚠️⚠️ delete EVERYTHING across all DBs
```

`FLUSHDB` and `FLUSHALL` are the "drop database" of Redis. **Never run them in production unless you mean it.**

#### Server Info

```
INFO                         # everything about the Redis server
INFO memory                  # just memory usage
INFO stats                   # ops/sec, hit rate, etc.
INFO clients                 # connected clients
PING                         # → PONG. Health check.
DBSIZE                       # how many keys in current DB
```

#### Real-Time Monitoring (Gold for Debugging)

```
MONITOR                      # watch every command flowing through Redis
                             # ⚠️ heavy load — only for debugging
                             # press Ctrl+C to stop
```

`MONITOR` lets you literally see your code's `GET` and `SET` calls happen in real-time as users hit the API. Run it in one terminal, hit your API in another, and watch.

---

## 9. Debugging Workflows

### Scenario 1: "I keep seeing the same trending articles"

User reports stale data. Walk through cache → DB → ingestion to find where staleness lives.

```powershell
# Step 1 — Get a Redis shell
docker exec -it cupid_redis redis-cli

# Step 2 — Find the user's cache entry
> KEYS trends:user:*
1) "trends:user:user_abc123"
2) "trends:user:user_def456"

# Step 3 — Inspect their entry
> GET trends:user:user_abc123
"{\"articles\":[...],\"niche\":\"ai/ml\",\"total_pool\":42,...}"

> TTL trends:user:user_abc123
(integer) 412     # 412s left = 6.8 minutes

# Step 4 — If the cache content is stale, bust it
> DEL trends:user:user_abc123
(integer) 1

# Step 5 — Tell user to refresh. Their next request now hits step 5
# of the request flow (cache miss → recompute from DB).

# Step 6 — If they still see stale data after the cache miss,
# the problem is in INGESTION, not the cache.
```

### Scenario 2: "Ingestion seems broken — the DB has no fresh articles"

Verify the cache isn't masking the problem:

```powershell
# Check how many articles got ingested today
docker exec cupid_postgres psql -U cupid -d cupid_db -c \
  "SELECT category, COUNT(*) FROM trending_articles \
   WHERE ingested_at > NOW() - INTERVAL '1 hour' \
   GROUP BY category;"

# Check the Celery worker logs for errors
# (in your terminal where Celery is running)

# Manually trigger ingestion to see if it works
docker exec cupid_redis redis-cli LRANGE celery 0 -1
# (shows pending Celery tasks)
```

### Scenario 3: "Redis seems slow"

```powershell
# Check memory
docker exec cupid_redis redis-cli INFO memory | findstr used_memory_human

# Check ops per second
docker exec cupid_redis redis-cli INFO stats | findstr ops_per_sec

# Watch live activity
docker exec -it cupid_redis redis-cli MONITOR
# Run for 30 seconds, look for slow patterns
```

### Scenario 4: "I want to see what's in the cache during development"

Quick Python script for ad-hoc inspection:

```python
# scripts/inspect_redis.py
import asyncio
from redis.asyncio import Redis


async def explore():
    r = Redis(host="localhost", port=6379, decode_responses=True)

    # Find all trends keys
    keys = await r.keys("trends:*")
    print(f"Found {len(keys)} trends keys\n")

    # Inspect each
    for key in keys[:10]:  # cap at 10 for sanity
        ttl = await r.ttl(key)
        value = await r.get(key)
        size = len(value) if value else 0
        print(f"Key: {key}")
        print(f"  TTL:   {ttl}s")
        print(f"  Size:  {size} bytes")
        print(f"  Value: {value[:120]}...\n")

    await r.aclose()


if __name__ == "__main__":
    asyncio.run(explore())
```

Run with:
```powershell
python scripts/inspect_redis.py
```

### Scenario 5: "I deployed new ranking logic but users still see old results"

After a deploy, cached responses still reflect the old logic. Force a cache refresh:

```powershell
# Bust ALL trends cache entries (forces every user to recompute)
docker exec cupid_redis redis-cli --scan --pattern "trends:user:*" | \
  xargs docker exec cupid_redis redis-cli DEL

# Or nuclear option for dev environment
docker exec cupid_redis redis-cli FLUSHDB
```

This is the cache invalidation step. **You must do this after deploying changes that affect cached output.** Otherwise users see old logic for up to 10 minutes.

---

## 10. Common Pitfalls and Anti-Patterns

### Pitfall 1: Treating Cache as Source of Truth

❌ **Wrong:**
```python
data = await redis.get("user:123")
if data is None:
    raise ValueError("User not found")  # WRONG — cache miss isn't "not found"
```

✅ **Right:**
```python
data = await redis.get("user:123")
if data is None:
    data = await db.fetch_user(123)
    await redis.set("user:123", data, ex=300)
```

The cache can disappear at any time (eviction, restart, manual delete). Always have a recompute path.

### Pitfall 2: Forgetting TTLs

❌ **Wrong:**
```python
await redis.set("trends:user:abc", value)    # NO TTL — lives forever
```

✅ **Right:**
```python
await redis.set("trends:user:abc", value, ex=600)
```

A key without a TTL is a memory leak. Eventually Redis fills up and starts evicting *other* keys. Always set TTL unless you have a deliberate reason not to.

### Pitfall 3: Caching Without Namespacing

❌ **Wrong:**
```python
await redis.set("abc123", value)    # what does "abc123" mean?
```

✅ **Right:**
```python
await redis.set("trends:user:abc123", value)
```

Without prefixes, you'll have collisions when you add new caches. Always namespace by feature.

### Pitfall 4: Using `KEYS *` in Production

❌ **Wrong:**
```python
keys = await redis.keys("trends:user:*")    # blocks Redis if many keys
```

✅ **Right:**
```python
async for key in redis.scan_iter(match="trends:user:*"):
    ...
```

`KEYS` blocks the entire Redis server while scanning. Fine for dev with hundreds of keys. Catastrophic in production with millions.

### Pitfall 5: Not Handling Cache Failures

❌ **Wrong:**
```python
data = json.loads(await redis.get("user:123"))   # crashes if Redis is down
```

✅ **Right:**
```python
try:
    raw = await redis.get("user:123")
    data = json.loads(raw) if raw else None
except Exception as exc:
    logger.warning("Cache read failed: %s", exc)
    data = None
```

A Redis outage should slow you down, not break you.

### Pitfall 6: Stale Cache After Code Changes

You deploy new ranking logic. Users still see old rankings for 10 minutes. **This is correct behavior** but surprises people. Always invalidate the cache as part of your deploy process when changing cached logic.

### Pitfall 7: Caching Personal Data Insecurely

❌ **Wrong:**
```python
await redis.set("user:abc", json.dumps({"password": "...", "ssn": "..."}))
```

Redis isn't designed for sensitive data. Don't cache passwords, payment info, or PII unless you've thought through encryption.

---

## 11. Future Use Cases for Redis in Cupid

As the project grows, these are natural places to add Redis caching:

### Phase 2 — User Sessions
Cache decoded JWT user objects to avoid hitting Postgres on every request.

```
Key:   session:{jwt_id}
Value: serialized User object
TTL:   matches JWT expiry
```

### Phase 3 — Composer Output Cache
If a user generates content for the same prompt twice, cache the LLM result.

```
Key:   composer:{hash(prompt + persona)}
Value: 3 generated variants
TTL:   1 hour
```

This saves real money on LLM API calls.

### Phase 4 — Rate Limiting
Track API requests per user per minute to prevent abuse.

```
Key:   ratelimit:user:{user_id}
Value: counter (incremented per request)
TTL:   60 seconds
```

Redis's `INCR` operation is atomic — perfect for counters.

### Phase 5 — Pub/Sub for Real-Time Updates
When ingestion completes, notify connected websockets to refresh.

```
PUBLISH trends:updated "{}"
```

Redis Streams or Pub/Sub channels enable this without polling.

### Phase 6 — Distributed Locks
When multiple Celery workers might try to ingest the same source, use a Redis lock.

```python
async with redis_lock("ingest:technology", timeout=300):
    await ingest_category("technology")
```

---

## Quick Reference Card

```
─────────────────────────────────────────────────────
  CONNECT
─────────────────────────────────────────────────────
docker exec -it cupid_redis redis-cli

─────────────────────────────────────────────────────
  INSPECT
─────────────────────────────────────────────────────
KEYS trends:user:*           # find keys
GET trends:user:abc          # read value
TTL trends:user:abc          # seconds until expiry
DBSIZE                       # total keys

─────────────────────────────────────────────────────
  CLEAR (when needed)
─────────────────────────────────────────────────────
DEL trends:user:abc          # one key
FLUSHDB                      # ALL keys (dev only!)

─────────────────────────────────────────────────────
  WATCH LIVE
─────────────────────────────────────────────────────
MONITOR                      # see every command in real-time

─────────────────────────────────────────────────────
  CHECK HEALTH
─────────────────────────────────────────────────────
PING                         # → PONG
INFO memory | findstr used   # memory usage
```

---

## TL;DR

- **Redis is a fast, expiring, network-accessible dict** that stores precomputed results.
- Cupid uses **cache-aside pattern**: read cache → on miss, compute → write cache → return.
- Current keys: `trends:user:*` with 10-minute TTL.
- **TTL handles cleanup automatically.** No cron jobs needed.
- **Cache failures must degrade gracefully** — service runs without Redis, just slower.
- Use `redis-cli` inside Docker for debugging. `KEYS`, `GET`, `TTL`, `DEL`, `MONITOR` cover 90% of needs.
- **Always namespace keys.** Always set TTLs. Always wrap reads in try/except.
- After deploying changes to cached logic, **bust the cache** so users see new behavior.

This is the foundation. Everything else is variations on these patterns.