"""
NYU Faculty Search - Streamlit App
"""

import os
import time
import streamlit as st
import chromadb
from chromadb.utils import embedding_functions
from openai import OpenAI
from pathlib import Path

# Page config
st.set_page_config(
    page_title="NYU Faculty Search",
    page_icon="🎓",
    layout="wide"
)

# Rate limit settings
MAX_QUERIES_PER_MINUTE = 5
MAX_QUERIES_PER_SESSION = 50

# Paths
DATA_DIR = Path(__file__).parent / "data"
CHROMA_DIR = DATA_DIR / "chroma_db"


def check_rate_limit():
    """Check if user is within rate limits. Returns (allowed, message)."""
    now = time.time()
    
    # Initialize tracking
    if "query_timestamps" not in st.session_state:
        st.session_state.query_timestamps = []
    if "total_queries" not in st.session_state:
        st.session_state.total_queries = 0
    
    # Clean old timestamps (older than 1 minute)
    st.session_state.query_timestamps = [
        ts for ts in st.session_state.query_timestamps 
        if now - ts < 60
    ]
    
    # Check session limit
    if st.session_state.total_queries >= MAX_QUERIES_PER_SESSION:
        return False, f"Session limit reached ({MAX_QUERIES_PER_SESSION} queries). Please refresh the page."
    
    # Check per-minute limit
    if len(st.session_state.query_timestamps) >= MAX_QUERIES_PER_MINUTE:
        wait_time = int(60 - (now - st.session_state.query_timestamps[0]))
        return False, f"Rate limit reached. Please wait {wait_time} seconds."
    
    return True, ""


def record_query():
    """Record a query for rate limiting."""
    st.session_state.query_timestamps.append(time.time())
    st.session_state.total_queries += 1


# Initialize clients (cached)
@st.cache_resource
def get_clients():
    api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("OpenAI API key not found. Add it to Streamlit secrets or .env")
        st.stop()
    
    openai_client = OpenAI(api_key=api_key)
    chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    openai_ef = embedding_functions.OpenAIEmbeddingFunction(
        api_key=api_key,
        model_name="text-embedding-3-small"
    )
    collection = chroma_client.get_collection(name="faculty_search", embedding_function=openai_ef)
    
    return openai_client, collection

openai_client, collection = get_clients()


def search_faculty(query: str, n_results: int = 20):
    """Search for relevant faculty."""
    results = collection.query(query_texts=[query], n_results=n_results)
    
    # Get unique professors with scores
    seen = set()
    unique_results = []
    for doc, meta, dist in zip(results['documents'][0], results['metadatas'][0], results['distances'][0]):
        faculty_id = meta['faculty_id']
        if faculty_id not in seen:
            seen.add(faculty_id)
            score = 1 - dist
            if score >= 0.3:  # Threshold
                unique_results.append((doc, meta, score))
        if len(unique_results) >= 5:
            break
    
    return unique_results


def generate_response(query: str, results: list, messages: list):
    """Generate AI response with streaming."""
    
    # Build context
    context_parts = []
    for doc, meta, score in results[:5]:
        entry = f"Professor: {meta['faculty_name']}\n"
        if meta.get('paper_title'):
            entry += f"Paper: {meta['paper_title']}\n"
        if meta.get('year'):
            entry += f"Year: {meta['year']}\n"
        entry += f"Content: {doc[:400]}"
        context_parts.append(entry)
    
    context = "\n\n---\n\n".join(context_parts) if context_parts else "No relevant faculty found."
    
    # Build messages
    system_msg = """You are a helpful research assistant for NYU. Based on the faculty research information provided,
recommend professors who match the user's query. Be specific about WHY each professor is relevant.
Keep responses concise. Only recommend professors from the context. If no relevant info, say so."""
    
    user_msg = f"""[Retrieved Faculty Information]
{context}

[User Question]
{query}"""
    
    full_messages = [{"role": "system", "content": system_msg}]
    full_messages.extend(messages)
    full_messages.append({"role": "user", "content": user_msg})
    
    # Stream response
    stream = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=full_messages,
        temperature=0.3,
        max_tokens=500,
        stream=True
    )
    
    return stream


# UI
st.title("🎓 NYU Faculty Search")
st.markdown("Find scholars based on research interests, topics, or questions.")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar
with st.sidebar:
    st.header("About")
    st.markdown("""
    This tool helps you find NYU scholars based on their research.
    
    **How it works:**
    1. Enter your research interest or question
    2. We search faculty websites, publications, and CVs
    3. AI recommends relevant professors
    
    **Tips:**
    - Be specific about topics
    - Ask follow-up questions
    - Try different phrasings
    """)
    
    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.session_state.total_queries = 0
        st.session_state.query_timestamps = []
        st.rerun()
    
    st.divider()
    
    # Show rate limit status
    remaining = MAX_QUERIES_PER_SESSION - st.session_state.get('total_queries', 0)
    st.caption(f"Queries remaining: {remaining}/{MAX_QUERIES_PER_SESSION}")
    st.caption("Built with Streamlit + ChromaDB + OpenAI")

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("What research topics are you interested in?"):
    # Check rate limit
    allowed, rate_msg = check_rate_limit()
    if not allowed:
        st.error(rate_msg)
        st.stop()
    
    # Record query
    record_query()
    
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Search
    with st.spinner("Searching faculty..."):
        results = search_faculty(prompt)
    
    # Display results in expander
    if results:
        with st.expander(f"📚 Found {len(results)} relevant faculty", expanded=False):
            for doc, meta, score in results:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{meta['faculty_name']}**")
                    if meta.get('paper_title'):
                        st.caption(f"📄 {meta['paper_title'][:80]}...")
                    st.caption(f"Type: {meta['chunk_type']}")
                with col2:
                    st.metric("Score", f"{score:.2f}")
                st.divider()
    
    # Generate AI response
    with st.chat_message("assistant"):
        if not results:
            response = "I couldn't find any highly relevant faculty for that query. Try rephrasing or using different keywords."
            st.markdown(response)
        else:
            stream = generate_response(prompt, results, st.session_state.messages[:-1])
            response = st.write_stream(stream)
    
    # Save assistant response
    st.session_state.messages.append({"role": "assistant", "content": response})
