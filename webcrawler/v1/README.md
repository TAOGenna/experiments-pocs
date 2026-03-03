# v1 — Breadth-First Toy Frontier

**Blog concept**: before any optimization, a crawler is just a graph walk. The web is a directed graph (pages → links). BFS explores it level by level.

## What you're building

A crawler that starts from a seed list, explores links breadth-first, and stops after fetching N pages. All state lives in memory.

## Specs

- Input: a list of 3–5 seed URLs and a max page count N (default 50)
- Data structures:
  - `frontier`: a FIFO queue (collections.deque) of URLs to visit
  - `visited`: a set of normalized URLs already fetched
- Loop: pop URL from frontier → fetch → parse links → normalize each → add unseen ones to frontier → repeat until N pages fetched or frontier empty
- Only follow `http`/`https` links
- Reuse `normalize()` and `parse_links()` from v0
- Track and print stats at the end

## Deliverables

1. `main.py` — the crawl loop
2. Terminal output showing:
   - each URL as it's fetched (with depth level)
   - final stats: `pages_fetched`, `unique_links_found`, `errors`, `elapsed_time`
3. Answer these questions in your README:
   - What happens if you seed with a single Wikipedia article? How fast does the frontier grow?
   - Does the crawler ever revisit a page? How do you know?
   - What fraction of discovered links are on the *same domain* as the page they were found on vs. external?

## Key concepts to internalize

- **The frontier is the heart of every crawler.** Everything else (politeness, persistence, sharding) is about managing it.
- **URL normalization is your dedup function.** If normalization is wrong, you revisit pages. If it's too aggressive, you miss pages.
- **BFS vs DFS matters.** BFS gives breadth (many domains), DFS goes deep (one site). Real crawlers want breadth.

## What this does NOT handle (yet)

- No rate limiting (you'll hammer domains)
- No robots.txt
- Synchronous fetching (one page at a time)
- No persistence (crash = start over)
