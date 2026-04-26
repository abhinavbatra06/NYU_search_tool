"""
Chunking Script for RAG Pipeline
- Processes pages.json, publications.json, and PDFs
- Creates chunks with metadata for vector DB
- Outputs chunks.json per faculty
"""

import json
import re
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional
import hashlib

# Optional: PDF extraction
try:
    import PyPDF2
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    print("Warning: PyPDF2 not installed. PDF extraction disabled. Run: pip install PyPDF2")

# Paths
DATA_DIR = Path(__file__).parent.parent / "data"
FACULTY_DIR = DATA_DIR / "faculty"
CHUNKS_LOG_PATH = DATA_DIR / "chunks_log.json"

# Settings
MAX_CHUNK_TOKENS = 500  # ~500 tokens ≈ ~2000 chars
MAX_CHUNK_CHARS = 2000
MIN_CONTENT_WORDS = 50  # Skip pages with fewer words
CHUNK_OVERLAP_CHARS = 200  # Overlap between chunks

# Skip patterns
SKIP_URL_PATTERNS = [
    r'wp-login', r'/feed', r'/rss', r'\.xml$',
    r'/cart', r'/checkout', r'/admin'
]


@dataclass
class Chunk:
    chunk_id: str
    faculty_id: str
    faculty_name: str
    chunk_type: str  # bio, research, publication, page, cv
    source: str  # website, semantic_scholar, pdf
    content: str
    url: Optional[str] = None
    page_title: Optional[str] = None
    paper_title: Optional[str] = None
    year: Optional[int] = None
    venue: Optional[str] = None
    citation_count: Optional[int] = None
    authors: Optional[list] = None
    chunk_index: Optional[int] = None  # For split pages
    total_chunks: Optional[int] = None


def generate_chunk_id(faculty_id: str, content: str, chunk_type: str, index: int = 0) -> str:
    """Generate unique chunk ID."""
    # Use full content hash for uniqueness
    hash_input = f"{faculty_id}:{chunk_type}:{content}:{index}"
    return hashlib.md5(hash_input.encode()).hexdigest()[:16]


def should_skip_url(url: str) -> bool:
    """Check if URL should be skipped."""
    url_lower = url.lower()
    return any(re.search(p, url_lower) for p in SKIP_URL_PATTERNS)


def split_text(text: str, max_chars: int = MAX_CHUNK_CHARS, overlap: int = CHUNK_OVERLAP_CHARS) -> list[str]:
    """Split text into chunks with overlap."""
    if len(text) <= max_chars:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + max_chars
        
        # Try to break at paragraph or sentence
        if end < len(text):
            # Look for paragraph break
            para_break = text.rfind('\n\n', start, end)
            if para_break > start + max_chars // 2:
                end = para_break
            else:
                # Look for sentence break
                sentence_break = text.rfind('. ', start, end)
                if sentence_break > start + max_chars // 2:
                    end = sentence_break + 1
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        start = end - overlap if end < len(text) else end
    
    return chunks


