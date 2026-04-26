"""
Faculty Website Explorer
Crawls faculty homepages, finds subpages, and outputs an Excel report for analysis.

Output: data/crawl_report.xlsx with sheets:
  - Summary: One row per faculty (status, page count, etc.)
  - All Pages: Every page found across all faculty sites
  - Errors: Any failed URLs with error details
"""

import yaml
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import pandas as pd
from pathlib import Path
import time
from dataclasses import dataclass
from typing import Optional
import re

# Playwright for JS-rendered sites
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("Warning: Playwright not installed. JS-rendered sites (as.nyu.edu) won't work.")
    print("Install with: pip install playwright && playwright install chromium")

# Configuration
CONFIG_PATH = Path(__file__).parent.parent / "config" / "faculty.yaml"
OUTPUT_PATH = Path(__file__).parent.parent / "data" / "crawl_report.xlsx"
MAX_PAGES_PER_SITE = 15  # Limit for exploration
REQUEST_TIMEOUT = 10
DELAY_BETWEEN_REQUESTS = 0.5  # Be polite

# Domains that need JavaScript rendering
JS_RENDERED_DOMAINS = ['as.nyu.edu', 'nyu.edu/faculty']


@dataclass
class PageInfo:
    faculty_name: str
    url: str
    status: str  # "success", "error", "skipped"
    error_message: Optional[str]
    page_title: Optional[str]
    text_length: Optional[int]
    link_count: Optional[int]
    internal_links: Optional[list]
    external_links: Optional[list]
    has_publications_keywords: bool
    has_research_keywords: bool
    has_bio_keywords: bool
    depth: int
    content: Optional[str] = None  # Actual text content


def load_faculty_config():
    """Load faculty list from YAML config."""
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config.get('faculty', [])


