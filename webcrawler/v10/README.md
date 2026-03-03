# v10 — Metrics, Observability, and Bottleneck Hunting

**Blog concept**: the blog exports metrics to a local Prometheus instance per node, with Grafana dashboards. The first fetcher process is designated the "leader" that writes metrics. The author admits the monitoring was imperfect (Grafana unit labels were wrong), but metrics were essential for identifying the memory growth crisis mid-crawl.

**Blog lesson**: without metrics, they wouldn't have caught that certain domain frontiers were growing to tens of gigabytes until OOM killed the process.

## What you're building

An instrumented crawler that exports real-time metrics. You should be able to diagnose any bottleneck (CPU parse, fetch latency, queue depth, disk I/O, domain starvation) from metrics alone, without reading logs.

## Specs

### Metrics to track

| Metric | Type | What it tells you |
|--------|------|-------------------|
| `pages_fetched_total` | Counter | Total progress |
| `pages_per_second` | Gauge | Current throughput |
| `fetch_latency_seconds` | Histogram (p50, p95, p99) | Network + server health |
| `parse_latency_seconds` | Histogram (p50, p95, p99) | Parser performance |
| `parse_queue_depth` | Gauge | Backpressure indicator |
| `frontier_total_urls` | Gauge | How much work remains |
| `domains_active` | Gauge | How many domains have URLs queued |
| `domains_ready` | Gauge | How many domains are ready to fetch now (not rate-limited) |
| `errors_total` | Counter (by type: timeout, dns, http_4xx, http_5xx, parse) | Error rate by category |
| `bloom_filter_checks` | Counter | Dedup activity |
| `bloom_false_positive_estimate` | Gauge | Filter health |
| `bytes_written_total` | Counter | Disk I/O load |
| `robots_cache_hit_rate` | Gauge | Cache effectiveness |

### Output options (pick one or more)

- **Option A: CLI dashboard** — print a summary table every 10 seconds to stdout (simplest)
- **Option B: CSV export** — append metrics to a CSV every 10 seconds, then plot with matplotlib after the crawl
- **Option C: Prometheus** — expose a `/metrics` endpoint using `prometheus_client` library, view in Grafana (most realistic)

### Bottleneck diagnosis exercise

Introduce artificial bottlenecks and see if you can identify them from metrics alone:

1. **Slow parser**: add 50ms sleep to parse — parse_latency should spike, parse_queue should fill
2. **Slow network**: add 500ms sleep to fetch — fetch_latency should spike, parse_queue should drain
3. **Domain starvation**: reduce seed list to 3 domains with D=5s — domains_ready drops to 0, pages/sec flatlines
4. **Disk I/O**: add 20ms sleep to storage writes — bytes_written slows, but does it affect pages/sec? (probably not unless queue fills)

For each scenario, write a 2-sentence diagnosis based only on the metrics.

## Deliverables

1. `metrics.py` — metrics collection and export module
2. `main.py` — fully instrumented crawler
3. Dashboard output (CLI table, CSV+plot, or Prometheus — your choice)
4. Bottleneck diagnosis report: for each of the 4 artificial bottlenecks, show the metrics and your diagnosis
5. Answer these questions in your README:
   - Which single metric is the best early warning for "something is wrong"? (hint: queue depth)
   - Why does the blog use "pages per second" as the top-level health metric?
   - What's the difference between a counter and a gauge? When do you use each?
   - The blog had a memory growth crisis from hot domain frontiers. Which metric would have caught it earliest?

## Key concepts to internalize

- **You can't optimize what you can't measure.** Every performance claim in the blog is backed by a number. Every bottleneck was identified via metrics.
- **Queue depth is the universal bottleneck indicator.** A full queue means the consumer is slow. An empty queue means the producer is slow. This is true for any pipeline.
- **Histograms > averages.** p50 tells you "normal." p99 tells you "worst case." A system with good p50 but terrible p99 has a tail latency problem (often caused by GC pauses or slow DNS).
- **Metrics are for operating, not just debugging.** The blog ran for 25.5 hours. Without metrics, you're flying blind for a full day.