def detect_page_chunk_type(page: dict) -> str:
    """Determine chunk type from page data."""
    url = page.get('url', '').lower()
    page_type = page.get('page_type', 'general')
    depth = page.get('depth', 0)
    
    if depth == 0:
        return 'bio'
    if page_type == 'research':
        return 'research'
    if page_type == 'publications':
        return 'publications_list'
    if page_type == 'teaching':
        return 'teaching'
    if '/cv' in url or '/resume' in url or '/vitae' in url:
        return 'cv_page'
    
    return 'page'


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract text from PDF."""
    if not PDF_SUPPORT:
        return ""
    
    try:
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        print(f"    Error extracting PDF {pdf_path}: {e}")
        return ""


def process_pages(pages_data: dict, faculty_id: str, faculty_name: str) -> list[Chunk]:
    """Process pages.json into chunks."""
    chunks = []
    
    for page in pages_data.get('pages', []):
        url = page.get('url', '')
        content = page.get('content', '')
        word_count = page.get('word_count', 0)
        title = page.get('title', '')
        
        # Skip junk pages
        if word_count < MIN_CONTENT_WORDS:
            continue
        if should_skip_url(url):
            continue
        if 'redirecting' in title.lower():
            continue
        
        chunk_type = detect_page_chunk_type(page)
        
        # Split long pages
        text_chunks = split_text(content)
        total = len(text_chunks)
        
        for i, text in enumerate(text_chunks):
            chunk_id = generate_chunk_id(faculty_id, text, chunk_type, i)
            
            chunks.append(Chunk(
                chunk_id=chunk_id,
                faculty_id=faculty_id,
                faculty_name=faculty_name,
                chunk_type=chunk_type,
                source='website',
                content=text,
                url=url,
                page_title=title,
                chunk_index=i if total > 1 else None,
                total_chunks=total if total > 1 else None,
            ))
    
    return chunks


def process_publications(pubs_data: dict, faculty_id: str, faculty_name: str) -> list[Chunk]:
    """Process publications.json into chunks."""
    chunks = []
    
    for paper in pubs_data.get('papers', []):
        title = paper.get('title', '')
        abstract = paper.get('abstract', '')
        year = paper.get('year')
        venue = paper.get('venue', '')
        citation_count = paper.get('citation_count', 0)
        authors = paper.get('authors', [])
        
        # Skip papers without title
        if not title:
            continue
        
        # Build content: title + abstract (if available)
        if abstract:
            content = f"Title: {title}\n\nAbstract: {abstract}"
        else:
            content = f"Title: {title}\n\nVenue: {venue}\nYear: {year}"
        
        chunk_id = generate_chunk_id(faculty_id, title, 'publication', 0)
        
        chunks.append(Chunk(
            chunk_id=chunk_id,
            faculty_id=faculty_id,
            faculty_name=faculty_name,
            chunk_type='publication',
            source='semantic_scholar',
            content=content,
            paper_title=title,
            year=year,
            venue=venue,
            citation_count=citation_count,
            authors=authors,
        ))
    
    return chunks


def process_pdfs(pdfs_data: list, faculty_dir: Path, faculty_id: str, faculty_name: str) -> list[Chunk]:
    """Process PDFs into chunks."""
    chunks = []
    
    if not PDF_SUPPORT:
        return chunks
    
    for pdf_info in pdfs_data:
        local_path = pdf_info.get('local_path', '')
        detected_as = pdf_info.get('detected_as', '')
        url = pdf_info.get('url', '')
        
        pdf_path = faculty_dir / local_path
        if not pdf_path.exists():
            continue
        
        print(f"    Extracting PDF: {local_path}")
        text = extract_pdf_text(pdf_path)
        
        if not text or len(text.split()) < MIN_CONTENT_WORDS:
            continue
        
        # CVs can be long - split into chunks
        text_chunks = split_text(text)
        total = len(text_chunks)
        
        for i, chunk_text in enumerate(text_chunks):
            chunk_id = generate_chunk_id(faculty_id, chunk_text, 'cv', i)
            
            chunks.append(Chunk(
                chunk_id=chunk_id,
                faculty_id=faculty_id,
                faculty_name=faculty_name,
                chunk_type='cv' if detected_as == 'CV' else 'pdf',
                source='pdf',
                content=chunk_text,
                url=url,
                page_title=f"CV - {faculty_name}" if detected_as == 'CV' else local_path,
                chunk_index=i if total > 1 else None,
                total_chunks=total if total > 1 else None,
            ))
    
    return chunks


def process_faculty(faculty_dir: Path) -> tuple[list[Chunk], dict]:
    """Process all data for a single faculty member."""
    faculty_id = faculty_dir.name
    chunks = []
    stats = {'pages': 0, 'publications': 0, 'pdfs': 0, 'total_chunks': 0}
    
    # Load pages.json
    pages_path = faculty_dir / "pages.json"
    if pages_path.exists():
        with open(pages_path, 'r', encoding='utf-8') as f:
            pages_data = json.load(f)
        
        faculty_name = pages_data.get('faculty_name', faculty_id)
        
        page_chunks = process_pages(pages_data, faculty_id, faculty_name)
        chunks.extend(page_chunks)
        stats['pages'] = len(page_chunks)
        
        # Process PDFs
        pdf_chunks = process_pdfs(pages_data.get('pdfs', []), faculty_dir, faculty_id, faculty_name)
        chunks.extend(pdf_chunks)
        stats['pdfs'] = len(pdf_chunks)
    else:
        faculty_name = faculty_id
    
    # Load publications.json
    pubs_path = faculty_dir / "publications.json"
    if pubs_path.exists():
        with open(pubs_path, 'r', encoding='utf-8') as f:
            pubs_data = json.load(f)
        
        pub_chunks = process_publications(pubs_data, faculty_id, faculty_name)
        chunks.extend(pub_chunks)
        stats['publications'] = len(pub_chunks)
    
    stats['total_chunks'] = len(chunks)
    
    return chunks, stats


def save_chunks(chunks: list[Chunk], faculty_dir: Path):
    """Save chunks to JSON file."""
    output_path = faculty_dir / "chunks.json"
    
    chunks_data = [asdict(c) for c in chunks]
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(chunks_data, f, indent=2, ensure_ascii=False)
    
    return output_path


def update_chunks_log(run_data: dict):
    """Update the chunks log."""
    if CHUNKS_LOG_PATH.exists():
        with open(CHUNKS_LOG_PATH, 'r') as f:
            log = json.load(f)
    else:
        log = {"runs": []}
    
    log["runs"].append(run_data)
    
    with open(CHUNKS_LOG_PATH, 'w') as f:
        json.dump(log, f, indent=2)


def main():
    print("="*60)
    print("CHUNKING PIPELINE")
    print("="*60)
    
    if not PDF_SUPPORT:
        print("\nNote: Install PyPDF2 for PDF extraction: pip install PyPDF2\n")
    
    start_time = datetime.now()
    run_id = start_time.strftime("%Y-%m-%d_%H%M%S")
    
    # Find all faculty directories
    faculty_dirs = [d for d in FACULTY_DIR.iterdir() if d.is_dir()]
    print(f"\nFound {len(faculty_dirs)} faculty directories")
    
    all_stats = []
    total_chunks = 0
    
    for faculty_dir in sorted(faculty_dirs):
        print(f"\n{'='*60}")
        print(f"Processing: {faculty_dir.name}")
        print('='*60)
        
        chunks, stats = process_faculty(faculty_dir)
        
        if chunks:
            output_path = save_chunks(chunks, faculty_dir)
            print(f"  Pages: {stats['pages']} chunks")
            print(f"  Publications: {stats['publications']} chunks")
            print(f"  PDFs: {stats['pdfs']} chunks")
            print(f"  Total: {stats['total_chunks']} chunks")
            print(f"  Saved: {output_path}")
            
            all_stats.append({
                'faculty_id': faculty_dir.name,
                **stats
            })
            total_chunks += stats['total_chunks']
        else:
            print("  No chunks created")
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total faculty: {len(all_stats)}")
    print(f"Total chunks: {total_chunks}")
    print(f"  - Page chunks: {sum(s['pages'] for s in all_stats)}")
    print(f"  - Publication chunks: {sum(s['publications'] for s in all_stats)}")
    print(f"  - PDF chunks: {sum(s['pdfs'] for s in all_stats)}")
    
    # Save log
    end_time = datetime.now()
    duration = end_time - start_time
    
    run_data = {
        'run_id': run_id,
        'started_at': start_time.isoformat(),
        'completed_at': end_time.isoformat(),
        'duration_seconds': duration.total_seconds(),
        'faculty_count': len(all_stats),
        'total_chunks': total_chunks,
        'page_chunks': sum(s['pages'] for s in all_stats),
        'publication_chunks': sum(s['publications'] for s in all_stats),
        'pdf_chunks': sum(s['pdfs'] for s in all_stats),
        'faculty_details': all_stats,
    }
    
    update_chunks_log(run_data)
    print(f"\nLog saved to: {CHUNKS_LOG_PATH}")


if __name__ == "__main__":
    main()
