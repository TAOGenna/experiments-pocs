# v6 — Robots.txt, User-Agent, and Domain Scope

**Blog concept**: the blog enforces full robots.txt compliance, uses an informative User-Agent string with contact info, and limits the crawl to a seed list of top ~1M domains (from Cisco + Cloudflare datasets). This is about **correctness, ethics, and blast radius reduction**.

**Blog detail**: robots.txt content is cached per domain with an expiration timestamp. The fetcher uses an LRU cache for domain metadata to reduce Redis load.

## What you're building

A robots.txt-aware crawler that respects `Disallow` rules, caches robots files, limits itself to an allowlist of domains, and identifies itself properly.

## Specs

### Robots.txt

- Before crawling any URL on a new domain, fetch and parse `https://{domain}/robots.txt`
- Use Python's `urllib.robotparser.RobotFileParser` (stdlib — no need to reinvent)
- Cache the parsed robots per domain with a TTL (default 24 hours)
- If robots.txt returns 4xx: treat as "allow all"
- If robots.txt returns 5xx or times out: treat as "disallow all" (conservative)
- If a URL is disallowed, skip it and log the skip
- Track: `robots_fetched`, `robots_cache_hits`, `urls_skipped_by_robots`

### User-Agent

- Set a descriptive User-Agent: `MyCrawler/0.6 (+https://github.com/yourname/webcrawler; contact@example.com)`
- Use this User-Agent both for robots.txt checks and for page fetches

### Domain scope

- Accept an allowlist file: one domain per line (start with 100 domains)
- Only crawl URLs whose domain is in the allowlist
- Accept a denylist file: domains to never crawl (e.g., `facebook.com`, `login.gov`)
- Links to non-allowlisted domains are discovered but not followed — log them as `skipped_out_of_scope`

## Deliverables

1. `main.py` — robots-aware, scoped crawler
2. `allowlist.txt` — your seed domain list (100+ domains)
3. `denylist.txt` — domains to block
4. Logs showing:
   - robots.txt fetches (should happen once per domain, then cache hits)
   - URLs skipped due to robots rules (with the rule that matched)
   - URLs skipped due to scope (not in allowlist)
5. Stats: `robots_fetched`, `robots_cache_hits`, `cache_hit_rate`, `urls_blocked_by_robots`, `urls_out_of_scope`
6. Answer these questions in your README:
   - What fraction of the top 100 domains have a robots.txt? What fraction disallow significant paths?
   - How much does robots.txt fetching + parsing add to per-domain latency? (it's a one-time cost per domain)
   - Why does the blog limit to top 1M domains? What problems do long-tail domains cause? (hint: spam, honeypots, infinite URL spaces)
   - Why does the blog say "DNS didn't come up at all"? What's the connection to seed-list scoping?

## Key concepts to internalize

- **Robots.txt is a social contract.** Ignoring it doesn't just violate etiquette — many sites block or rate-limit crawlers that ignore it.
- **Caching robots.txt is essential.** Without caching, you'd fetch robots.txt before every page on a domain. With caching + TTL, it's ~1 extra fetch per domain per day.
- **Scope reduction is a design choice, not a limitation.** The blog deliberately chose top 1M domains. This eliminates DNS amplification, honeypot traps, and infinite-depth link farms.
- **Long-tail domains are dangerous.** Auto-generated sites, SEO spam farms, and calendar pages can generate infinite unique URLs. An allowlist is a circuit breaker.
