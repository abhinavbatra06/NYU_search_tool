"""
Quick sitemap checker for all faculty websites
"""

import yaml
import requests
from pathlib import Path
from urllib.parse import urlparse

CONFIG_PATH = Path(__file__).parent.parent / "config" / "faculty.yaml"

# Common sitemap locations to check
SITEMAP_PATHS = [
    "sitemap.xml",
    "sitemap_index.xml",
    "wp-sitemap.xml",        # WordPress native (5.5+)
    "sitemap/sitemap.xml",
    "robots.txt",            # Often contains sitemap reference
]

def load_faculty():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config.get('faculty', [])

def get_base_url(url: str) -> str:
    """Get base URL (homepage)"""
    parsed = urlparse(url)
    # For wp.nyu.edu/name/ style, keep the path
    path = parsed.path.rstrip('/')
    if path:
        return f"{parsed.scheme}://{parsed.netloc}{path}/"
    return f"{parsed.scheme}://{parsed.netloc}/"

def check_url(url: str) -> tuple[bool, str]:
    """Check if URL exists and what type"""
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            content_type = r.headers.get('content-type', '')
            if 'xml' in content_type or '<urlset' in r.text[:500] or '<sitemapindex' in r.text[:500]:
                return True, "SITEMAP"
            elif 'Sitemap:' in r.text:
                return True, "ROBOTS (has sitemap ref)"
            else:
                return True, "EXISTS (not sitemap)"
        return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, str(e)[:30]

def main():
    faculty = load_faculty()
    
    print("=" * 80)
    print("SITEMAP CHECK FOR ALL FACULTY")
    print("=" * 80)
    
    results = []
    
    for f in faculty:
        name = f.get('name', 'Unknown')
        url = f.get('url', '')
        base = get_base_url(url)
        
        print(f"\n{name}")
        print(f"  Base: {base}")
        
        found_sitemap = False
        for path in SITEMAP_PATHS:
            check_url_full = base + path
            exists, status = check_url(check_url_full)
            
            if exists and "SITEMAP" in status:
                print(f"  ✓ {path} -> {status}")
                found_sitemap = True
                results.append({
                    'name': name,
                    'base_url': base,
                    'sitemap_url': check_url_full,
                    'status': status
                })
                break
            elif exists and "ROBOTS" in status:
                print(f"  ~ {path} -> {status}")
                results.append({
                    'name': name,
                    'base_url': base,
                    'sitemap_url': check_url_full,
                    'status': status
                })
                found_sitemap = True
                break
        
        if not found_sitemap:
            print(f"  ✗ No sitemap found")
            results.append({
                'name': name,
                'base_url': base,
                'sitemap_url': None,
                'status': 'NO SITEMAP'
            })
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    with_sitemap = [r for r in results if r['sitemap_url']]
    without = [r for r in results if not r['sitemap_url']]
    
    print(f"\nWith sitemap: {len(with_sitemap)}")
    for r in with_sitemap:
        print(f"  - {r['name']}: {r['sitemap_url']}")
    
    print(f"\nNo sitemap: {len(without)}")
    for r in without:
        print(f"  - {r['name']}")

if __name__ == "__main__":
    main()
