# Goal: fetch a single URL, parse <a> links, print normalized URLs.
# Learn: URL normalization basics, HTML parsing surface.
# Success: given a page, you extract links deterministically (no duplicates after normalization).

import posixpath
import requests
from urllib.parse import urlparse, urljoin, urlunparse

from bs4 import BeautifulSoup

ALLOWED_SCHEMES = {"http", "https"}
DEFAULT_PORTS = {"http": 80, "https": 443}


def normalize(url: str) -> str:
    parsed = urlparse(url)

    # Scheme and host are case-insensitive per RFC
    scheme = parsed.scheme.lower()
    hostname = parsed.hostname.lower() if parsed.hostname else ""

    # Strip default port (:80 for http, :443 for https)
    port = parsed.port
    if port == DEFAULT_PORTS.get(scheme):
        port = None
    netloc = f"{hostname}:{port}" if port else hostname

    # Collapse . and .. segments in path
    path = posixpath.normpath(parsed.path) if parsed.path else "/"
    # normpath strips the trailing slash and turns "" into ".", fix both
    if path == ".":
        path = "/"
    # Preserve trailing slash from original if path had one (except root which already has it)
    if parsed.path.endswith("/") and not path.endswith("/"):
        path += "/"

    # Reassemble without fragment
    return urlunparse((scheme, netloc, path, parsed.params, parsed.query, ""))


def parse_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for tag in soup.find_all("a", href=True):
        absolute = urljoin(base_url, tag["href"])
        if urlparse(absolute).scheme in ALLOWED_SCHEMES:
            links.append(normalize(absolute))
    return links


def fetch_and_extract(url: str):
    r = requests.get(url)
    # r.url is the final URL after any redirects — correct base for resolving relative hrefs
    links = parse_links(r.text, r.url)
    unique_links = sorted(set(links))
    for link in unique_links:
        print(link)


fetch_and_extract("https://taogenna.github.io")
