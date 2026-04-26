"""
Interactive query tool for faculty search
Usage: python scripts/query.py "your question here"

Supports hybrid search: semantic similarity + keyword matching
Includes LLM generation for natural language answers
"""

import sys
import os
import re
from pathlib import Path
from dotenv import load_dotenv
import chromadb
from chromadb.utils import embedding_functions
from openai import OpenAI

load_dotenv()

DATA_DIR = Path(__file__).parent.parent / "data"
CHROMA_DIR = DATA_DIR / "chroma_db"

# Initialize OpenAI client
client_openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def extract_keywords(text: str) -> set[str]:
    """Extract meaningful keywords from text (3+ chars, lowercase)."""
    # Common stopwords to ignore
    stopwords = {'the', 'and', 'for', 'that', 'with', 'are', 'this', 'from', 'was', 'were', 
                 'been', 'have', 'has', 'had', 'will', 'would', 'could', 'should', 'may',
                 'can', 'who', 'what', 'which', 'how', 'why', 'where', 'when', 'about',
                 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'between',
                 'under', 'again', 'further', 'then', 'once', 'here', 'there', 'all', 'each',
                 'both', 'few', 'more', 'most', 'other', 'some', 'such', 'only', 'own', 'same',
                 'than', 'too', 'very', 'just', 'also', 'now', 'related', 'results', 'relevant'}
    
    words = re.findall(r'\b[a-z]{3,}\b', text.lower())
    return {w for w in words if w not in stopwords}


def keyword_score(doc: str, meta: dict, keywords: set[str]) -> float:
    """Score document based on keyword matches."""
    if not keywords:
        return 0.0
    
    # Combine searchable text
    searchable = doc.lower()
    if meta.get('paper_title'):
        searchable += ' ' + meta['paper_title'].lower()
    if meta.get('faculty_name'):
        searchable += ' ' + meta['faculty_name'].lower()
    
    # Count keyword matches
    matches = sum(1 for kw in keywords if kw in searchable)
    return matches / len(keywords)


def generate_answer(question: str, results: list) -> str:
    """Generate a natural language answer using retrieved context."""
    
    # Build context from top results
    context_parts = []
    for doc, meta, _, _, _ in results[:5]:
        faculty = meta['faculty_name']
        chunk_type = meta['chunk_type']
        
        context_entry = f"Professor: {faculty}\n"
        if meta.get('paper_title'):
            context_entry += f"Paper: {meta['paper_title']}\n"
        if meta.get('year'):
            context_entry += f"Year: {meta['year']}\n"
        context_entry += f"Content: {doc[:500]}"
        context_parts.append(context_entry)
    
    context = "\n\n---\n\n".join(context_parts)
    
    system_prompt = """You are a helpful research assistant for NYU. Based on the faculty research information provided, 
recommend professors who match the user's query. Be specific about WHY each professor is relevant, 
citing their research topics, papers, or expertise. Keep your response concise but informative.

IMPORTANT: Only recommend professors explicitly mentioned in the context below. 
If the context doesn't contain information relevant to the user's question, say:
"I don't have enough information to answer this question based on the faculty data available."
Do NOT invent or guess faculty names, papers, or research topics."""

    user_prompt = f"""Question: {question}

Faculty Research Information:
{context}

Based on this information, which professors would you recommend and why?"""

    # Stream response
    stream = client_openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.3,
        max_tokens=500,
        stream=True
    )
    
    full_response = ""
    for chunk in stream:
        if chunk.choices[0].delta.content:
            content = chunk.choices[0].delta.content
            print(content, end="", flush=True)
            full_response += content
    print()  # newline at end
    
    return full_response


