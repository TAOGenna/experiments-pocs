# v9 — Storage Format and I/O Budget

**Blog concept**: the blog stores fetched pages on local NVMe instance storage, not S3. The economics were decisive: S3 PUT costs alone would be $183–$5,183/day depending on page count. Local NVMe is included in the instance price.

**Blog detail**: they considered but didn't implement compression (snappy, zstd) due to time constraints. Storage format was minimal — truncated HTML + metadata.

## What you're building

A storage layer that writes fetched pages and metadata to disk efficiently, with size budgets and optional compression. Then measure whether disk I/O becomes the bottleneck.

## Specs

### Storage format

Each fetched page produces a record:
```
{
  "url": "https://example.com/page",
  "domain": "example.com",
  "fetch_time": "2025-01-15T10:30:00Z",
  "status_code": 200,
  "content_length": 45231,
  "content_type": "text/html",
  "html_path": "data/example.com/abc123.html.zst"
}
```

- Metadata goes to a single JSONL file (one JSON object per line, append-only)
- HTML goes to per-domain directories: `data/{domain}/{hash}.html` (or `.html.zst` if compressed)
- Content hash: first 16 chars of SHA-256 of the URL (for filename)

### Size budgets

- Max stored page size: 250KB (truncate before writing, matching the blog's parse truncation)
- Max total storage: configurable (default 10GB for testing)
- When approaching the limit, stop fetching new pages (graceful shutdown)

### Compression experiment

- Implement three modes: `none`, `gzip`, `zstd`
- For each mode, measure on a 1000-page crawl:
  - Write throughput (pages/sec, MB/sec)
  - Total disk usage
  - Compression ratio
  - CPU overhead of compression

### I/O budget analysis

- Measure your sustained write rate (MB/sec)
- Compare against your disk's capability (run `dd` or `fio` to get baseline sequential write speed)
- Calculate: at your current pages/sec, what's the required write bandwidth? Is disk the bottleneck?
  ```
  required_write_bandwidth = pages_per_sec * avg_stored_page_size
  ```

## Deliverables

1. `storage.py` — storage module (write page, read page, metadata index, compression modes)
2. `main.py` — crawler with storage integrated
3. Compression comparison table:
   ```
   mode  | write_mb_sec | disk_usage_mb | compression_ratio | cpu_overhead_pct
   none  | ...          | ...           | 1.0               | 0%
   gzip  | ...          | ...           | ...               | ...
   zstd  | ...          | ...           | ...               | ...
   ```
4. I/O budget calculation showing: "at X pages/sec with avg Y KB/page, I need Z MB/sec write. My disk does W MB/sec. Headroom = W/Z."
5. Answer these questions in your README:
   - At 950 pages/sec (the blog's rate) with 250KB max page size, what's the worst-case write bandwidth needed?
   - Why did the blog choose instance storage over S3? Calculate the S3 PUT cost for 1 billion pages.
   - When would disk become the bottleneck? How many pages/sec would you need?
   - Is compression worth the CPU cost? The blog didn't implement it — were they right?

## Key concepts to internalize

- **I/O budgets are arithmetic, not guesswork.** You can calculate exactly when disk becomes the bottleneck: `required_bandwidth = throughput * record_size`. If that exceeds your disk's write speed, disk is the bottleneck.
- **Storage economics drive architecture.** S3 is elastic but expensive per operation. Local NVMe is fixed-cost and fast but non-durable and capacity-limited. The blog made the economic choice.
- **Compression trades CPU for disk.** At crawler scale, CPU is already scarce (SSL + parsing). Adding compression CPU cost might hurt more than the disk savings help.
- **JSONL (newline-delimited JSON) is the simplest structured append-only format.** One line = one record. Easy to write, easy to grep, easy to recover from partial writes.
