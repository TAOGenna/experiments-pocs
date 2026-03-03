# v8 — Durable Crawl State

**Blog concept**: the blog uses Redis as a persistent state store. Per-domain frontiers, the domain queue, visited entries, Bloom filter state, and robots.txt caches all live in Redis. If the process crashes, Redis still has the state.

**Blog reality**: *they had to restart mid-crawl* due to memory growth from hot domains (wikipedia, yahoo — frontier queues grew to tens of GB). Crash recovery wasn't theoretical — it was operationally necessary.

## What you're building

Make the crawler's state survive a kill/restart. Start simple (file-based), then optionally move to Redis.

## Specs

### Approach: append-only log + periodic snapshots

The simplest durable state pattern:

1. **Append-only log (WAL)**: every state mutation gets appended to a file
   - `VISITED <url> <timestamp>`
   - `FRONTIER_ADD <domain> <url>`
   - `FRONTIER_POP <domain> <url>`
   - `DOMAIN_SCHEDULE <domain> <next_allowed_time>`
2. **Periodic snapshot**: every S seconds (default 60), write the full state to a snapshot file
   - `snapshot_{timestamp}.json` — contains visited set/Bloom, all frontier queues, scheduler heap
3. **Recovery**: on startup, load the latest snapshot, then replay log entries after that snapshot's timestamp

### What must be persisted

| State | Why |
|-------|-----|
| Visited set / Bloom filter | Avoid re-fetching pages |
| Per-domain frontier queues | Resume crawling where you left off |
| Scheduler heap (next_allowed_time per domain) | Maintain politeness on restart |
| Robots.txt cache | Avoid re-fetching robots on restart |

### What can be reconstructed

| State | How |
|-------|-----|
| Stats counters | Re-derive from log |
| In-flight fetches | Will be lost — re-add URLs to frontier on recovery |
| Parse queue contents | Will be lost — those pages will be re-fetched (acceptable) |

### Test protocol

1. Start a crawl with 100+ seed domains
2. Let it run for 2+ minutes
3. Kill it (`kill -9`, not graceful shutdown)
4. Restart
5. Verify: pages fetched before the kill are NOT re-fetched (check logs)
6. Verify: crawl continues from approximately where it left off
7. Measure: how many pages are "wasted" (re-fetched) after recovery?

## Deliverables

1. `main.py` — crawler with WAL + snapshots
2. `state.py` — state persistence module (save/load/replay)
3. Kill-and-restart test results showing:
   - Pages fetched before kill
   - Pages re-fetched after restart (should be small — only in-flight + post-last-snapshot)
   - Total "waste" as a fraction of total crawl
4. Answer these questions in your README:
   - Why append-only log + snapshots instead of updating a database on every operation?
   - What's the tradeoff in snapshot frequency S? (too often = slow, too rare = more replay on recovery)
   - The blog uses Redis. What does Redis give you that files don't? (hint: atomic operations, concurrent access from multiple processes)
   - What happens if the process crashes *during* a snapshot write? How would you handle this? (hint: write to temp file, atomic rename)

## Key concepts to internalize

- **Durability is about defining what you can afford to lose.** The blog can lose in-flight fetches (they'll be re-fetched). It can NOT lose the visited set (that causes duplicate work and politeness violations).
- **WAL + snapshots is a universal pattern.** Databases (Postgres, SQLite), message queues (Kafka), and games all use this. Fast appends for normal operation, snapshots to bound recovery time.
- **Atomic file operations matter.** A half-written snapshot is worse than no snapshot. Write to a temp file, fsync, then rename.
- **The hot domain problem is real.** Wikipedia's frontier can grow to gigabytes. Durability means persisting that — and recovering it. The blog had to manually exclude hot domains mid-crawl.
