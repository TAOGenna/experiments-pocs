# v0 — Hello Web Crawler

Single-URL link extractor. Fetches a page, parses all `<a>` tags, resolves relative hrefs to absolute URLs, normalizes them to a canonical form, and prints the deduplicated set.

## What normalization does

| Step | Example |
|------|---------|
| Resolve relative → absolute | `/about` → `https://example.com/about` |
| Remove fragment | `https://a.com/x#section` → `https://a.com/x` |
| Lowercase scheme + host | `HTTPs://EXAMPLE.com` → `https://example.com` |
| Strip default port | `https://a.com:443/x` → `https://a.com/x` |
| Collapse `.` / `..` in path | `/a/b/../c` → `/a/c` |

## Flow

```mermaid
sequenceDiagram
    participant Main
    participant requests
    participant BeautifulSoup
    participant normalize

    Main->>requests: GET url
    requests-->>Main: response (html + final url after redirects)
    Main->>BeautifulSoup: parse html
    BeautifulSoup-->>Main: all <a href="..."> values
    loop each href
        Main->>Main: urljoin(base_url, href) → absolute URL
        Main->>Main: filter — keep http/https only
        Main->>normalize: absolute URL
        normalize-->>Main: canonical URL (no fragment, lowercase, no default port, clean path)
    end
    Main->>Main: deduplicate via set()
    Main->>Main: print sorted unique links
```

## Run

```bash
uv run main.py
```
