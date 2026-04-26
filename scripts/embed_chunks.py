"""
Embed chunks and store in ChromaDB
- Loads chunks from all faculty folders
- Embeds using OpenAI text-embedding-3-small
- Stores in local ChromaDB with metadata
"""

import json
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import chromadb
from chromadb.utils import embedding_functions

# Load environment variables
load_dotenv()

# Paths
DATA_DIR = Path(__file__).parent.parent / "data"
FACULTY_DIR = DATA_DIR / "faculty"
CHROMA_DIR = DATA_DIR / "chroma_db"
EMBED_LOG_PATH = DATA_DIR / "embed_log.json"

# Settings
COLLECTION_NAME = "faculty_search"
EMBEDDING_MODEL = "text-embedding-3-small"
BATCH_SIZE = 100  # OpenAI recommends batching


def load_all_chunks() -> list[dict]:
    """Load chunks from all faculty folders."""
    all_chunks = []
    
    for faculty_dir in sorted(FACULTY_DIR.iterdir()):
        if not faculty_dir.is_dir():
            continue
        
        chunks_path = faculty_dir / "chunks.json"
        if not chunks_path.exists():
            continue
        
        with open(chunks_path, 'r', encoding='utf-8') as f:
            chunks = json.load(f)
        
        all_chunks.extend(chunks)
    
    return all_chunks


def prepare_metadata(chunk: dict) -> dict:
    """Prepare metadata for ChromaDB (must be str, int, float, or bool)."""
    metadata = {
        'faculty_id': chunk.get('faculty_id', ''),
        'faculty_name': chunk.get('faculty_name', ''),
        'chunk_type': chunk.get('chunk_type', ''),
        'source': chunk.get('source', ''),
    }
    
    # Optional fields
    if chunk.get('url'):
        metadata['url'] = chunk['url']
    if chunk.get('page_title'):
        metadata['page_title'] = chunk['page_title']
    if chunk.get('paper_title'):
        metadata['paper_title'] = chunk['paper_title']
    if chunk.get('year'):
        metadata['year'] = int(chunk['year'])
    if chunk.get('venue'):
        metadata['venue'] = chunk['venue']
    if chunk.get('citation_count') is not None:
        metadata['citation_count'] = int(chunk['citation_count'])
    if chunk.get('authors'):
        metadata['authors'] = ', '.join(chunk['authors'][:5])  # String for Chroma
    
    return metadata


def update_embed_log(run_data: dict):
    """Update the embedding log."""
    if EMBED_LOG_PATH.exists():
        with open(EMBED_LOG_PATH, 'r') as f:
            log = json.load(f)
    else:
        log = {"runs": []}
    
    log["runs"].append(run_data)
    
    with open(EMBED_LOG_PATH, 'w') as f:
        json.dump(log, f, indent=2)


def main():
    print("="*60)
    print("EMBEDDING PIPELINE")
    print("="*60)
    
    # Check API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not found in .env file")
        return
    
    print(f"API Key: {api_key[:8]}...{api_key[-4:]}")
    
    start_time = datetime.now()
    run_id = start_time.strftime("%Y-%m-%d_%H%M%S")
    
    # Load chunks
    print("\nLoading chunks...")
    all_chunks = load_all_chunks()
    print(f"Loaded {len(all_chunks)} total chunks")
    
    # Deduplicate by chunk_id (same content = same ID)
    seen_ids = set()
    chunks = []
    duplicates = 0
    for chunk in all_chunks:
        chunk_id = chunk.get('chunk_id', '')
        if chunk_id and chunk_id not in seen_ids:
            seen_ids.add(chunk_id)
            chunks.append(chunk)
        else:
            duplicates += 1
    
    print(f"After deduplication: {len(chunks)} unique chunks")
    if duplicates > 0:
        print(f"  (Removed {duplicates} duplicates)")
    
    # Initialize ChromaDB
    print(f"\nInitializing ChromaDB at {CHROMA_DIR}...")
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    
    # Create embedding function
    openai_ef = embedding_functions.OpenAIEmbeddingFunction(
        api_key=api_key,
        model_name=EMBEDDING_MODEL
    )
    
    # Delete existing collection if exists (fresh start)
    try:
        client.delete_collection(name=COLLECTION_NAME)
        print(f"Deleted existing collection: {COLLECTION_NAME}")
    except:
        pass
    
    # Create collection
    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=openai_ef,
        metadata={"description": "Faculty search embeddings"}
    )
    print(f"Created collection: {COLLECTION_NAME}")
    
    # Embed in batches
    print(f"\nEmbedding {len(chunks)} chunks in batches of {BATCH_SIZE}...")
    
    total_embedded = 0
    errors = []
    
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(chunks) + BATCH_SIZE - 1) // BATCH_SIZE
        
        print(f"  Batch {batch_num}/{total_batches} ({len(batch)} chunks)...", end=" ")
        
        try:
            # Prepare batch data (deduplicate within batch as safety net)
            batch_seen = set()
            unique_batch = []
            for c in batch:
                if c['chunk_id'] not in batch_seen:
                    batch_seen.add(c['chunk_id'])
                    unique_batch.append(c)
            
            ids = [c['chunk_id'] for c in unique_batch]
            documents = [c['content'] for c in unique_batch]
            metadatas = [prepare_metadata(c) for c in unique_batch]
            
            # Add to collection (ChromaDB handles embedding)
            # Using upsert to handle any duplicate IDs gracefully
            collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )
            
            total_embedded += len(unique_batch)
            print("✓")
            
        except Exception as e:
            print(f"ERROR: {e}")
            errors.append({
                'batch': batch_num,
                'error': str(e)
            })
    
    # Summary
    end_time = datetime.now()
    duration = end_time - start_time
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total chunks: {len(chunks)}")
    print(f"Embedded: {total_embedded}")
    print(f"Errors: {len(errors)}")
    print(f"Duration: {duration}")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Storage: {CHROMA_DIR}")
    
    # Verify
    print(f"\nVerifying collection...")
    count = collection.count()
    print(f"Documents in collection: {count}")
    
    # Test query
    print(f"\nTest query: 'ethnic diversity and cooperation'")
    results = collection.query(
        query_texts=["ethnic diversity and cooperation"],
        n_results=3
    )
    
    print("Top 3 results:")
    for i, (doc, meta) in enumerate(zip(results['documents'][0], results['metadatas'][0])):
        print(f"  {i+1}. [{meta['faculty_name']}] {meta['chunk_type']}: {doc[:80]}...")
    
    # Save log
    run_data = {
        'run_id': run_id,
        'started_at': start_time.isoformat(),
        'completed_at': end_time.isoformat(),
        'duration_seconds': duration.total_seconds(),
        'total_chunks': len(chunks),
        'embedded': total_embedded,
        'errors': len(errors),
        'collection': COLLECTION_NAME,
        'model': EMBEDDING_MODEL,
    }
    
    update_embed_log(run_data)
    print(f"\nLog saved to: {EMBED_LOG_PATH}")


if __name__ == "__main__":
    main()
