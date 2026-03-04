# Goal: BFS crawl from seed URLs, stop after N pages.
# Learn: frontier management, dedup via visited set, BFS depth tracking.
# Success: no URL is fetched twice; stats show frontier growth and domain distribution.

import posixpath
import time
from collections import deque
from urllib.parse import urlparse, urljoin, urlunparse

import requests
from bs4 import BeautifulSoup

ALLOWED_SCHEMES = {"http", "https"}
DEFAULT_PORTS = {"http": 80, "https": 443}

SEEDS = [
    "https://en.wikipedia.org/wiki/Web_crawler",
    "https://docs.python.org/3/",
    "https://codeforces.com",
]
MAX_PAGES = 50


def normalize(url: str) -> str:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    hostname = parsed.hostname.lower() if parsed.hostname else ""
    port = parsed.port
    if port == DEFAULT_PORTS.get(scheme):
        port = None
    netloc = f"{hostname}:{port}" if port else hostname
    path = posixpath.normpath(parsed.path) if parsed.path else "/"
    if path == ".":
        path = "/"
    if parsed.path.endswith("/") and not path.endswith("/"):
        path += "/"
    return urlunparse((scheme, netloc, path, parsed.params, parsed.query, ""))


def parse_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for tag in soup.find_all("a", href=True):
        absolute = urljoin(base_url, tag["href"])
        if urlparse(absolute).scheme in ALLOWED_SCHEMES:
            links.append(normalize(absolute))
    return links


def crawl(seeds: list[str], max_pages: int):
    frontier = deque()
    visited: set[str] = set()
    # depth tracks the BFS level for each URL
    depth: dict[str, int] = {}

    session = requests.Session()
    session.headers["User-Agent"] = "v1-toy-crawler/0.1 (educational project)"

    # Stats
    errors = 0
    same_domain_links = 0
    external_links = 0

    # Seed the frontier
    for url in seeds:
        normalized = normalize(url)
        if normalized not in visited:
            frontier.append(normalized)
            visited.add(normalized)
            depth[normalized] = 0

    pages_fetched = 0
    start = time.time()

    while frontier and pages_fetched < max_pages:
        url = frontier.popleft()
        current_depth = depth[url]

        try:
            r = session.get(url, timeout=10)
            r.raise_for_status()
        except Exception as e:
            print(f"  ERROR: {e}")
            errors += 1
            continue

        pages_fetched += 1
        links = parse_links(r.text, r.url)
        unique_new = set(links) - visited

        # Count same-domain vs external
        current_domain = urlparse(url).netloc
        for link in links:
            if urlparse(link).netloc == current_domain:
                same_domain_links += 1
            else:
                external_links += 1

        # Add unseen links to frontier
        for link in unique_new:
            visited.add(link)
            frontier.append(link)
            depth[link] = current_depth + 1

        print(
            f"[depth={current_depth}] [{pages_fetched}/{max_pages}] {url} "
            f"— {len(links)} links, {len(unique_new)} new | frontier: {len(frontier)}"
        )

    elapsed = time.time() - start

    print("\n--- Stats ---")
    print(f"Pages fetched:      {pages_fetched}")
    print(f"Unique URLs seen:   {len(visited)}")
    print(f"Errors:             {errors}")
    print(f"Elapsed:            {elapsed:.2f}s")
    print(f"Same-domain links:  {same_domain_links}")
    print(f"External links:     {external_links}")
    total = same_domain_links + external_links
    if total:
        print(f"Same-domain ratio:  {same_domain_links / total:.1%}")
    print(f"Frontier remaining: {len(frontier)}")


if __name__ == "__main__":
    crawl(SEEDS, MAX_PAGES)
