"""
Link Discovery & Classification Script
Shows what links we CAN crawl using the bucket strategy.
Runs on first 5 professors only.
"""

import yaml
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import pandas as pd
from pathlib import Path
import time
import re

# Paths
CONFIG_PATH = Path(__file__).parent.parent / "config" / "faculty.yaml"
OUTPUT_PATH = Path(__file__).parent.parent / "data" / "link_discovery.xlsx"

# Settings
MAX_FACULTY = 5  # Only first 5
MAX_INTERNAL_PAGES = 30
MAX_NEWS_PAGES = 3
DELAY = 0.3

# Classification patterns
NEWS_PATTERNS = [
    r'/news/', r'/blog/', r'/posts/', r'/press/',
    r'/20\d{2}/', r'/\d{4}/\d{2}/',  # Date patterns like /2024/ or /2024/01/
]

ACADEMIC_PROFILE_DOMAINS = {
    'scholar.google.com': 'Google Scholar',
    'orcid.org': 'ORCID',
    'researchgate.net': 'ResearchGate',
    'papers.ssrn.com': 'SSRN',
    'ssrn.com': 'SSRN',
    'semanticscholar.org': 'Semantic Scholar',
    'arxiv.org': 'arXiv',
    'pubmed.ncbi.nlm.nih.gov': 'PubMed',
    'philpapers.org': 'PhilPapers',
}

CV_PATTERNS = [
    r'\bcv\b', r'\bresume\b', r'\bvitae\b', r'\bcurriculum\b',
]

SKIP_DOMAINS = [
    'twitter.com', 'x.com', 'linkedin.com', 'facebook.com', 'instagram.com',
    'youtube.com', 'nytimes.com', 'washingtonpost.com', 'bbc.com', 'cnn.com',
    'theguardian.com', 'wsj.com', 'forbes.com', 'medium.com',
]

SKIP_PATH_PATTERNS = [
    r'/admissions', r'/apply', r'/contact-us', r'/privacy', r'/terms',
    r'/login', r'/wp-admin', r'/cart', r'/checkout',
]


def load_faculty():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config.get('faculty', [])[:MAX_FACULTY]


