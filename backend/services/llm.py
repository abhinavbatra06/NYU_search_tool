"""LLM-based answer generation for search results."""

from typing import List, Tuple, Dict, Any
from openai import OpenAI


def build_context_from_results(
    results: List[Tuple[str, Dict[str, Any], float]],
    max_results: int = 5
) -> str:
    """Build RAG context string from retrieved results."""
    context_parts = []

    for doc, meta, score in results[:max_results]:
        entry = f"Professor: {meta.get('faculty_name', 'Unknown')}\n"
        if meta.get('url'):
            entry += f"Website: {meta['url']}\n"
        if meta.get('paper_title'):
            entry += f"Paper: {meta['paper_title']}\n"
        if meta.get('year'):
            entry += f"Year: {meta['year']}\n"
        entry += f"Content: {doc[:400]}"
        context_parts.append(entry)

    return "\n\n---\n\n".join(context_parts) if context_parts else "No relevant faculty found."


def generate_answer(
    client: OpenAI,
    question: str,
    context: str,
    conversation_history: List[Dict[str, str]] = None,
    temperature: float = 0.3,
    max_tokens: int = 500
) -> str:
    """Generate a natural language answer using retrieved context."""
    
    system_msg = """You are a helpful research assistant for NYU. Your ONLY purpose is to help users find NYU faculty based on research interests, topics, methods, or expertise.

If the user's question is NOT about finding faculty or research topics (e.g. they ask about weather, coding help, general knowledge, opinions, or anything unrelated to NYU faculty search), respond with exactly:
"I can only help with finding NYU faculty by research interest. Try asking something like: 'Who works on climate and cities?' or 'Faculty studying machine learning and ethics?'"

Otherwise, based on the faculty research information provided, recommend professors who match the user's query. Be specific about WHY each professor is relevant. Keep responses concise. Only recommend professors from the context. If no relevant faculty are found in the context, say so.
IMPORTANT: Always include the professor's website link when available, formatted as markdown: [Professor Name](URL)"""

    user_msg = f"""[Retrieved Faculty Information]
{context}

[User Question]
{question}"""

    messages = [{"role": "system", "content": system_msg}]
    
    if conversation_history:
        messages.extend(conversation_history)
    
    messages.append({"role": "user", "content": user_msg})

    stream = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True
    )

    full_response = ""
    for chunk in stream:
        if chunk.choices[0].delta.content:
            full_response += chunk.choices[0].delta.content

    return full_response
