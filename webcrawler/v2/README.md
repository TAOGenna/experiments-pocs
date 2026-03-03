# v2 — Per-Domain Politeness

**Blog concept**: *"The domain is the unit of scheduling."* This is the single most important architectural insight from the blog. You don't have one big queue — you have one queue **per domain**, and a scheduler that decides which domain to fetch from next.

**Blog numbers**: the crawler used a **70-second minimum delay** between requests to the same domain. Despite this, it sustained ~950 pages/sec because it was crawling from **millions of domains in parallel**.

## What you're building

Replace the single FIFO frontier from v1 with per-domain queues and a time-based scheduler. The crawler should never hit the same domain faster than a configurable delay D.

## Specs

- Data structures:
  ```
  frontiers: dict[str, deque[str]]    # domain → queue of URLs
  ready_heap: MinHeap[(float, str)]   # (next_allowed_time, domain)
  visited: set[str]
  ```
- Scheduler loop:
  1. Pop the domain with the earliest `next_allowed_time` from the heap
  2. If `next_allowed_time` is in the future, **sleep until then**
  3. Pop one URL from that domain's queue
  4. Fetch and parse it
  5. For each new link: extract domain, add to `frontiers[domain]`; if domain is new, push it onto `ready_heap` with `next_allowed_time = now`
  6. Push the fetched domain back onto `ready_heap` with `next_allowed_time = now + D`
  7. If the domain's queue is empty, don't push it back
- Configurable delay D (default: 2 seconds for testing — the blog uses 70s at scale)
- Seed with at least 10 URLs **across different domains**
- Still synchronous (one fetch at a time) — that's intentional for this step

## Deliverables

1. `main.py` — the scheduler + per-domain frontier
2. Logs showing timestamp + domain + URL for each fetch — you must be able to visually verify no domain appears twice within D seconds
3. Terminal stats: `domains_seen`, `domains_with_remaining_urls`, `pages_fetched`, `pages/sec`
4. Answer these questions in your README:
   - With 1 concurrent fetcher and D=2s, what's the **theoretical maximum pages/sec** as a function of the number of active domains?
   - Why is throughput limited by the number of domains, not by network speed?
   - What happens when most domains in the heap have `next_allowed_time` in the future? (preview: this is why v3 exists)

## Key concepts to internalize

- **Politeness converts a network-bound problem into a scheduling problem.** You have spare bandwidth but can't use it on any single domain.
- **Throughput = min(concurrency, active_domains) / D.** With 1 fetcher and D=2s, you need at least 1 domain fetched every cycle. With 100 concurrent fetchers, you need 100 ready domains.
- **The heap is the scheduler.** This pattern (min-heap of next-allowed timestamps) is the same one the blog uses via Redis sorted sets.

## What this does NOT handle (yet)

- Only 1 fetch at a time (throughput is terrible)
- No async/concurrency
- No robots.txt
- No persistence