def get_domain(url: str) -> str:
    """Extract domain from URL for comparison."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def is_internal_link(link: str, base_domain: str) -> bool:
    """Check if link is internal to the site."""
    if not link:
        return False
    if link.startswith('#') or link.startswith('mailto:') or link.startswith('javascript:'):
        return False
    
    parsed = urlparse(link)
    if not parsed.netloc:  # Relative URL
        return True
    
    link_domain = f"{parsed.scheme}://{parsed.netloc}"
    return link_domain == base_domain


def is_crawlable_link(url: str) -> bool:
    """Filter out non-HTML resources."""
    skip_extensions = ['.pdf', '.doc', '.docx', '.ppt', '.pptx', '.zip', '.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mp3']
    lower_url = url.lower()
    return not any(lower_url.endswith(ext) for ext in skip_extensions)


def detect_page_type(text: str, url: str) -> dict:
    """Detect content type using keyword patterns."""
    text_lower = text.lower()
    url_lower = url.lower()
    
    pub_keywords = ['publication', 'paper', 'journal', 'conference', 'proceedings', 
                    'arxiv', 'doi', 'et al', 'forthcoming', 'in press']
    research_keywords = ['research', 'project', 'interest', 'work on', 'study', 'lab', 'group']
    bio_keywords = ['about', 'bio', 'cv', 'curriculum', 'education', 'ph.d', 'professor', 
                    'i am', 'my research', 'i received']
    
    return {
        'has_publications_keywords': any(kw in text_lower or kw in url_lower for kw in pub_keywords),
        'has_research_keywords': any(kw in text_lower or kw in url_lower for kw in research_keywords),
        'has_bio_keywords': any(kw in text_lower or kw in url_lower for kw in bio_keywords),
    }


def needs_js_rendering(url: str) -> bool:
    """Check if URL requires JavaScript rendering."""
    return any(domain in url for domain in JS_RENDERED_DOMAINS)


def fetch_page_playwright(url: str) -> tuple[Optional[BeautifulSoup], Optional[str]]:
    """Fetch a page using Playwright (for JS-rendered sites)."""
    if not PLAYWRIGHT_AVAILABLE:
        return None, "Playwright not installed"
    
    try:
        with sync_playwright() as p:
            # Use user's actual Chrome with their cookies/session
            # Close Chrome first if it's open!
            import os
            chrome_path = os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\User Data')
            
            print(f"    [JS] Using your Chrome profile (close Chrome first!)")
            
            browser = p.chromium.launch_persistent_context(
                user_data_dir=chrome_path,
                channel="chrome",  # Use installed Chrome
                headless=False,
                viewport={'width': 1920, 'height': 1080},
            )
            
            page = browser.new_page()
            
            # Navigate
            print(f"    [JS] Navigating to: {url}")
            page.goto(url, wait_until="load", timeout=60000)
            
            # Wait for page to fully render
            print(f"    [JS] Waiting 10 seconds for content...")
            page.wait_for_timeout(10000)
            
            html = page.content()
            
            print(f"    [JS] HTML length: {len(html)} chars")
            
            # Save raw HTML for debugging
            debug_path = Path(__file__).parent.parent / "data" / "debug_page.html"
            with open(debug_path, 'w', encoding='utf-8') as f:
                f.write(html)
            print(f"    [JS] Saved raw HTML to: {debug_path}")
            
            browser.close()
        
        soup = BeautifulSoup(html, 'html.parser')
        return soup, None
        
    except Exception as e:
        return None, f"Playwright error: {str(e)}"


def fetch_page(url: str) -> tuple[Optional[BeautifulSoup], Optional[str]]:
    """Fetch a page and return parsed HTML or error."""
    
    # Use Playwright for JS-rendered sites
    if needs_js_rendering(url):
        print(f"    [JS] Using Playwright for: {url[:60]}...")
        return fetch_page_playwright(url)
    
    # Use requests for regular sites
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        response.raise_for_status()
        
        # Check if it's HTML
        content_type = response.headers.get('content-type', '')
        if 'text/html' not in content_type and 'application/xhtml' not in content_type:
            return None, f"Non-HTML content: {content_type}"
        
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup, None
        
    except requests.exceptions.Timeout:
        return None, "Timeout"
    except requests.exceptions.ConnectionError:
        return None, "Connection failed"
    except requests.exceptions.HTTPError as e:
        return None, f"HTTP {e.response.status_code}"
    except Exception as e:
        return None, str(e)


def extract_links(soup: BeautifulSoup, base_url: str, base_domain: str) -> tuple[list, list]:
    """Extract and categorize links from page."""
    internal = []
    external = []
    
    for a in soup.find_all('a', href=True):
        href = a['href'].strip()
        
        # Skip empty or anchor-only links
        if not href or href == '#':
            continue
        
        # Resolve relative URLs
        full_url = urljoin(base_url, href)
        
        # Clean up URL (remove fragments)
        parsed = urlparse(full_url)
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if parsed.query:
            clean_url += f"?{parsed.query}"
        
        if is_internal_link(full_url, base_domain):
            if is_crawlable_link(clean_url) and clean_url not in internal:
                internal.append(clean_url)
        else:
            if clean_url not in external:
                external.append(clean_url)
    
    return internal, external


def get_page_text(soup: BeautifulSoup) -> str:
    """Extract visible text from page."""
    # Remove script and style elements
    for element in soup(['script', 'style', 'nav', 'footer', 'header']):
        element.decompose()
    
    text = soup.get_text(separator=' ', strip=True)
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text)
    return text


def crawl_faculty_site(faculty_name: str, homepage_url: str) -> list[PageInfo]:
    """Crawl a faculty site and return info about all pages found."""
    pages = []
    visited = set()
    queue = [(homepage_url, 0)]  # (url, depth)
    base_domain = get_domain(homepage_url)
    
    print(f"  Crawling {faculty_name}...")
    
    while queue and len(visited) < MAX_PAGES_PER_SITE:
        url, depth = queue.pop(0)
        
        # Normalize URL
        url = url.rstrip('/')
        
        if url in visited:
            continue
        visited.add(url)
        
        # Fetch page
        soup, error = fetch_page(url)
        time.sleep(DELAY_BETWEEN_REQUESTS)
        
        if error:
            pages.append(PageInfo(
                faculty_name=faculty_name,
                url=url,
                status="error",
                error_message=error,
                page_title=None,
                text_length=None,
                link_count=None,
                internal_links=None,
                external_links=None,
                has_publications_keywords=False,
                has_research_keywords=False,
                has_bio_keywords=False,
                depth=depth,
                content=None
            ))
            continue
        
        # Extract info
        title = soup.title.string.strip() if soup.title and soup.title.string else "(no title)"
        text = get_page_text(soup)
        internal_links, external_links = extract_links(soup, url, base_domain)
        type_markers = detect_page_type(text, url)
        
        pages.append(PageInfo(
            faculty_name=faculty_name,
            url=url,
            status="success",
            error_message=None,
            page_title=title[:100] if title else None,  # Truncate long titles
            text_length=len(text),
            link_count=len(internal_links) + len(external_links),
            internal_links=internal_links,
            external_links=external_links,
            has_publications_keywords=type_markers['has_publications_keywords'],
            has_research_keywords=type_markers['has_research_keywords'],
            has_bio_keywords=type_markers['has_bio_keywords'],
            depth=depth,
            content=text[:30000]  # Store content (truncate if huge)
        ))
        
        # Add internal links to queue (only go 2 levels deep)
        if depth < 2:
            for link in internal_links:
                if link not in visited:
                    queue.append((link, depth + 1))
    
    return pages


def create_summary_df(all_pages: list[PageInfo]) -> pd.DataFrame:
    """Create summary DataFrame - one row per faculty."""
    summary = []
    
    faculty_groups = {}
    for page in all_pages:
        if page.faculty_name not in faculty_groups:
            faculty_groups[page.faculty_name] = []
        faculty_groups[page.faculty_name].append(page)
    
    for faculty_name, pages in faculty_groups.items():
        success_pages = [p for p in pages if p.status == "success"]
        error_pages = [p for p in pages if p.status == "error"]
        
        homepage = next((p for p in pages if p.depth == 0), None)
        
        summary.append({
            'Faculty Name': faculty_name,
            'Homepage URL': homepage.url if homepage else '',
            'Homepage Status': homepage.status if homepage else 'not_found',
            'Homepage Error': homepage.error_message if homepage and homepage.status == 'error' else '',
            'Total Pages Found': len(success_pages),
            'Failed Pages': len(error_pages),
            'Has Publications Page': any(p.has_publications_keywords for p in success_pages),
            'Has Research Page': any(p.has_research_keywords for p in success_pages),
            'Has Bio Page': any(p.has_bio_keywords for p in success_pages),
            'Total Text (chars)': sum(p.text_length or 0 for p in success_pages),
            'Crawlable': 'Yes' if success_pages else 'No',
            'Notes': homepage.error_message if homepage and homepage.status == 'error' else ''
        })
    
    return pd.DataFrame(summary)


def create_pages_df(all_pages: list[PageInfo]) -> pd.DataFrame:
    """Create detailed DataFrame - one row per page."""
    rows = []
    for page in all_pages:
        rows.append({
            'Faculty Name': page.faculty_name,
            'URL': page.url,
            'Status': page.status,
            'Error': page.error_message or '',
            'Page Title': page.page_title or '',
            'Depth': page.depth,
            'Text Length': page.text_length or 0,
            'Link Count': page.link_count or 0,
            'Has Publications Keywords': page.has_publications_keywords,
            'Has Research Keywords': page.has_research_keywords,
            'Has Bio Keywords': page.has_bio_keywords,
            'Internal Links': '; '.join(page.internal_links[:5]) if page.internal_links else '',  # First 5
            'External Links Count': len(page.external_links) if page.external_links else 0
        })
    
    return pd.DataFrame(rows)


def create_errors_df(all_pages: list[PageInfo]) -> pd.DataFrame:
    """Create errors DataFrame."""
    errors = [p for p in all_pages if p.status == "error"]
    rows = [{
        'Faculty Name': p.faculty_name,
        'URL': p.url,
        'Error': p.error_message,
        'Depth': p.depth
    } for p in errors]
    
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=['Faculty Name', 'URL', 'Error', 'Depth'])


def create_content_df(all_pages: list[PageInfo]) -> pd.DataFrame:
    """Create content DataFrame - full text dump."""
    rows = []
    for page in all_pages:
        if page.status == "success" and page.content:
            rows.append({
                'Faculty Name': page.faculty_name,
                'URL': page.url,
                'Page Title': page.page_title or '',
                'Depth': page.depth,
                'Content Preview (first 500 chars)': page.content[:500] if page.content else '',
                'Full Content': page.content or ''
            })
    return pd.DataFrame(rows)


def create_links_df(all_pages: list[PageInfo]) -> pd.DataFrame:
    """Create discovered links DataFrame - all links found."""
    rows = []
    for page in all_pages:
        if page.status == "success":
            # Internal links
            if page.internal_links:
                for link in page.internal_links:
                    rows.append({
                        'Faculty Name': page.faculty_name,
                        'Found On Page': page.url,
                        'Link URL': link,
                        'Link Type': 'Internal',
                        'Crawled': 'Yes' if any(p.url.rstrip('/') == link.rstrip('/') for p in all_pages) else 'No'
                    })
            # External links
            if page.external_links:
                for link in page.external_links:
                    rows.append({
                        'Faculty Name': page.faculty_name,
                        'Found On Page': page.url,
                        'Link URL': link,
                        'Link Type': 'External',
                        'Crawled': 'No'
                    })
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=['Faculty Name', 'Found On Page', 'Link URL', 'Link Type', 'Crawled'])


def main():
    print("=" * 60)
    print("Faculty Website Explorer")
    print("=" * 60)
    
    # Load config
    faculty_list = load_faculty_config()
    print(f"\nLoaded {len(faculty_list)} faculty members from config\n")
    
    # Crawl each site
    all_pages = []
    for faculty in faculty_list:
        name = faculty.get('name', 'Unknown')
        url = faculty.get('url', '')
        
        if not url:
            print(f"  Skipping {name} - no URL")
            continue
        
        pages = crawl_faculty_site(name, url)
        all_pages.extend(pages)
        
        success = len([p for p in pages if p.status == "success"])
        errors = len([p for p in pages if p.status == "error"])
        print(f"    Found {success} pages, {errors} errors")
    
    # Create output directory
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # Create DataFrames
    summary_df = create_summary_df(all_pages)
    pages_df = create_pages_df(all_pages)
    errors_df = create_errors_df(all_pages)
    content_df = create_content_df(all_pages)
    links_df = create_links_df(all_pages)
    
    # Write to Excel
    print(f"\nWriting report to {OUTPUT_PATH}...")
    with pd.ExcelWriter(OUTPUT_PATH, engine='openpyxl') as writer:
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        pages_df.to_excel(writer, sheet_name='All Pages', index=False)
        content_df.to_excel(writer, sheet_name='Content', index=False)
        links_df.to_excel(writer, sheet_name='All Links', index=False)
        errors_df.to_excel(writer, sheet_name='Errors', index=False)
    
    # Print quick summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total faculty: {len(faculty_list)}")
    print(f"Crawlable: {len(summary_df[summary_df['Crawlable'] == 'Yes'])}")
    print(f"Not crawlable: {len(summary_df[summary_df['Crawlable'] == 'No'])}")
    print(f"Total pages found: {len([p for p in all_pages if p.status == 'success'])}")
    print(f"Total errors: {len([p for p in all_pages if p.status == 'error'])}")
    print(f"\nReport saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
