# Web Crawler — Progressive Build

A progressive, educational build of a web crawler. Each version introduces one core concept from [andrewkchan's billion-page crawl post](https://andrewkchan.dev/posts/crawler.html).

## Concept dependency graph

```
v0 URL normalization + link extraction
│
v1 BFS graph walk + visited set + frontier
│
v2 Per-domain frontiers + time-based scheduler  ← THE key insight
│
├──────────────────────┐
v3 Async I/O           v6 Robots.txt + scope
│                      │
v4 Fetch→Parse         │
│  pipeline            │
│                      │
v5 Parser bench +      │
│  truncation          │
│                      │
├──────────────────────┘
│
v7 Bloom filter dedup
│
v8 Durable state (WAL + snapshots)
│
v9 Storage format + I/O budget
│
v10 Metrics + observability
```

v3–v5 (performance) and v6 (correctness) are independent tracks — you can do them in either order. Everything else is sequential.

## Concept map: blog → version

| Blog concept | Version | One-sentence summary |
|---|---|---|
| Link extraction, URL canonicalization | v0 | Fetch one page, extract and normalize links |
| Frontier, BFS, dedup by visited set | v1 | Crawl N pages without revisiting |
| Per-domain queues, rate-limit scheduling | v2 | The domain is the unit of scheduling |
| asyncio, 6000+ concurrent connections | v3 | I/O concurrency via async, throughput curves |
| 9 fetchers : 6 parsers, bounded queue | v4 | Producer-consumer pipeline with backpressure |
| selectolax vs lxml, 250KB truncation | v5 | Parser choice + truncation as performance levers |
| robots.txt caching, top-1M seed list | v6 | Ethics, scope, and blast radius reduction |
| Bloom filter for seen URLs | v7 | Probabilistic dedup: trade accuracy for memory |
| Redis state, crash mid-crawl | v8 | WAL + snapshots for crash recovery |
| NVMe vs S3 economics, compression | v9 | Storage I/O budget analysis |
| Prometheus, Grafana, memory growth crisis | v10 | You can't optimize what you can't measure |

## Blog numbers to keep in mind

- **1 billion pages** in **25.5 hours** for **$462**
- **~950 pages/sec** sustained throughput
- **70-second** minimum delay between same-domain requests
- **25% of CPU** spent on SSL handshakes
- Mean page size: **242 KB** (up from 51 KB in 2012)
- **6,000–7,000** concurrent async connections per fetcher process
- **9 fetchers + 6 parsers** per node (12 nodes total)
- Bloom filter for dedup — false positives acceptable because the crawl is a sample

## Status

- [x] v0 — Hello crawler
- [ ] v1 — BFS frontier
- [ ] v2 — Per-domain politeness
- [ ] v3 — Async fetchers
- [ ] v4 — Fetch→Parse pipeline
- [ ] v5 — Parser benchmarking
- [ ] v6 — Robots.txt + scope
- [ ] v7 — Bloom filter
- [ ] v8 — Durable state
- [ ] v9 — Storage + I/O
- [ ] v10 — Metrics + observability
