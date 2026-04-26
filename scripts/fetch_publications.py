"""
Fetch publications from Semantic Scholar API
- Gets structured publication data (title, abstract, year, venue)
- Saves to data/faculty/{id}/publications.json
"""

import yaml
import requests
import json
from pathlib import Path
import time
from datetime import datetime

# Paths
CONFIG_PATH = Path(__file__).parent.parent / "config" / "faculty.yaml"
DATA_DIR = Path(__file__).parent.parent / "data"
FACULTY_DIR = DATA_DIR / "faculty"
PUBLICATIONS_LOG_PATH = DATA_DIR / "publications_log.json"

# Settings
MAX_FACULTY = None  # None = all faculty
DELAY = 1.0  # Be nice to the API
PAPERS_PER_AUTHOR = 50  # Max papers to fetch per author

# Semantic Scholar API
BASE_URL = "https://api.semanticscholar.org/graph/v1"


def load_faculty():
    """Load faculty from YAML config."""
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config.get('faculty', [])


def load_crawled_faculty():
    """Load faculty from crawled data (data/faculty/)."""  
    crawled = []
    if not FACULTY_DIR.exists():
        return crawled
    
    # Check for folder-based structure (faculty_id/pages.json)
    for faculty_dir in FACULTY_DIR.iterdir():
        if faculty_dir.is_dir():
            pages_json = faculty_dir / "pages.json"
            if pages_json.exists():
                try:
                    with open(pages_json, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    crawled.append({
                        'name': data.get('faculty_name', 'Unknown'),
                        'url': data.get('homepage', ''),
                        'faculty_id': data.get('faculty_id', faculty_dir.name),
                        'source': 'crawled'
                    })
                except Exception:
                    pass
    
    # Check for direct JSON files (faculty_id.json) - from HTML parsing
    for json_file in FACULTY_DIR.glob("*.json"):
        if json_file.name == "desktop.ini":
            continue
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            crawled.append({
                'name': data.get('faculty_name', 'Unknown'),
                'url': data.get('homepage', ''),
                'faculty_id': data.get('faculty_id', json_file.stem),
                'source': 'html_parsed'
            })
        except Exception:
            pass
    
    return crawled


def get_all_faculty():
    """Get combined list of faculty from YAML + crawled data."""
    faculty_list = []
    seen_ids = set()
    
    # 1. Load from YAML (with URL)
    yaml_faculty = load_faculty()
    for f in yaml_faculty:
        url = f.get('url', '')
        if url:
            faculty_id = generate_faculty_id(url)
            if faculty_id not in seen_ids:
                seen_ids.add(faculty_id)
                faculty_list.append({
                    'name': f.get('name', 'Unknown'),
                    'url': url,
                    'faculty_id': faculty_id,
                    'source': 'yaml'
                })
    
    # 2. Load from crawled data (HTML_pages, etc.)
    crawled_faculty = load_crawled_faculty()
    for f in crawled_faculty:
        faculty_id = f.get('faculty_id', '')
        if faculty_id and faculty_id not in seen_ids:
            seen_ids.add(faculty_id)
            faculty_list.append(f)
    
    # Apply limit if set
    if MAX_FACULTY:
        return faculty_list[:MAX_FACULTY]
    return faculty_list


def generate_faculty_id(url: str) -> str:
    """Generate unique ID from URL (same logic as crawl.py)."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    domain = parsed.netloc.replace('.', '_').replace('-', '_')
    path = parsed.path.strip('/').replace('/', '_').replace('-', '_').replace('.html', '').replace('.htm', '')
    if path:
        return f"{domain}_{path}"
    return domain


def search_author(name: str) -> dict | None:
    """Search for author by name, return best match."""
    url = f"{BASE_URL}/author/search"
    params = {
        "query": name,
        "limit": 5,
        "fields": "name,affiliations,paperCount,citationCount,hIndex"
    }
    
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        
        if not data.get('data'):
            return None
        
        # Try to find NYU-affiliated author, or take first result
        for author in data['data']:
            affiliations = author.get('affiliations', []) or []
            if any('nyu' in aff.lower() or 'new york university' in aff.lower() for aff in affiliations):
                return author
        
        # Fallback: return first result
        return data['data'][0]
    
    except Exception as e:
        print(f"    Error searching author: {e}")
        return None


def get_author_papers(author_id: str) -> list[dict]:
    """Get papers for an author, sorted by citation count (default)."""
    url = f"{BASE_URL}/author/{author_id}/papers"
    params = {
        "limit": PAPERS_PER_AUTHOR,
        "fields": "title,abstract,year,venue,publicationDate,citationCount,openAccessPdf,authors"
    }
    
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        return data.get('data', [])
    
    except Exception as e:
        print(f"    Error fetching papers: {e}")
        return []


def format_paper(paper: dict) -> dict:
    """Format paper data for storage."""
    authors = paper.get('authors', [])
    author_names = [a.get('name', '') for a in authors[:5]]  # First 5 authors
    if len(authors) > 5:
        author_names.append(f"et al. ({len(authors)} total)")
    
    return {
        'title': paper.get('title', ''),
        'abstract': paper.get('abstract', ''),
        'year': paper.get('year'),
        'venue': paper.get('venue', ''),
        'publication_date': paper.get('publicationDate', ''),
        'citation_count': paper.get('citationCount', 0),
        'authors': author_names,
        'open_access_pdf': paper.get('openAccessPdf', {}).get('url') if paper.get('openAccessPdf') else None,
    }


def fetch_faculty_publications(name: str, faculty_id: str) -> dict:
    """Fetch publications for a faculty member."""
    print(f"\n{'='*60}")
    print(f"Fetching: {name}")
    print(f"ID: {faculty_id}")
    print('='*60)
    
    # Search for author
    print(f"  Searching Semantic Scholar...")
    author = search_author(name)
    time.sleep(DELAY)
    
    if not author:
        print(f"  ❌ Author not found")
        return {
            'faculty_name': name,
            'faculty_id': faculty_id,
            'semantic_scholar_id': None,
            'error': 'Author not found',
            'papers': [],
            'fetched_at': datetime.now().isoformat(),
        }
    
    author_id = author.get('authorId')
    print(f"  ✓ Found: {author.get('name')}")
    print(f"    ID: {author_id}")
    print(f"    Affiliations: {author.get('affiliations', [])}")
    print(f"    Paper count: {author.get('paperCount', 0)}")
    print(f"    h-index: {author.get('hIndex', 0)}")
    
    # Get papers
    print(f"  Fetching papers...")
    papers = get_author_papers(author_id)
    time.sleep(DELAY)
    
    print(f"  ✓ Retrieved {len(papers)} papers")
    
    # Format papers
    formatted_papers = [format_paper(p) for p in papers]
    
    # Count papers with abstracts
    with_abstract = sum(1 for p in formatted_papers if p['abstract'])
    print(f"    With abstracts: {with_abstract}/{len(formatted_papers)}")
    
    # Show sample
    if formatted_papers:
        sample = formatted_papers[0]
        print(f"\n  Sample paper:")
        print(f"    Title: {sample['title'][:60]}...")
        print(f"    Year: {sample['year']}")
        print(f"    Venue: {sample['venue'][:40] if sample['venue'] else 'N/A'}...")
        print(f"    Abstract: {sample['abstract'][:80] if sample['abstract'] else 'N/A'}...")
    
    return {
        'faculty_name': name,
        'faculty_id': faculty_id,
        'semantic_scholar_id': author_id,
        'semantic_scholar_name': author.get('name'),
        'affiliations': author.get('affiliations', []),
        'paper_count_total': author.get('paperCount', 0),
        'citation_count_total': author.get('citationCount', 0),
        'h_index': author.get('hIndex', 0),
        'papers': formatted_papers,
        'fetched_at': datetime.now().isoformat(),
    }


def save_publications(data: dict, faculty_id: str):
    """Save publications to JSON."""
    faculty_dir = FACULTY_DIR / faculty_id
    faculty_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = faculty_dir / "publications.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"  Saved: {output_path}")


def update_publications_log(run_data: dict):
    """Update the publications log."""
    if PUBLICATIONS_LOG_PATH.exists():
        with open(PUBLICATIONS_LOG_PATH, 'r') as f:
            log = json.load(f)
    else:
        log = {"runs": []}
    
    log["runs"].append(run_data)
    
    with open(PUBLICATIONS_LOG_PATH, 'w') as f:
        json.dump(log, f, indent=2)


def main():
    print("="*60)
    print("SEMANTIC SCHOLAR PUBLICATION FETCHER")
    print("="*60)
    
    start_time = datetime.now()
    run_id = start_time.strftime("%Y-%m-%d_%H%M%S")
    
    faculty_list = get_all_faculty()
    yaml_count = sum(1 for f in faculty_list if f.get('source') == 'yaml')
    crawled_count = len(faculty_list) - yaml_count
    print(f"\nFetching publications for {len(faculty_list)} faculty members")
    print(f"  From YAML: {yaml_count}")
    print(f"  From crawled/HTML: {crawled_count}")
    
    results = []
    
    for faculty in faculty_list:
        name = faculty.get('name', 'Unknown')
        faculty_id = faculty.get('faculty_id', '')
        
        try:
            data = fetch_faculty_publications(name, faculty_id)
            save_publications(data, faculty_id)
            results.append({
                'name': name,
                'papers': len(data['papers']),
                'with_abstract': sum(1 for p in data['papers'] if p['abstract']),
                'found': data['semantic_scholar_id'] is not None,
            })
        except Exception as e:
            print(f"  CRITICAL ERROR: {e}")
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for r in results:
        status = "✓" if r['found'] else "❌"
        print(f"  {status} {r['name']}: {r['papers']} papers ({r['with_abstract']} with abstracts)")
    
    # Save log
    end_time = datetime.now()
    duration = end_time - start_time
    
    run_data = {
        'run_id': run_id,
        'started_at': start_time.isoformat(),
        'completed_at': end_time.isoformat(),
        'duration_seconds': duration.total_seconds(),
        'faculty_count': len(results),
        'faculty_found': sum(1 for r in results if r['found']),
        'total_papers': sum(r['papers'] for r in results),
        'papers_with_abstracts': sum(r['with_abstract'] for r in results),
        'faculty_details': results,
    }
    
    update_publications_log(run_data)
    print(f"\nLog saved to: {PUBLICATIONS_LOG_PATH}")


if __name__ == "__main__":
    main()
