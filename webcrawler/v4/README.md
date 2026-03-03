# v4 — Fetch→Parse Pipeline with Backpressure

**Blog concept**: the blog separates fetching and parsing into **distinct process pools** with a queue between them. The fetcher's job is to download HTML; the parser's job is to extract links and store results. This is a producer-consumer pipeline.

**Blog numbers**: 9 fetcher processes + 6 parser processes per node. The ratio matters — parsing is CPU-heavier than fetching (per page), so you need fewer parsers but they each max out a core.

## What you're building

Split the crawler into two stages connected by a bounded async queue. The fetcher produces `(url, html)` pairs. The parser consumes them, extracts links, and feeds new URLs back to the scheduler.

## Specs

- Architecture:
  ```
  Scheduler ──▶ Fetcher workers (C concurrent)
                      │
                      ▼
              ┌──────────────┐
              │ parse_queue   │  (asyncio.Queue, maxsize=Q)
              │ bounded to Q  │
              └──────────────┘
                      │
                      ▼
              Parser workers (P concurrent)
                      │
                      ▼
              Scheduler.add_links(new_urls)
  ```
- `parse_queue` is an `asyncio.Queue(maxsize=Q)` where Q is configurable (start with 100)
- When the queue is full, fetchers **block on put** — this is backpressure
- P parser workers consume from the queue
- Simulate slow parsing: add an artificial `await asyncio.sleep(0.05)` in the parser to exaggerate the effect
- Log queue depth periodically (every 5 seconds)
- Measure: pages/sec with and without the artificial parse delay

## Deliverables

1. `main.py` — pipeline crawler with fetch stage, parse stage, bounded queue
2. Queue depth log showing:
   - Without delay: queue stays near-empty (parsers keep up)
   - With delay: queue fills up, fetchers slow down (backpressure working)
3. Throughput comparison: fast parse vs slow parse
4. Answer these questions in your README:
   - What happens if the queue is unbounded and parsers are slow? (memory grows forever)
   - What's the relationship between Q (queue size) and memory usage?
   - If you have C fetchers and P parsers, and each parse takes T_parse seconds while each fetch takes T_fetch seconds, what ratio C:P keeps the pipeline balanced?
   - Why did the blog choose 9 fetchers : 6 parsers (3:2 ratio)? What does that tell you about relative costs?

## Key concepts to internalize

- **Backpressure is how systems avoid running out of memory.** Without it, the fast stage (fetch) outruns the slow stage (parse), and queued work grows without bound.
- **Bounded queues are the mechanism.** `maxsize=Q` means "block the producer when Q items are waiting." This automatically throttles the fast stage.
- **Pipeline balance matters.** If parse is 2x slower per item than fetch, you need ~2x as many parser workers. The blog's 9:6 ratio tells you parsing is ~1.5x the cost of fetching per page.
- **Queue depth is a key metric.** If it's always full → parsers are the bottleneck. Always empty → fetchers are. Oscillating → balanced.

## What this does NOT handle (yet)

- Parsing uses BeautifulSoup (slow) — not yet optimized
- No truncation of large pages
- Still single-process