def fetch(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        return BeautifulSoup(r.text, 'html.parser'), None
    except Exception as e:
        return None, str(e)


def get_base_path(url: str) -> str:
    """Get the base path for a faculty site."""
    parsed = urlparse(url)
    path = parsed.path.rstrip('/')
    # For paths like /bonikowski, keep /bonikowski
    # For paths like /faculty/name.html, keep /faculty/name (without .html)
    if path.endswith('.html') or path.endswith('.htm'):
        path = '/'.join(path.split('/')[:-1])
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def get_link_text(a_tag) -> str:
    """Get the text of a link."""
    return a_tag.get_text(strip=True).lower()


def classify_link(url: str, link_text: str, base_path: str) -> tuple[str, str]:
    """
    Classify a link into a bucket.
    Returns: (bucket, reason)
    """
    url_lower = url.lower()
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    path = parsed.path.lower()
    
    # Check CV/PDF first (high priority)
    is_pdf = url_lower.endswith('.pdf')
    has_cv_keyword = any(re.search(p, url_lower) or re.search(p, link_text) for p in CV_PATTERNS)
    if is_pdf and has_cv_keyword:
        return 'CV_PDF', 'PDF with CV keyword'
    if has_cv_keyword:
        return 'CV_PDF', 'CV keyword in URL or text'
    
    # Skip domains
    for skip_domain in SKIP_DOMAINS:
        if skip_domain in domain:
            return 'SKIP', f'Skip domain: {skip_domain}'
    
    # Academic profiles
    for profile_domain, profile_name in ACADEMIC_PROFILE_DOMAINS.items():
        if profile_domain in domain:
            return 'ACADEMIC_PROFILE', profile_name
    
    # Skip path patterns
    for pattern in SKIP_PATH_PATTERNS:
        if re.search(pattern, path):
            return 'SKIP', f'Skip path pattern: {pattern}'
    
    # Internal vs external
    if url.startswith(base_path):
        # It's internal - check if news
        for pattern in NEWS_PATTERNS:
            if re.search(pattern, url):
                return 'NEWS_BLOG', f'News pattern: {pattern}'
        return 'INTERNAL', 'Same base path'
    
    # Check if same domain but different path (e.g., other nyu.edu pages)
    base_domain = urlparse(base_path).netloc
    if domain == base_domain:
        return 'SAME_DOMAIN_OTHER', 'Same domain, different section'
    
    # PDF (not CV)
    if is_pdf:
        return 'OTHER_PDF', 'PDF file'
    
    # External - unknown
    return 'EXTERNAL_OTHER', 'External domain'


def extract_links(soup, current_url) -> list[dict]:
    """Extract all links with metadata."""
    links = []
    seen = set()
    
    for a in soup.find_all('a', href=True):
        href = a['href'].strip()
        if not href or href.startswith('#') or href.startswith('mailto:') or href.startswith('javascript:'):
            continue
        
        full_url = urljoin(current_url, href).split('#')[0]
        
        if full_url in seen:
            continue
        seen.add(full_url)
        
        links.append({
            'url': full_url,
            'link_text': get_link_text(a)[:100],
        })
    
    return links


def discover_faculty_links(faculty_name: str, homepage_url: str) -> list[dict]:
    """Discover and classify all links from a faculty's site."""
    print(f"\n{'='*60}")
    print(f"Discovering: {faculty_name}")
    print(f"Homepage: {homepage_url}")
    print('='*60)
    
    base_path = get_base_path(homepage_url)
    print(f"Base path: {base_path}")
    
    all_links = []
    visited = set()
    queue = [(homepage_url, 0, 'homepage')]  # (url, depth, source)
    
    # Counters for limits
    internal_count = 0
    news_count = 0
    
    while queue:
        url, depth, source = queue.pop(0)
        url = url.rstrip('/')
        
        if url in visited:
            continue
        
        # Check limits
        bucket, _ = classify_link(url, '', base_path)
        if bucket == 'INTERNAL' and internal_count >= MAX_INTERNAL_PAGES:
            continue
        if bucket == 'NEWS_BLOG' and news_count >= MAX_NEWS_PAGES:
            continue
        
        visited.add(url)
        
        # Only fetch internal pages and homepage
        if not (url.startswith(base_path) or url == homepage_url):
            continue
        
        print(f"  [Depth {depth}] Fetching: {url[:70]}...")
        soup, error = fetch(url)
        time.sleep(DELAY)
        
        if error:
            print(f"    ERROR: {error}")
            continue
        
        if bucket == 'INTERNAL':
            internal_count += 1
        elif bucket == 'NEWS_BLOG':
            news_count += 1
        
        # Extract links from this page
        links = extract_links(soup, url)
        print(f"    Found {len(links)} links")
        
        for link in links:
            link_url = link['url']
            link_text = link['link_text']
            bucket, reason = classify_link(link_url, link_text, base_path)
            
            all_links.append({
                'faculty_name': faculty_name,
                'found_on': url,
                'depth': depth,
                'url': link_url,
                'link_text': link_text,
                'bucket': bucket,
                'reason': reason,
            })
            
            # Queue internal links for further crawling (depth limit)
            if bucket == 'INTERNAL' and depth < 2 and link_url not in visited:
                queue.append((link_url, depth + 1, url))
            elif bucket == 'NEWS_BLOG' and depth < 1 and news_count < MAX_NEWS_PAGES and link_url not in visited:
                queue.append((link_url, depth + 1, url))
    
    return all_links


def main():
    faculty_list = load_faculty()
    print(f"Processing {len(faculty_list)} faculty members\n")
    
    all_links = []
    
    for faculty in faculty_list:
        name = faculty.get('name', 'Unknown')
        url = faculty.get('url', '')
        
        if not url:
            print(f"Skipping {name} - no URL")
            continue
        
        links = discover_faculty_links(name, url)
        all_links.extend(links)
    
    # Create DataFrames
    df = pd.DataFrame(all_links)
    
    # Summary by bucket
    summary_rows = []
    for faculty in faculty_list:
        name = faculty.get('name')
        faculty_links = [l for l in all_links if l['faculty_name'] == name]
        
        buckets = {}
        for l in faculty_links:
            bucket = l['bucket']
            buckets[bucket] = buckets.get(bucket, 0) + 1
        
        summary_rows.append({
            'Faculty': name,
            'Internal Pages': buckets.get('INTERNAL', 0),
            'News/Blog': buckets.get('NEWS_BLOG', 0),
            'Academic Profiles': buckets.get('ACADEMIC_PROFILE', 0),
            'CV/PDFs': buckets.get('CV_PDF', 0),
            'Other PDFs': buckets.get('OTHER_PDF', 0),
            'Same Domain Other': buckets.get('SAME_DOMAIN_OTHER', 0),
            'External Other': buckets.get('EXTERNAL_OTHER', 0),
            'Skipped': buckets.get('SKIP', 0),
            'Total Links': len(faculty_links),
        })
    
    summary_df = pd.DataFrame(summary_rows)
    
    # Create separate sheets per bucket
    internal_df = df[df['bucket'] == 'INTERNAL'][['faculty_name', 'url', 'link_text', 'found_on', 'depth']]
    academic_df = df[df['bucket'] == 'ACADEMIC_PROFILE'][['faculty_name', 'url', 'reason', 'link_text']]
    cv_df = df[df['bucket'] == 'CV_PDF'][['faculty_name', 'url', 'link_text', 'reason']]
    news_df = df[df['bucket'] == 'NEWS_BLOG'][['faculty_name', 'url', 'link_text']]
    skip_df = df[df['bucket'] == 'SKIP'][['faculty_name', 'url', 'reason']]
    
    # Write Excel
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*60}")
    print("Writing Excel report...")
    
    with pd.ExcelWriter(OUTPUT_PATH, engine='openpyxl') as writer:
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        internal_df.to_excel(writer, sheet_name='Internal Pages', index=False)
        academic_df.to_excel(writer, sheet_name='Academic Profiles', index=False)
        cv_df.to_excel(writer, sheet_name='CVs & PDFs', index=False)
        news_df.to_excel(writer, sheet_name='News & Blog', index=False)
        skip_df.to_excel(writer, sheet_name='Skipped', index=False)
        df.to_excel(writer, sheet_name='All Links Raw', index=False)
    
    print(f"Saved to: {OUTPUT_PATH}")
    
    # Print summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print('='*60)
    print(summary_df.to_string(index=False))


if __name__ == "__main__":
    main()
