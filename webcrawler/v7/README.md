# v7 — Probabilistic Dedup with Bloom Filters

**Blog concept**: the blog uses a Bloom filter for "seen URLs" to reduce memory and speed up lookups. A Bloom filter is a probabilistic data structure: it can tell you "definitely not seen" or "probably seen" — it has false positives but **never false negatives**.

**Blog insight**: *"Small probability of false positives... acceptable because the crawl is a sample."* The crawler doesn't need to visit every page — it's sampling the web. Losing a few URLs to false positives is fine.

## What you're building

Replace the `visited: set[str]` with a Bloom filter. Understand the tradeoffs by running it alongside the exact set and comparing.

## Specs

### Part A: Bloom filter from scratch

Build a minimal Bloom filter (don't use a library yet):
- Parameters: `m` (bit array size), `k` (number of hash functions)
- Operations: `add(url)`, `might_contain(url) → bool`
- Use `mmh3` (MurmurHash3) or `hashlib` to generate k hash values from one input
- **Sizing formula**: for n items and desired false positive rate p:
  ```
  m = -(n * ln(p)) / (ln(2))^2
  k = (m / n) * ln(2)
  ```

### Part B: Empirical validation

- Generate a synthetic dataset: 1M random URL strings
- Insert 500K of them into the Bloom filter
- Test all 1M: the 500K inserted should all return True, the other 500K should mostly return False
- Measure the empirical false positive rate
- Compare with the theoretical rate for your chosen m and k
- Produce a table:
  ```
  target_fpr | m (bits) | k  | empirical_fpr | memory_mb | set_memory_mb
  0.1        | ...      | ...| ...           | ...       | ...
  0.01       | ...      | ...| ...           | ...       | ...
  0.001      | ...      | ...| ...           | ...       | ...
  ```

### Part C: Integrate into crawler

- Replace `visited` set with the Bloom filter in your crawler
- Keep the exact set running **in parallel** (for comparison, not for production)
- After a crawl of N pages, report:
  - URLs the Bloom filter rejected that the set would have allowed (false positives → missed pages)
  - Memory usage: Bloom filter vs. set
  - Lookup time: Bloom filter vs. set (use `timeit`)

## Deliverables

1. `bloom.py` — your Bloom filter implementation
2. `benchmark_bloom.py` — synthetic validation (Part B)
3. Results table (false positive rates, memory comparison)
4. Updated `main.py` with Bloom filter integrated
5. Answer these questions in your README:
   - For 10M URLs at FPR=0.01, how much memory does the Bloom filter use vs. a Python set?
   - Why are false positives acceptable but false negatives would be catastrophic? (hint: false negative = revisit = politeness violation + wasted work)
   - Could you use a Bloom filter for the *frontier* (URLs to visit) instead of just visited? Why or why not?
   - What happens to the false positive rate as the filter fills up? At what load factor does it become useless?

## Key concepts to internalize

- **Probabilistic data structures trade accuracy for space.** A set is exact but grows linearly with items. A Bloom filter is fixed-size but has false positives.
- **The math is simple and trustworthy.** Given n and p, you can calculate exactly how many bits you need. And the empirical rate matches the theory.
- **For sampling workloads, "probably correct" is enough.** The crawler samples the web — missing 1% of URLs to false positives doesn't meaningfully affect the result.
- **Memory is the hidden constraint.** At billion-URL scale, a Python set of URL strings would consume 100+ GB. A Bloom filter at FPR=0.01 uses ~1.2 GB for 1 billion items.
