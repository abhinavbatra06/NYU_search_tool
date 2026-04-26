"""
Faculty Website Crawler
- Crawls depth 0 and 1
- Downloads CV PDFs
- Stores JSON per faculty for RAG pipeline
- Creates crawl log and Excel summary
"""

import yaml
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import pandas as pd
from pathlib import Path
import time
import re
import json
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional
import hashlib

# Paths
CONFIG_PATH = Path(__file__).parent.parent / "config" / "faculty.yaml"
HTML_PAGES_DIR = Path(__file__).parent.parent / "config" / "HTML_pages"
DATA_DIR = Path(__file__).parent.parent / "data"
FACULTY_DIR = DATA_DIR / "faculty"
CRAWL_LOG_PATH = DATA_DIR / "crawl_log.json"

# Settings
MAX_DEPTH = 1
DELAY = 0.5
REQUEST_TIMEOUT = 15

# CV/PDF patterns (fixed to catch cv_, cv-, etc.)
CV_PATTERNS = [
    r'cv[_\-\.]', r'[_\-\.]cv[_\-\.]', r'[_\-\.]cv$', r'^cv$',
    r'resume', r'vitae', r'curriculum',
]

# Skip domains
SKIP_DOMAINS = [
    'twitter.com', 'x.com', 'linkedin.com', 'facebook.com', 'instagram.com',
    'youtube.com', 'nytimes.com', 'washingtonpost.com', 'bbc.com', 'cnn.com',
    'theguardian.com', 'wsj.com', 'forbes.com', 'medium.com',
]

# Academic profile domains
ACADEMIC_PROFILE_DOMAINS = {
    'scholar.google.com': 'Google Scholar',
    'orcid.org': 'ORCID',
    'researchgate.net': 'ResearchGate',
    'papers.ssrn.com': 'SSRN',
    'ssrn.com': 'SSRN',
    'semanticscholar.org': 'Semantic Scholar',
    'arxiv.org': 'arXiv',
    'pubmed.ncbi.nlm.nih.gov': 'PubMed',
}


@dataclass
class PageData:
    url: str
    title: str
    content: str
    depth: int
    page_type: str
    word_count: int
    crawled_at: str
    links_found: int
    error: Optional[str] = None


@dataclass 
class PDFData:
    url: str
    local_path: str
    detected_as: str
    size_kb: int
    downloaded_at: str


@dataclass
class FacultyData:
    faculty_id: str
    faculty_name: str
    homepage: str
    crawled_at: str
    pages: list
    pdfs: list
    external_profiles: list
    errors: list


def load_faculty_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config.get('faculty', [])


def generate_faculty_id(url: str) -> str:
    """Generate unique ID from URL."""
    parsed = urlparse(url)
    domain = parsed.netloc.replace('.', '_').replace('-', '_')
    path = parsed.path.strip('/').replace('/', '_').replace('-', '_').replace('.html', '').replace('.htm', '')
    
    if path:
        return f"{domain}_{path}"
    return domain


