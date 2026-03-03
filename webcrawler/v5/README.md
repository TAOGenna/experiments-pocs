# v5 — Parser Benchmarking + Truncation

**Blog concept**: the blog discovered that **parser choice and page truncation are massive performance levers**. Switching from `lxml` to `selectolax` (which wraps the Lexbor C parser) and truncating pages before parsing were key optimizations.

**Blog numbers**:
- Mean page size in 2025: **242 KB** (up from 51 KB in 2012)
- Median page size: **138 KB**
- Parser throughput: ~160 pages/sec per parser process with selectolax
- Truncation threshold: **250 KB** (above mean, near 2x median)

## What you're building

A benchmark harness that measures parse performance across different parsers and truncation thresholds. Then integrate the best combination into your crawler.

## Specs

### Part A: Benchmark harness

- Collect a corpus: use your v4 crawler to save 200+ raw HTML pages to disk (varying sizes)
- Parsers to benchmark:
  - `beautifulsoup4` with `html.parser` (pure Python)
  - `beautifulsoup4` with `lxml` backend
  - `lxml.html` directly
  - `selectolax` (Lexbor)
- Truncation thresholds: `None` (full page), `500KB`, `250KB`, `100KB`, `50KB`
- For each (parser, threshold) combination, measure:
  - **parse time per page** (median, p95, p99)
  - **links extracted** (to check correctness — are you losing links by truncating?)
  - **parse time per KB of input**
- Output a table:
  ```
  parser       | trunc  | median_ms | p95_ms | p99_ms | links_found | ms_per_kb
  -------------|--------|-----------|--------|--------|-------------|----------
  bs4+html.p   | None   | ...       | ...    | ...    | ...         | ...
  bs4+lxml     | None   | ...       | ...    | ...    | ...         | ...
  lxml.html    | None   | ...       | ...    | ...    | ...         | ...
  selectolax   | None   | ...       | ...    | ...    | ...         | ...
  bs4+html.p   | 250KB  | ...       | ...    | ...    | ...         | ...
  ...
  ```

### Part B: Integrate into crawler

- Replace BeautifulSoup with the fastest parser in your v4 pipeline
- Add truncation before parsing (configurable threshold)
- Measure pipeline throughput before and after

## Deliverables

1. `benchmark.py` — standalone benchmark harness
2. `corpus/` — directory of saved HTML pages (or a script to generate it)
3. Results table (in README or as CSV)
4. Updated `main.py` with fast parser + truncation integrated
5. Answer these questions in your README:
   - How much faster is selectolax vs BeautifulSoup? (expect 5–20x)
   - At what truncation threshold do you start losing a significant number of links?
   - The blog truncates at 250KB. Based on your data, is that a good threshold? Would you choose differently?
   - Why does parse time per KB matter more than parse time per page?
   - If pages keep getting bigger (they will), what breaks first in your pipeline?

## Key concepts to internalize

- **Parser choice is not a micro-optimization — it's a pipeline-defining decision.** A 10x faster parser means 10x fewer parser processes needed.
- **Truncation is trading recall for throughput.** You lose some links in the tail of huge pages, but most links are in headers/navs/footers (early in the HTML).
- **Measure, don't guess.** The blog didn't assume lxml was fast enough — they benchmarked, found it wasn't, and switched.
- **Page size is a variable, not a constant.** The web is getting heavier. Your system must handle the distribution, not the average.
