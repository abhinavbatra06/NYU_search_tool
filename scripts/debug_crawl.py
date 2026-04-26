"""
Debug crawler - Deep crawl of a single faculty site
Shows ALL discovered URLs
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time

# Target
HOMEPAGE = "https://wp.nyu.edu/bonikowski/"
MAX_PAGES = 50  # Higher limit for deep exploration
DELAY = 0.3

def fetch(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        return BeautifulSoup(r.text, 'html.parser'), None
    except Exception as e:
        return None, str(e)

def get_all_links(soup, current_url):
    """Get ALL links from a page"""
    links = []
    for a in soup.find_all('a', href=True):
        href = a['href'].strip()
        if not href or href.startswith('#') or href.startswith('mailto:') or href.startswith('javascript:'):
            continue
        full_url = urljoin(current_url, href)
        # Remove fragments
        full_url = full_url.split('#')[0]
        links.append(full_url)
    return list(set(links))  # Dedupe

def main():
    print(f"Deep crawling: {HOMEPAGE}\n")
    print("=" * 80)
    
    visited = set()
    queue = [(HOMEPAGE, 0)]
    all_discovered = {}  # url -> {found_on, depth}
    
    while queue and len(visited) < MAX_PAGES:
        url, depth = queue.pop(0)
        url = url.rstrip('/')
        
        if url in visited:
            continue
        
        print(f"[Depth {depth}] Fetching: {url}")
        visited.add(url)
        
        soup, error = fetch(url)
        time.sleep(DELAY)
        
        if error:
            print(f"  ERROR: {error}")
            continue
        
        links = get_all_links(soup, url)
        print(f"  Found {len(links)} links")
        
        for link in links:
            if link not in all_discovered:
                all_discovered[link] = {'found_on': url, 'depth': depth + 1}
            
            # Only queue links that look related to this site
            # Check if it's under the same base path
            if link.startswith(HOMEPAGE) and link not in visited:
                queue.append((link, depth + 1))
    
    # Report
    print("\n" + "=" * 80)
    print("CRAWLED PAGES (actually visited):")
    print("=" * 80)
    for i, url in enumerate(sorted(visited), 1):
        print(f"  {i}. {url}")
    
    print(f"\nTotal crawled: {len(visited)}")
    
    print("\n" + "=" * 80)
    print("ALL DISCOVERED LINKS (found but not necessarily crawled):")
    print("=" * 80)
    
    # Group by type
    internal = []
    external = []
    
    for link in sorted(all_discovered.keys()):
        if link.startswith(HOMEPAGE):
            internal.append(link)
        else:
            external.append(link)
    
    print(f"\n--- INTERNAL (start with {HOMEPAGE}): {len(internal)} ---")
    for link in internal:
        crawled = "✓" if link.rstrip('/') in visited or link in visited else " "
        print(f"  [{crawled}] {link}")
    
    print(f"\n--- EXTERNAL: {len(external)} ---")
    for link in external[:30]:  # First 30 only
        print(f"      {link}")
    if len(external) > 30:
        print(f"      ... and {len(external) - 30} more")

if __name__ == "__main__":
    main()
