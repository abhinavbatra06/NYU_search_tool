"""
Parse Manually Saved HTML Files
- Reads HTML files from test_html/ folder
- Extracts faculty content from NYU as.nyu.edu pages
- Outputs JSON in same format as crawl.py for pipeline integration
"""

from bs4 import BeautifulSoup
from pathlib import Path
import json
import re
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional
import hashlib

# Paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
FACULTY_DIR = DATA_DIR / "faculty"
HTML_DIR = SCRIPT_DIR.parent / "test_html"


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
class FacultyData:
    faculty_id: str
    faculty_name: str
    homepage: str
    crawled_at: str
    pages: list
    pdfs: list
    external_profiles: list
    errors: list


def generate_faculty_id(url: str) -> str:
    """Generate unique ID from URL."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    domain = parsed.netloc.replace('.', '_').replace('-', '_')
    path = parsed.path.strip('/').replace('/', '_').replace('-', '_').replace('.html', '').replace('.htm', '')
    
    if path:
        return f"{domain}_{path}"
    return domain


def extract_canonical_url(soup: BeautifulSoup) -> str:
    """Extract canonical URL from meta tag."""
    link = soup.find('link', rel='canonical')
    if link and link.get('href'):
        return link['href']
    
    # Fallback: look in og:url
    meta = soup.find('meta', property='og:url')
    if meta and meta.get('content'):
        return meta['content']
    
    return ""


def extract_faculty_name(soup: BeautifulSoup) -> str:
    """Extract faculty name from page."""
    # Title tag
    if soup.title:
        title = soup.title.get_text(strip=True)
        # Clean common suffixes
        title = re.sub(r'\s*\|\s*NYU.*$', '', title)
        title = re.sub(r'\s*-\s*NYU.*$', '', title)
        if title and len(title) < 100:
            return title
    
    # og:title
    meta = soup.find('meta', property='og:title')
    if meta and meta.get('content'):
        return meta['content']
    
    # h1 tag
    h1 = soup.find('h1')
    if h1:
        return h1.get_text(strip=True)[:100]
    
    return "(unknown)"


def extract_title(soup: BeautifulSoup) -> str:
    """Extract position/title from lead paragraph."""
    lead = soup.find('p', class_='lead')
    if lead:
        return lead.get_text(strip=True)
    return ""


def extract_bio_content(soup: BeautifulSoup) -> str:
    """Extract the main bio/about content."""
    # Look for generic-content sections
    content_parts = []
    
    # Main bio text
    wrapper = soup.find('div', class_='bio-wrapper')
    if wrapper:
        articles = wrapper.find_all('article', class_='generic-content')
        for article in articles:
            # Get section header
            header = article.find('h2')
            if header:
                content_parts.append(f"\n## {header.get_text(strip=True)}\n")
            
            # Get content
            content_div = article.find('div', class_='content-wrapper')
            if content_div:
                text = content_div.get_text(separator='\n', strip=True)
                content_parts.append(text)
    
    # Also get publications list
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


def extract_structured_data(soup: BeautifulSoup) -> dict:
    """Extract structured data sections."""
    data = {
        'education': [],
        'research_areas': [],
        'teaching': [],
        'awards': [],
        'publications': [],
        'books': []
    }
    
    # Find all generic-content articles
    articles = soup.find_all('article', class_='generic-content')
    for article in articles:
        header = article.find('h2')
        if not header:
            continue
        
        header_text = header.get_text(strip=True).lower()
        content_div = article.find('div', class_='content-wrapper')
        if not content_div:
            continue
        
        # Determine which section this is
        if 'education' in header_text:
            paras = content_div.find_all('p')
            data['education'] = [p.get_text(strip=True) for p in paras if p.get_text(strip=True)]
        
        elif 'research' in header_text or 'interest' in header_text:
            text = content_div.get_text(strip=True)
            data['research_areas'] = [a.strip() for a in re.split(r'[,;]', text) if a.strip()]
        
        elif 'teaching' in header_text:
            paras = content_div.find_all('p')
            data['teaching'] = [p.get_text(strip=True) for p in paras if p.get_text(strip=True)]
        
        elif 'award' in header_text or 'honor' in header_text:
            paras = content_div.find_all('p')
            data['awards'] = [p.get_text(strip=True) for p in paras if p.get_text(strip=True)]
        
        elif 'publication' in header_text:
            paras = content_div.find_all('p')
            for p in paras:
                text = p.get_text(strip=True)
                if text:
                    data['publications'].append(text)
    
    # Get books from publication-list
    pub_lists = soup.find_all('div', class_='publication-list')
    for pub_list in pub_lists:
        header = pub_list.find('h2')
        if header and 'book' in header.get_text(strip=True).lower():
            items = pub_list.find_all('li', class_='publication-list__link')
            for item in items:
                caption = item.find('div', class_='publication-list__caption')
                if caption:
                    data['books'].append(caption.get_text(strip=True))
    
    return data


def parse_html_file(html_path: Path) -> Optional[FacultyData]:
    """Parse a single HTML file and extract faculty data."""
    print(f"\nParsing: {html_path.name}")
    
    with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
        html = f.read()
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Extract URL
    url = extract_canonical_url(soup)
    if not url:
        print(f"  Warning: No canonical URL found")
        url = f"file://{html_path}"
    
    print(f"  URL: {url}")
    
    # Extract faculty info
    faculty_name = extract_faculty_name(soup)
    faculty_id = generate_faculty_id(url)
    position_title = extract_title(soup)
    bio_content = extract_bio_content(soup)
    structured = extract_structured_data(soup)
    
    print(f"  Name: {faculty_name}")
    print(f"  ID: {faculty_id}")
    print(f"  Position: {position_title[:60]}..." if len(position_title) > 60 else f"  Position: {position_title}")
    
    # Build full content for RAG
    full_content_parts = []
    
    # Header info
    full_content_parts.append(f"# {faculty_name}")
    if position_title:
        full_content_parts.append(f"\n{position_title}")
    
    # Bio
    if bio_content:
        full_content_parts.append(f"\n{bio_content}")
    
    # Structured sections
    if structured['education']:
        full_content_parts.append("\n## Education")
        for item in structured['education']:
            full_content_parts.append(f"- {item}")
    
    if structured['research_areas']:
        full_content_parts.append("\n## Research Areas")
        full_content_parts.append(', '.join(structured['research_areas']))
    
    if structured['teaching']:
        full_content_parts.append("\n## Teaching")
        for item in structured['teaching']:
            full_content_parts.append(f"- {item}")
    
    if structured['awards']:
        full_content_parts.append("\n## Awards and Honors")
        for item in structured['awards']:
            full_content_parts.append(f"- {item}")
    
    full_content = '\n'.join(full_content_parts)
    word_count = len(full_content.split())
    
    print(f"  Words extracted: {word_count}")
    
    if word_count < 50:
        print(f"  Warning: Very little content extracted")
    
    # Create PageData
    page = PageData(
        url=url,
        title=faculty_name,
        content=full_content,
        depth=0,
        page_type="bio",
        word_count=word_count,
        crawled_at=datetime.now().isoformat(),
        links_found=0,
        error=None
    )
    
    # Create FacultyData
    faculty = FacultyData(
        faculty_id=faculty_id,
        faculty_name=faculty_name,
        homepage=url,
        crawled_at=datetime.now().isoformat(),
        pages=[asdict(page)],
        pdfs=[],
        external_profiles=[],
        errors=[]
    )
    
    return faculty


def save_faculty_data(faculty: FacultyData):
    """Save faculty data to JSON file."""
    FACULTY_DIR.mkdir(parents=True, exist_ok=True)
    
    output_path = FACULTY_DIR / f"{faculty.faculty_id}.json"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(asdict(faculty), f, indent=2, ensure_ascii=False)
    
    print(f"  Saved: {output_path.name}")
    return output_path


def main():
    print("=" * 60)
    print("PARSE SAVED HTML FILES")
    print("=" * 60)
    
    if not HTML_DIR.exists():
        print(f"\nError: HTML directory not found: {HTML_DIR}")
        print("Create the directory and save HTML files there.")
        return
    
    # Find all HTML files
    html_files = list(HTML_DIR.glob("*.html")) + list(HTML_DIR.glob("*.htm"))
    
    if not html_files:
        print(f"\nNo HTML files found in: {HTML_DIR}")
        return
    
    print(f"\nFound {len(html_files)} HTML file(s)")
    
    results = []
    for html_path in html_files:
        try:
            faculty = parse_html_file(html_path)
            if faculty:
                save_path = save_faculty_data(faculty)
                results.append({
                    'source': html_path.name,
                    'faculty_name': faculty.faculty_name,
                    'faculty_id': faculty.faculty_id,
                    'words': faculty.pages[0]['word_count'] if faculty.pages else 0,
                    'output': save_path.name
                })
        except Exception as e:
            print(f"  Error: {e}")
            results.append({
                'source': html_path.name,
                'error': str(e)
            })
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    success = [r for r in results if 'error' not in r]
    failed = [r for r in results if 'error' in r]
    
    print(f"\nSuccessfully parsed: {len(success)}")
    for r in success:
        print(f"  - {r['faculty_name']}: {r['words']} words")
    
    if failed:
        print(f"\nFailed: {len(failed)}")
        for r in failed:
            print(f"  - {r['source']}: {r['error']}")
    
    print(f"\nOutput directory: {FACULTY_DIR}")
    print("\nNext steps:")
    print("  1. Run chunk_data.py to process the new data")
    print("  2. Run embed_chunks.py to update embeddings")


if __name__ == "__main__":
    main()