def get_base_path(url: str) -> str:
    """Get the base path for internal link detection."""
    parsed = urlparse(url)
    path = parsed.path.rstrip('/')
    if path.endswith('.html') or path.endswith('.htm'):
        path = '/'.join(path.split('/')[:-1])
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def fetch_page(url: str) -> tuple[Optional[BeautifulSoup], Optional[str], Optional[str]]:
    """Fetch a page. Returns (soup, html, error)."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        
        content_type = r.headers.get('content-type', '')
        if 'text/html' not in content_type and 'application/xhtml' not in content_type:
            return None, None, f"Non-HTML: {content_type}"
        
        return BeautifulSoup(r.text, 'html.parser'), r.text, None
    except requests.exceptions.Timeout:
        return None, None, "Timeout"
    except requests.exceptions.ConnectionError:
        return None, None, "Connection failed"
    except requests.exceptions.HTTPError as e:
        return None, None, f"HTTP {e.response.status_code}"
    except Exception as e:
        return None, None, str(e)[:100]


def download_pdf(url: str, save_path: Path) -> tuple[bool, int, Optional[str]]:
    """Download a PDF. Returns (success, size_kb, error)."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    try:
        r = requests.get(url, headers=headers, timeout=30, stream=True)
        r.raise_for_status()
        
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(save_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        
        size_kb = save_path.stat().st_size // 1024
        return True, size_kb, None
    except Exception as e:
        return False, 0, str(e)[:100]


def extract_text(soup: BeautifulSoup) -> str:
    """Extract clean text from HTML."""
    for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
        element.decompose()
    
    text = soup.get_text(separator=' ', strip=True)
    text = re.sub(r'\s+', ' ', text)
    return text


def get_page_title(soup: BeautifulSoup) -> str:
    """Extract page title."""
    if soup.title and soup.title.string:
        return soup.title.string.strip()[:200]
    h1 = soup.find('h1')
    if h1:
        return h1.get_text(strip=True)[:200]
    return "(no title)"


def detect_page_type(url: str, text: str) -> str:
    """Detect page type from URL and content."""
    url_lower = url.lower()
    text_lower = text.lower()[:2000]
    
    if re.search(r'/(publications?|papers?|articles?)(/|$|\?)', url_lower):
        return "publications"
    if re.search(r'/(research|projects?)(/|$|\?)', url_lower):
        return "research"
    if re.search(r'/(about|bio|profile)(/|$|\?)', url_lower):
        return "bio"
    if re.search(r'/(teaching|courses?)(/|$|\?)', url_lower):
        return "teaching"
    if re.search(r'/(news|blog|posts?)(/|$|\?)', url_lower):
        return "news"
    if re.search(r'/(contact)(/|$|\?)', url_lower):
        return "contact"
    
    # Content-based detection
    if 'publication' in text_lower or 'et al' in text_lower:
        return "publications"
    if 'my research' in text_lower or 'i study' in text_lower:
        return "research"
    if 'i am' in text_lower and 'professor' in text_lower:
        return "bio"
    
    return "general"


def is_cv_link(url: str, link_text: str) -> bool:
    """Check if link is a CV/resume PDF."""
    url_lower = url.lower()
    text_lower = link_text.lower()
    
    if not url_lower.endswith('.pdf'):
        return False
    
    combined = url_lower + ' ' + text_lower
    return any(re.search(p, combined) for p in CV_PATTERNS)


def is_internal_link(url: str, base_path: str) -> bool:
    """Check if URL is internal to the faculty site."""
    return url.startswith(base_path)


def is_skip_domain(url: str) -> bool:
    """Check if URL should be skipped."""
    domain = urlparse(url).netloc.lower()
    return any(skip in domain for skip in SKIP_DOMAINS)


def get_academic_profile_type(url: str) -> Optional[str]:
    """Check if URL is an academic profile."""
    domain = urlparse(url).netloc.lower()
    for profile_domain, profile_name in ACADEMIC_PROFILE_DOMAINS.items():
        if profile_domain in domain:
            return profile_name
    return None


def extract_links(soup: BeautifulSoup, current_url: str) -> list[dict]:
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
        
        link_text = a.get_text(strip=True)[:100]
        links.append({'url': full_url, 'text': link_text})
    
    return links


def crawl_faculty(name: str, homepage_url: str, faculty_id: str) -> FacultyData:
    """Crawl a single faculty's website."""
    print(f"\n{'='*60}")
    print(f"Crawling: {name}")
    print(f"Homepage: {homepage_url}")
    print(f"ID: {faculty_id}")
    print('='*60)
    
    base_path = get_base_path(homepage_url)
    faculty_dir = FACULTY_DIR / faculty_id
    
    # Clear old data before crawling
    if faculty_dir.exists():
        import shutil
        shutil.rmtree(faculty_dir)
    
    faculty_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir = faculty_dir / "pdfs"
    
    pages = []
    pdfs = []
    external_profiles = []
    errors = []
    
    visited = set()
    queue = [(homepage_url, 0)]
    cv_urls_found = set()
    profile_urls_found = set()
    
    while queue:
        url, depth = queue.pop(0)
        url = url.rstrip('/')
        
        if url in visited:
            continue
        if depth > MAX_DEPTH:
            continue
        
        visited.add(url)
        
        print(f"  [Depth {depth}] {url[:70]}...")
        
        soup, raw_html, error = fetch_page(url)
        time.sleep(DELAY)
        
        now = datetime.now().isoformat()
        
        if error:
            print(f"    ERROR: {error}")
            errors.append({
                'url': url,
                'error': error,
                'timestamp': now
            })
            continue
        
        # Extract links FIRST (before extract_text modifies soup)
        links = extract_links(soup, url)
        
        # Extract content (this modifies soup via decompose)
        title = get_page_title(soup)
        content = extract_text(soup)
        page_type = detect_page_type(url, content)
        word_count = len(content.split())
        
        print(f"    Title: {title[:50]}... | {word_count} words | {len(links)} links")
        
        # Save page
        pages.append(PageData(
            url=url,
            title=title,
            content=content,
            depth=depth,
            page_type=page_type,
            word_count=word_count,
            crawled_at=now,
            links_found=len(links)
        ))
        
        # Process links
        for link in links:
            link_url = link['url']
            link_text = link['text']
            
            # Skip if already processed
            if link_url.rstrip('/') in visited:
                continue
            
            # Check for CV PDFs
            if is_cv_link(link_url, link_text) and link_url not in cv_urls_found:
                cv_urls_found.add(link_url)
                print(f"    📄 CV found: {link_url[:60]}...")
                
                # Download PDF
                pdf_filename = f"cv_{hashlib.md5(link_url.encode()).hexdigest()[:8]}.pdf"
                pdf_path = pdf_dir / pdf_filename
                
                success, size_kb, pdf_error = download_pdf(link_url, pdf_path)
                
                if success:
                    print(f"       Downloaded: {size_kb} KB")
                    pdfs.append(PDFData(
                        url=link_url,
                        local_path=f"pdfs/{pdf_filename}",
                        detected_as="CV",
                        size_kb=size_kb,
                        downloaded_at=datetime.now().isoformat()
                    ))
                else:
                    print(f"       Download failed: {pdf_error}")
                    errors.append({
                        'url': link_url,
                        'error': f"PDF download: {pdf_error}",
                        'timestamp': datetime.now().isoformat()
                    })
            
            # Check for academic profiles
            profile_type = get_academic_profile_type(link_url)
            if profile_type and link_url not in profile_urls_found:
                profile_urls_found.add(link_url)
                print(f"    🎓 {profile_type}: {link_url[:60]}...")
                external_profiles.append({
                    'type': profile_type,
                    'url': link_url
                })
            
            # Queue internal links for depth 1
            if depth < MAX_DEPTH:
                if is_internal_link(link_url, base_path) and not is_skip_domain(link_url):
                    if not link_url.lower().endswith(('.pdf', '.doc', '.docx', '.ppt', '.pptx', '.zip')):
                        queue.append((link_url, depth + 1))
    
    return FacultyData(
        faculty_id=faculty_id,
        faculty_name=name,
        homepage=homepage_url,
        crawled_at=datetime.now().isoformat(),
        pages=[asdict(p) for p in pages],
        pdfs=[asdict(p) for p in pdfs],
        external_profiles=external_profiles,
        errors=errors
    )


def save_faculty_data(data: FacultyData):
    """Save faculty data to JSON."""
    faculty_dir = FACULTY_DIR / data.faculty_id
    faculty_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = faculty_dir / "pages.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(asdict(data), f, indent=2, ensure_ascii=False)
    
    print(f"  Saved: {output_path}")


# ============================================================
# SAVED HTML PARSING (for NYU as.nyu.edu pages)
# ============================================================

def extract_canonical_url(soup: BeautifulSoup) -> str:
    """Extract canonical URL from meta tag."""
    link = soup.find('link', rel='canonical')
    if link and link.get('href'):
        return link['href']
    meta = soup.find('meta', property='og:url')
    if meta and meta.get('content'):
        return meta['content']
    return ""


def extract_nyu_faculty_name(soup: BeautifulSoup) -> str:
    """Extract faculty name from NYU page."""
    if soup.title:
        title = soup.title.get_text(strip=True)
        title = re.sub(r'\s*\|\s*NYU.*$', '', title)
        title = re.sub(r'\s*-\s*NYU.*$', '', title)
        if title and len(title) < 100:
            return title
    h1 = soup.find('h1')
    if h1:
        return h1.get_text(strip=True)[:100]
    return "(unknown)"


def extract_nyu_bio_content(soup: BeautifulSoup) -> str:
    """Extract structured content from NYU faculty page."""
    content_parts = []
    
    # Position/title from lead paragraph
    lead = soup.find('p', class_='lead')
    if lead:
        content_parts.append(lead.get_text(strip=True))
    
    # Main bio wrapper
    wrapper = soup.find('div', class_='bio-wrapper')
    if wrapper:
        articles = wrapper.find_all('article', class_='generic-content')
        for article in articles:
            header = article.find('h2')
            if header:
                content_parts.append(f"\n## {header.get_text(strip=True)}\n")
            content_div = article.find('div', class_='content-wrapper')
            if content_div:
                text = content_div.get_text(separator='\n', strip=True)
                content_parts.append(text)
    
    # Publication lists
    pub_lists = soup.find_all('div', class_='publication-list')
    for pub_list in pub_lists:
        header = pub_list.find('h2')
        if header:
            content_parts.append(f"\n## {header.get_text(strip=True)}\n")
        items = pub_list.find_all('li', class_='publication-list__link')
        for item in items:
            title_el = item.find('div', class_='publication-list__title')
            caption_el = item.find('div', class_='publication-list__caption')
            if title_el:
                content_parts.append(f"- {title_el.get_text(strip=True)}")
            if caption_el:
                content_parts.append(f"  {caption_el.get_text(strip=True)}")
    
    return '\n'.join(content_parts)


def parse_saved_html(html_path: Path) -> Optional[FacultyData]:
    """Parse a saved HTML file into FacultyData."""
    print(f"\n  Parsing HTML: {html_path.name}")
    
    with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
        html = f.read()
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Extract URL and name
    url = extract_canonical_url(soup) or f"file://{html_path}"
    faculty_name = extract_nyu_faculty_name(soup)
    faculty_id = generate_faculty_id(url)
    
    # Extract content
    bio_content = extract_nyu_bio_content(soup)
    
    # Build full content
    full_content = f"# {faculty_name}\n\n{bio_content}"
    word_count = len(full_content.split())
    
    print(f"    Name: {faculty_name}")
    print(f"    URL: {url[:60]}...")
    print(f"    Words: {word_count}")
    
    if word_count < 50:
        print(f"    Warning: Very little content extracted")
    
    page = PageData(
        url=url,
        title=faculty_name,
        content=full_content,
        depth=0,
        page_type="bio",
        word_count=word_count,
        crawled_at=datetime.now().isoformat(),
        links_found=0
    )
    
    return FacultyData(
        faculty_id=faculty_id,
        faculty_name=faculty_name,
        homepage=url,
        crawled_at=datetime.now().isoformat(),
        pages=[asdict(page)],
        pdfs=[],
        external_profiles=[],
        errors=[]
    )


def process_saved_html_files() -> list[FacultyData]:
    """Process all saved HTML files from HTML_pages folder."""
    if not HTML_PAGES_DIR.exists():
        print(f"\nNo HTML_pages folder found at: {HTML_PAGES_DIR}")
        return []
    
    html_files = list(HTML_PAGES_DIR.glob("*.html")) + list(HTML_PAGES_DIR.glob("*.htm"))
    
    if not html_files:
        print(f"\nNo HTML files in: {HTML_PAGES_DIR}")
        return []
    
    print(f"\n{'='*60}")
    print(f"PROCESSING SAVED HTML FILES ({len(html_files)} files)")
    print('='*60)
    
    results = []
    for html_path in html_files:
        try:
            faculty = parse_saved_html(html_path)
            if faculty:
                save_faculty_data(faculty)
                results.append(faculty)
        except Exception as e:
            print(f"    ERROR: {e}")
    
    return results


def update_crawl_log(run_data: dict):
    """Update the crawl log."""
    if CRAWL_LOG_PATH.exists():
        with open(CRAWL_LOG_PATH, 'r') as f:
            log = json.load(f)
    else:
        log = {"runs": []}
    
    log["runs"].append(run_data)
    
    with open(CRAWL_LOG_PATH, 'w') as f:
        json.dump(log, f, indent=2)


def create_excel_report(all_faculty_data: list[FacultyData], run_id: str):
    """Create Excel summary report."""
    report_path = DATA_DIR / f"crawl_report_{run_id}.xlsx"
    
    # Run summary
    run_summary = [{
        'Run ID': run_id,
        'Timestamp': datetime.now().isoformat(),
        'Faculty Crawled': len(all_faculty_data),
        'Total Pages': sum(len(f.pages) for f in all_faculty_data),
        'Total PDFs': sum(len(f.pdfs) for f in all_faculty_data),
        'Total Errors': sum(len(f.errors) for f in all_faculty_data),
    }]
    
    # Faculty summary
    faculty_summary = []
    for f in all_faculty_data:
        depth_0 = len([p for p in f.pages if p['depth'] == 0])
        depth_1 = len([p for p in f.pages if p['depth'] == 1])
        profiles = ', '.join([p['type'] for p in f.external_profiles]) or '-'
        
        faculty_summary.append({
            'Faculty Name': f.faculty_name,
            'ID': f.faculty_id,
            'Homepage': f.homepage,
            'Pages (Depth 0)': depth_0,
            'Pages (Depth 1)': depth_1,
            'Total Pages': len(f.pages),
            'CVs Found': len(f.pdfs),
            'Academic Profiles': profiles,
            'Errors': len(f.errors),
        })
    
    # All pages
    all_pages = []
    for f in all_faculty_data:
        for p in f.pages:
            all_pages.append({
                'Faculty': f.faculty_name,
                'URL': p['url'],
                'Title': p['title'][:80],
                'Depth': p['depth'],
                'Page Type': p['page_type'],
                'Word Count': p['word_count'],
                'Crawled At': p['crawled_at'],
            })
    
    # PDFs
    all_pdfs = []
    for f in all_faculty_data:
        for p in f.pdfs:
            all_pdfs.append({
                'Faculty': f.faculty_name,
                'URL': p['url'],
                'Local Path': p['local_path'],
                'Type': p['detected_as'],
                'Size (KB)': p['size_kb'],
            })
    
    # Errors
    all_errors = []
    for f in all_faculty_data:
        for e in f.errors:
            all_errors.append({
                'Faculty': f.faculty_name,
                'URL': e['url'],
                'Error': e['error'],
                'Timestamp': e['timestamp'],
            })
    
    # Write Excel
    with pd.ExcelWriter(report_path, engine='openpyxl') as writer:
        pd.DataFrame(run_summary).to_excel(writer, sheet_name='Run Summary', index=False)
        pd.DataFrame(faculty_summary).to_excel(writer, sheet_name='Faculty Summary', index=False)
        pd.DataFrame(all_pages).to_excel(writer, sheet_name='All Pages', index=False)
        pd.DataFrame(all_pdfs).to_excel(writer, sheet_name='PDFs Downloaded', index=False)
        pd.DataFrame(all_errors).to_excel(writer, sheet_name='Errors', index=False)
    
    print(f"\nExcel report: {report_path}")


def main():
    print("="*60)
    print("FACULTY WEBSITE CRAWLER")
    print("="*60)
    
    start_time = datetime.now()
    run_id = start_time.strftime("%Y-%m-%d_%H%M%S")
    
    # Create directories
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    FACULTY_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load faculty
    faculty_list = load_faculty_config()
    print(f"\nLoaded {len(faculty_list)} faculty members")
    
    # Crawl each faculty from YAML
    all_faculty_data = []
    
    for faculty in faculty_list:
        name = faculty.get('name', 'Unknown')
        url = faculty.get('url', '')
        
        if not url:
            print(f"\nSkipping {name} - no URL")
            continue
        
        faculty_id = generate_faculty_id(url)
        
        try:
            data = crawl_faculty(name, url, faculty_id)
            save_faculty_data(data)
            all_faculty_data.append(data)
        except Exception as e:
            print(f"  CRITICAL ERROR: {e}")
    
    # Process saved HTML files (NYU as.nyu.edu pages)
    html_faculty_data = process_saved_html_files()
    all_faculty_data.extend(html_faculty_data)
    
    # Create reports
    end_time = datetime.now()
    duration = end_time - start_time
    
    run_data = {
        'run_id': run_id,
        'started_at': start_time.isoformat(),
        'completed_at': end_time.isoformat(),
        'duration_seconds': duration.total_seconds(),
        'faculty_count': len(all_faculty_data),
        'pages_crawled': sum(len(f.pages) for f in all_faculty_data),
        'pdfs_downloaded': sum(len(f.pdfs) for f in all_faculty_data),
        'errors': sum(len(f.errors) for f in all_faculty_data),
    }
    
    update_crawl_log(run_data)
    create_excel_report(all_faculty_data, run_id)
    
    # Summary
    print("\n" + "="*60)
    print("CRAWL COMPLETE")
    print("="*60)
    print(f"Duration: {duration}")
    print(f"Faculty: {run_data['faculty_count']}")
    print(f"Pages: {run_data['pages_crawled']}")
    print(f"PDFs: {run_data['pdfs_downloaded']}")
    print(f"Errors: {run_data['errors']}")
    print(f"\nData saved to: {FACULTY_DIR}")


if __name__ == "__main__":
    main()