def query(question: str, n_results: int = 50, mode: str = 'hybrid'):
    """
    Query the collection with hybrid search.
    
    Modes:
    - 'semantic': Pure embedding similarity
    - 'keyword': Pure keyword matching
    - 'hybrid': Combined (default)
    """
    
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    openai_ef = embedding_functions.OpenAIEmbeddingFunction(
        api_key=os.getenv("OPENAI_API_KEY"),
        model_name="text-embedding-3-small"
    )
    collection = client.get_collection(name="faculty_search", embedding_function=openai_ef)
    
    # Extract keywords from question
    keywords = extract_keywords(question)
    
    print("="*70)
    print(f"QUERY: {question}")
    print(f"MODE: {mode} | Keywords: {', '.join(sorted(keywords)) if keywords else 'none'}")
    print("="*70)
    
    # Fetch results
    results = collection.query(query_texts=[question], n_results=n_results)
    
    # Score and combine
    scored_results = []
    for doc, meta, dist in zip(results['documents'][0], results['metadatas'][0], results['distances'][0]):
        semantic_score = 1 - dist  # Convert distance to similarity (0-1ish)
        kw_score = keyword_score(doc, meta, keywords)
        
        if mode == 'semantic':
            final_score = semantic_score
        elif mode == 'keyword':
            final_score = kw_score
        else:  # hybrid
            # Weight: 70% semantic, 30% keyword
            final_score = (0.7 * semantic_score) + (0.3 * kw_score)
        
        scored_results.append((doc, meta, final_score, semantic_score, kw_score))
    
    # Sort by final score descending
    scored_results.sort(key=lambda x: x[2], reverse=True)
    
    # Get unique professors
    seen_faculty = set()
    unique_results = []
    
    for doc, meta, final_score, sem_score, kw_score in scored_results:
        faculty_id = meta['faculty_id']
        if faculty_id not in seen_faculty:
            seen_faculty.add(faculty_id)
            unique_results.append((doc, meta, final_score, sem_score, kw_score))
        if len(unique_results) >= 10:
            break
    
    # Filter by score threshold
    MIN_SCORE_THRESHOLD = 0.3
    unique_results = [r for r in unique_results if r[2] >= MIN_SCORE_THRESHOLD]
    
    if not unique_results:
        print("\nNo highly relevant faculty found for this query.")
        print("Try rephrasing your question or using different keywords.")
        return [], None
    
    print(f"\nTOP {min(len(unique_results), 5)} RECOMMENDED PROFESSORS:\n")
    print("-" * 70)
    
    for i, (doc, meta, final_score, sem_score, kw_score) in enumerate(unique_results[:5], 1):
        print(f"\n{i}. {meta['faculty_name']}")
        print(f"   Match Score: {final_score:.3f} (semantic: {sem_score:.3f}, keyword: {kw_score:.3f})")
        
        # Show what matched
        print(f"\n   MATCHED DOCUMENT:")
        print(f"   Type: {meta['chunk_type']}")
        if meta.get('url'):
            print(f"   Source: {meta['url']}")
        if meta.get('paper_title'):
            print(f"   Paper: {meta['paper_title']}")
        if meta.get('year'):
            print(f"   Year: {meta['year']}")
        
        # Show full chunk content
        print(f"\n   FULL CHUNK:")
        print(f"   {'='*60}")
        print(f"   {doc}")
        print(f"   {'='*60}")
        print()
        print("-" * 70)
    
    # Generate natural language answer
    print("\n" + "=" * 70)
    print("AI RECOMMENDATION:")
    print("=" * 70)
    answer = generate_answer(question, unique_results)
    print("=" * 70)
    print("=" * 70)
    
    return unique_results, answer


def chat_mode():
    """Interactive chat mode with conversation memory."""
    
    print("=" * 70)
    print("FACULTY SEARCH CHAT")
    print("Type your questions. Type 'quit' or 'exit' to stop.")
    print("Type 'clear' to reset conversation history.")
    print("=" * 70)
    
    # Initialize ChromaDB once
    chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    openai_ef = embedding_functions.OpenAIEmbeddingFunction(
        api_key=os.getenv("OPENAI_API_KEY"),
        model_name="text-embedding-3-small"
    )
    collection = chroma_client.get_collection(name="faculty_search", embedding_function=openai_ef)
    
    # Conversation history
    messages = [
        {"role": "system", "content": """You are a helpful research assistant for NYU. You help users find faculty members 
based on their research interests. When recommending professors, cite specific papers, topics, or expertise.

IMPORTANT: Only recommend professors explicitly mentioned in the [Retrieved Faculty Information] context.
If the context doesn't contain relevant information, say clearly:
"I don't have enough information about that topic in my faculty database."
Do NOT invent faculty names, papers, or research areas. You can have back-and-forth conversations 
and answer follow-up questions about faculty you've already discussed."""}
    ]
    
    while True:
        try:
            user_input = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break
        
        if not user_input:
            continue
        
        if user_input.lower() in ('quit', 'exit'):
            print("Goodbye!")
            break
        
        if user_input.lower() == 'clear':
            messages = messages[:1]  # Keep only system message
            print("Conversation cleared.")
            continue
        
        # Retrieve relevant context
        results = collection.query(query_texts=[user_input], n_results=10)
        
        # Build context from results
        context_parts = []
        seen_faculty = set()
        for doc, meta in zip(results['documents'][0][:5], results['metadatas'][0][:5]):
            faculty = meta['faculty_name']
            if faculty in seen_faculty:
                continue
            seen_faculty.add(faculty)
            
            entry = f"Professor: {faculty}\n"
            if meta.get('paper_title'):
                entry += f"Paper: {meta['paper_title']}\n"
            if meta.get('year'):
                entry += f"Year: {meta['year']}\n"
            entry += f"Content: {doc[:400]}"
            context_parts.append(entry)
        
        context = "\n\n---\n\n".join(context_parts)
        
        # Add user message with context
        user_message = f"""[Retrieved Faculty Information]
{context}

[User Question]
{user_input}"""
        
        messages.append({"role": "user", "content": user_message})
        
        # Generate response with streaming
        stream = client_openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.3,
            max_tokens=500,
            stream=True
        )
        
        print()  # newline before response
        assistant_reply = ""
        for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                print(content, end="", flush=True)
                assistant_reply += content
        print()  # newline at end
        
        messages.append({"role": "assistant", "content": assistant_reply})


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # No args = interactive chat mode
        chat_mode()
    else:
        # Check if last arg is mode
        mode = 'hybrid'
        args = sys.argv[1:]
        if args[-1] in ('hybrid', 'semantic', 'keyword'):
            mode = args[-1]
            args = args[:-1]
        
        question = " ".join(args)
        results, answer = query(question, mode=mode)
