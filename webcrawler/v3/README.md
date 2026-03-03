# v3 — Async Fetchers (I/O Concurrency)

**Blog concept**: the blog runs **6,000–7,000 concurrent async operations per fetcher process** using Python's `asyncio`. The insight: while one request waits for a server to respond, you can start thousands of others. Network I/O is waiting, not working.

**Blog numbers**: each node had 9 fetcher processes. Network utilization was ~8 Gbps out of 25 Gbps available. The bottleneck was **CPU** (SSL handshakes = 25% of CPU), not network.

## What you're building

Convert the synchronous fetcher from v2 into an async fetcher using `asyncio` + `aiohttp`. Keep the per-domain scheduler from v2 intact — but now, instead of fetching one URL at a time, you fetch C URLs concurrently.

## Specs

- Replace `requests` with `aiohttp` (async HTTP client)
- Concurrency parameter C (start with 10, experiment up to 100+)
- The scheduler must still enforce per-domain delay D — concurrency means fetching from **different domains simultaneously**, not blasting one domain
- Architecture:
  ```
  async def worker(id, scheduler):
      while not done:
          url, domain = await scheduler.next()  # blocks until a domain is ready
          html = await fetch(url)
          links = parse_links(html, url)
          scheduler.add_links(links)
          scheduler.release(domain)              # pushes domain back with delay

  # Launch C workers
  await asyncio.gather(*[worker(i, scheduler) for i in range(C)])
  ```
- The scheduler needs a lock or async-safe structure since multiple workers access it
- Measure: pages/sec at C=1, 5, 10, 25, 50, 100
- Seed with 50+ URLs across many domains

## Deliverables

1. `main.py` — async crawler with configurable concurrency
2. A throughput table or chart:
   ```
   C=1:   ~X pages/sec
   C=5:   ~X pages/sec
   C=10:  ~X pages/sec
   C=50:  ~X pages/sec
   C=100: ~X pages/sec
   ```
3. Answer these questions in your README:
   - At what concurrency level does throughput stop increasing? Why?
   - Is the bottleneck network, CPU, or available domains?
   - What happens if you set C=1000 but only have 20 seed domains?
   - The blog mentions SSL handshakes consume 25% of CPU. Can you observe CPU usage increasing with concurrency? (use `time` or `psutil`)

## Key concepts to internalize

- **Async I/O is cooperative multitasking.** Each `await` is a yield point. No OS threads, no context switching cost.
- **Concurrency ≠ parallelism.** asyncio runs on one CPU core. You get I/O overlap, not CPU parallelism. That's fine because fetching is I/O-bound.
- **The scheduler is the bottleneck governor.** Even with C=10000, you can't go faster than "number of ready domains / D". Concurrency only helps if there are enough domains ready to fetch.
- **CPU becomes visible at scale.** SSL, HTML parsing, URL normalization — these eat CPU. The blog found CPU was the actual ceiling, not bandwidth.

## What this does NOT handle (yet)

- Parsing is still inline with fetching (no pipeline separation)
- No backpressure (if parsing is slow, memory grows)
- Still single-process (can't use multiple CPU cores)
