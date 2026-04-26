"""
Bulk test questions from Excel and dump results
Usage: python scripts/bulk_test.py input.xlsx [output.xlsx]

Input Excel format:
- Column A: Questions to test

Output includes:
- Question, Top professors, Scores, AI Answer, Latency
"""

import sys
import os
import time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import pandas as pd
import chromadb
from chromadb.utils import embedding_functions
from openai import OpenAI

load_dotenv()

DATA_DIR = Path(__file__).parent.parent / "data"
CHROMA_DIR = DATA_DIR / "chroma_db"

# Initialize clients once
client_openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=os.getenv("OPENAI_API_KEY"),
    model_name="text-embedding-3-small"
)
collection = chroma_client.get_collection(name="faculty_search", embedding_function=openai_ef)


def generate_answer(question: str, results: list) -> str:
    """Generate answer from retrieved context."""
    if not results:
        return "No relevant faculty found."
    
    context_parts = []
    for doc, meta, score in results[:5]:
        entry = f"Professor: {meta['faculty_name']}\n"
        if meta.get('paper_title'):
            entry += f"Paper: {meta['paper_title']}\n"
        if meta.get('year'):
            entry += f"Year: {meta['year']}\n"
        entry += f"Content: {doc[:400]}"
        context_parts.append(entry)
    
    context = "\n\n---\n\n".join(context_parts)
    
    system_prompt = """You are a research assistant for NYU. Recommend professors matching the query.
Be concise. Only recommend professors from the context. If no relevant info, say so."""

    response = client_openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Question: {question}\n\nFaculty Info:\n{context}"}
        ],
        temperature=0.3,
        max_tokens=300
    )
    
    return response.choices[0].message.content


def process_question(question: str) -> dict:
    """Process a single question and return all metadata."""
    start_time = time.time()
    
    # Retrieve
    results = collection.query(query_texts=[question], n_results=20)
    
    # Get unique professors with scores
    seen = set()
    unique_results = []
    for doc, meta, dist in zip(results['documents'][0], results['metadatas'][0], results['distances'][0]):
        faculty_id = meta['faculty_id']
        if faculty_id not in seen:
            seen.add(faculty_id)
            score = 1 - dist
            unique_results.append((doc, meta, score))
        if len(unique_results) >= 5:
            break
    
    # Filter by threshold
    unique_results = [r for r in unique_results if r[2] >= 0.3]
    
    retrieval_time = time.time() - start_time
    
    # Generate answer
    gen_start = time.time()
    answer = generate_answer(question, unique_results)
    generation_time = time.time() - gen_start
    
    total_time = time.time() - start_time
    
    # Build result
    top_profs = [r[1]['faculty_name'] for r in unique_results]
    top_scores = [round(r[2], 3) for r in unique_results]
    chunk_types = [r[1]['chunk_type'] for r in unique_results]
    sources = [r[1].get('url', r[1].get('paper_title', 'N/A'))[:80] for r in unique_results]
    
    return {
        'question': question,
        'top_professor_1': top_profs[0] if len(top_profs) > 0 else '',
        'score_1': top_scores[0] if len(top_scores) > 0 else '',
        'top_professor_2': top_profs[1] if len(top_profs) > 1 else '',
        'score_2': top_scores[1] if len(top_scores) > 1 else '',
        'top_professor_3': top_profs[2] if len(top_profs) > 2 else '',
        'score_3': top_scores[2] if len(top_scores) > 2 else '',
        'top_professor_4': top_profs[3] if len(top_profs) > 3 else '',
        'score_4': top_scores[3] if len(top_scores) > 3 else '',
        'top_professor_5': top_profs[4] if len(top_profs) > 4 else '',
        'score_5': top_scores[4] if len(top_scores) > 4 else '',
        'all_professors': ', '.join(top_profs),
        'all_scores': ', '.join(map(str, top_scores)),
        'chunk_types': ', '.join(chunk_types),
        'sources': ' | '.join(sources),
        'ai_answer': answer,
        'retrieval_time_sec': round(retrieval_time, 2),
        'generation_time_sec': round(generation_time, 2),
        'total_time_sec': round(total_time, 2),
        'num_results': len(unique_results)
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/bulk_test.py input.xlsx [output.xlsx]")
        print("\nInput Excel should have questions in column A (with or without header)")
        sys.exit(1)
    
    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f"ERROR: File not found: {input_path}")
        sys.exit(1)
    
    # Output path
    if len(sys.argv) >= 3:
        output_path = Path(sys.argv[2])
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = DATA_DIR / f"bulk_test_results_{timestamp}.xlsx"
    
    print("=" * 60)
    print("BULK TEST")
    print("=" * 60)
    print(f"Input: {input_path}")
    print(f"Output: {output_path}")
    
    # Read input
    df_input = pd.read_excel(input_path, header=None)
    questions = df_input[0].dropna().tolist()
    
    # Skip header if it looks like one
    if questions and questions[0].lower() in ('question', 'questions', 'query', 'queries', 'q'):
        questions = questions[1:]
    
    print(f"Questions: {len(questions)}")
    print("=" * 60)
    
    results = []
    for i, question in enumerate(questions, 1):
        print(f"\n[{i}/{len(questions)}] {question[:60]}...")
        try:
            result = process_question(str(question))
            results.append(result)
            print(f"  → {result['num_results']} professors, {result['total_time_sec']}s")
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({
                'question': question,
                'error': str(e)
            })
    
    # Save results
    df_output = pd.DataFrame(results)
    df_output.to_excel(output_path, index=False)
    
    print("\n" + "=" * 60)
    print("COMPLETE")
    print("=" * 60)
    print(f"Processed: {len(results)} questions")
    print(f"Output saved: {output_path}")
    
    # Summary stats
    if results:
        avg_time = sum(r.get('total_time_sec', 0) for r in results) / len(results)
        avg_results = sum(r.get('num_results', 0) for r in results) / len(results)
        print(f"Avg time: {avg_time:.2f}s")
        print(f"Avg results: {avg_results:.1f}")


if __name__ == "__main__":
    main()
