# NYU Research Scholar Search Tool - System Design

## Overview

An AI-powered semantic search tool that enables users to find research scholars and their work across individual faculty websites. The system uses RAG (Retrieval-Augmented Generation) to provide intelligent, context-aware search results.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACE                                  │
│                    (Web App / API / Chat Interface)                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           QUERY PROCESSING LAYER                             │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐  ┌──────────────────┐   │
│  │Query Parser │→ │Query Embedder│→ │Intent Router│→ │Retrieval Planner │   │
│  └─────────────┘  └──────────────┘  └─────────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           RETRIEVAL LAYER (RAG)                              │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────────────┐ │
│  │ Vector Search  │  │ Metadata Filter│  │ Re-ranker (Recency/Citations) │ │
│  └────────────────┘  └────────────────┘  └────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           GENERATION LAYER                                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌───────────────────────────────┐│
│  │ Context Builder │→ │ LLM Inference   │→ │ Response Formatter + Grounding││
│  └─────────────────┘  └─────────────────┘  └───────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                      │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────────────┐ │
│  │ Vector Store   │  │ Document Store │  │ Scholar Metadata DB            │ │
│  │ (Embeddings)   │  │ (Raw Content)  │  │ (Profiles, Citations, Links)   │ │
│  └────────────────┘  └────────────────┘  └────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                      ▲
                                      │
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA INGESTION PIPELINE                            │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────────────────┐ │
│  │ Web Scraper│  │ Doc Parser │  │ Chunker    │  │ Embedding Generator    │ │
│  │ (Websites) │  │ (PDF/Docs) │  │            │  │                        │ │
│  └────────────┘  └────────────┘  └────────────┘  └────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Deep Dive

### 1. Data Ingestion Pipeline

**Purpose**: Crawl, parse, and index content from scholar websites and documents.

#### 1.1 Data Sources
| Source | Method | POC Approach | Production Approach |
|--------|--------|--------------|---------------------|
| Faculty Websites | Web scraping | BeautifulSoup + requests | Scrapy/Playwright + proxy rotation |
| Research Papers | PDF parsing | PyMuPDF / pdfplumber | GROBID for structured extraction |
| Google Docs | API | Google Docs API | Same + incremental sync |
| Notion | API | Notion API | Same + webhooks for updates |
| Scholar Profiles | API/Scraping | Semantic Scholar API | Same + Google Scholar (careful with rate limits) |

#### 1.2 Crawling Strategy

```python
# Conceptual: Catalog-driven crawling
class ScholarCrawler:
    def __init__(self, catalog_url: str):
        self.catalog_url = catalog_url
        self.scholar_websites = []
    
    def discover_scholars(self) -> List[Scholar]:
        """Parse catalog page to extract scholar links"""
        pass
    
    def crawl_scholar_website(self, scholar: Scholar) -> List[Document]:
        """Deep crawl individual scholar website"""
        # Crawl: /publications, /research, /teaching, /about
        pass
    
    def schedule_incremental_update(self, cadence: str = "weekly"):
        """Re-crawl for updates"""
        pass
```

#### 1.3 Document Processing

```
Raw HTML/PDF → Clean Text → Chunking → Embedding → Vector Store
                    │
                    └─→ Metadata Extraction → Metadata DB
```

**Chunking Strategy (Critical for RAG quality)**:
- **POC**: Fixed-size chunks (512-1024 tokens) with overlap (50-100 tokens)
- **Production**: Semantic chunking (by paragraph/section) + hierarchical chunks

```python
# Chunking approaches
class ChunkingStrategy:
    # POC: Simple recursive splitter
    FIXED_SIZE = {
        "chunk_size": 800,
        "chunk_overlap": 100,
        "separators": ["\n\n", "\n", ". ", " "]
    }
    
    # Production: Semantic + Hierarchical
    SEMANTIC = {
        "method": "sentence_transformers",  # Cluster similar sentences
        "parent_chunk_size": 2000,          # For context retrieval
        "child_chunk_size": 400             # For precise matching
    }
```

---

### 2. Storage Layer

#### 2.1 Vector Database Options

| Solution | POC Fit | Production Fit | Cost | Notes |
|----------|---------|----------------|------|-------|
| **Chroma** | ✅ Excellent | ⚠️ Limited | Free | Local, simple, great for POC |
| **Pinecone** | ✅ Good | ✅ Excellent | ~$70/mo starter | Managed, scales well |
| **Weaviate** | ✅ Good | ✅ Excellent | Free (self-host) | Hybrid search built-in |
| **Qdrant** | ✅ Good | ✅ Excellent | Free (self-host) | Great filtering, Rust-based |
| **pgvector** | ✅ Good | ✅ Good | DB cost | If already using Postgres |

**Recommendation**:
- **POC**: Chroma (local, zero setup)
- **Production**: Qdrant or Weaviate (self-hosted) OR Pinecone (managed)

#### 2.2 Schema Design

```python
# Document schema
Document = {
    "id": "uuid",
    "scholar_id": "prof_123",
    "scholar_name": "Dr. Jane Smith",
    "source_url": "https://cs.nyu.edu/~jsmith/publications.html",
    "source_type": "website|paper|profile",
    "content": "Raw text content...",
    "chunk_index": 0,
    "total_chunks": 5,
    "embedding": [0.1, 0.2, ...],  # 1536-dim for OpenAI, 768 for smaller models
    
    # Metadata for filtering/ranking
    "metadata": {
        "department": "Computer Science",
        "research_areas": ["NLP", "Machine Learning"],
        "publication_year": 2024,
        "citation_count": 150,
        "last_updated": "2025-02-01",
        "content_type": "publication|bio|research_statement|news"
    }
}

# Scholar schema (separate table/collection)
Scholar = {
    "id": "prof_123",
    "name": "Dr. Jane Smith",
    "title": "Associate Professor",
    "department": "Computer Science",
    "website_url": "https://cs.nyu.edu/~jsmith",
    "email": "jsmith@nyu.edu",
    "research_areas": ["NLP", "Machine Learning"],
    "h_index": 25,
    "total_citations": 3500,
    "profile_embedding": [...]  # Embedding of their "about" section
}
```

---

### 3. Embedding Strategy

#### 3.1 Model Options

| Model | Dimensions | Cost | Quality | Speed |
|-------|------------|------|---------|-------|
| **OpenAI text-embedding-3-small** | 1536 | $0.02/1M tokens | Very Good | Fast |
| **OpenAI text-embedding-3-large** | 3072 | $0.13/1M tokens | Excellent | Fast |
| **Cohere embed-v3** | 1024 | $0.10/1M tokens | Excellent | Fast |
| **sentence-transformers/all-MiniLM-L6-v2** | 384 | Free | Good | Fast (local) |
| **BAAI/bge-large-en-v1.5** | 1024 | Free | Very Good | Medium (local) |
| **nomic-embed-text** | 768 | Free | Very Good | Fast (local) |

**Recommendation**:
- **POC**: OpenAI `text-embedding-3-small` (cheap, easy, good quality)
- **Budget Production**: `BAAI/bge-large-en-v1.5` or `nomic-embed-text` (self-hosted)
- **Quality Production**: OpenAI `text-embedding-3-large` or Cohere

#### 3.2 Embedding Service Architecture

```python
# Abstracted embedding service for extensibility
from abc import ABC, abstractmethod

class EmbeddingService(ABC):
    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        pass
    
    @abstractmethod
    def embed_query(self, query: str) -> List[float]:
        pass

class OpenAIEmbedding(EmbeddingService):
    def __init__(self, model="text-embedding-3-small"):
        self.model = model
        self.client = OpenAI()
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        response = self.client.embeddings.create(input=texts, model=self.model)
        return [r.embedding for r in response.data]

class LocalEmbedding(EmbeddingService):
    def __init__(self, model_name="BAAI/bge-large-en-v1.5"):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name)
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.model.encode(texts).tolist()

# Factory for easy switching
def get_embedding_service(provider: str = "openai") -> EmbeddingService:
    providers = {
        "openai": OpenAIEmbedding,
        "local": LocalEmbedding,
    }
    return providers[provider]()
```

---

### 4. Retrieval Layer

#### 4.1 Multi-Stage Retrieval Pipeline

```
User Query
    │
    ▼
┌──────────────────┐
│ Query Embedding  │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Vector Search    │ ← Top-K (k=50-100)
│ (Semantic Match) │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Metadata Filter  │ ← Department, Year, etc.
│ (Optional)       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Re-ranking       │ ← Cross-encoder or custom scoring
│                  │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Final Results    │ ← Top-K (k=5-10)
└──────────────────┘
```

#### 4.2 Retrieval Implementation

```python
class ScholarRetriever:
    def __init__(self, vector_store, reranker=None):
        self.vector_store = vector_store
        self.reranker = reranker
    
    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        filters: dict = None,
        ranking_weights: dict = None
    ) -> List[RetrievalResult]:
        """
        Multi-stage retrieval with re-ranking
        """
        # Stage 1: Vector search
        query_embedding = self.embed_query(query)
        candidates = self.vector_store.search(
            embedding=query_embedding,
            top_k=50,  # Over-retrieve for re-ranking
            filters=filters
        )
        
        # Stage 2: Re-ranking
        if self.reranker:
            candidates = self.reranker.rerank(query, candidates)
        
        # Stage 3: Custom scoring (recency, citations, etc.)
        if ranking_weights:
            candidates = self.apply_custom_ranking(candidates, ranking_weights)
        
        return candidates[:top_k]
    
    def apply_custom_ranking(self, candidates, weights):
        """
        weights = {
            "semantic_score": 0.5,
            "recency": 0.2,      # Boost recent content
            "citations": 0.2,    # Boost highly-cited scholars
            "source_quality": 0.1
        }
        """
        for c in candidates:
            c.final_score = (
                weights["semantic_score"] * c.similarity_score +
                weights["recency"] * self._recency_score(c.metadata["last_updated"]) +
                weights["citations"] * self._normalize_citations(c.metadata["citation_count"]) +
                weights["source_quality"] * self._source_quality_score(c.metadata["source_type"])
            )
        return sorted(candidates, key=lambda x: x.final_score, reverse=True)
```

#### 4.3 Hybrid Search (Production Enhancement)

```python
# Combine vector search with keyword search for better recall
class HybridRetriever:
    def retrieve(self, query: str, alpha: float = 0.7):
        # Vector search (semantic)
        vector_results = self.vector_search(query)
        
        # BM25/keyword search (lexical)
        keyword_results = self.keyword_search(query)
        
        # Reciprocal Rank Fusion
        combined = self.rrf_fusion(
            vector_results, 
            keyword_results, 
            alpha=alpha  # Weight towards semantic
        )
        return combined
```

---

### 5. Generation Layer (LLM)

#### 5.1 LLM Options

| Model | Cost | Quality | Speed | Context | POC | Prod |
|-------|------|---------|-------|---------|-----|------|
| **GPT-4o** | $2.50/1M in, $10/1M out | Excellent | Fast | 128K | ✅ | ✅ |
| **GPT-4o-mini** | $0.15/1M in, $0.60/1M out | Very Good | Very Fast | 128K | ✅ | ✅ |
| **Claude 3.5 Sonnet** | $3/1M in, $15/1M out | Excellent | Fast | 200K | ✅ | ✅ |
| **Claude 3.5 Haiku** | $0.25/1M in, $1.25/1M out | Good | Very Fast | 200K | ✅ | ✅ |
| **Llama 3.1 70B** | Free (self-host) | Very Good | Medium | 128K | ⚠️ | ✅ |
| **Mixtral 8x7B** | Free (self-host) | Good | Fast | 32K | ⚠️ | ✅ |

**Recommendation**:
- **POC**: GPT-4o-mini (best cost/quality tradeoff)
- **Production**: GPT-4o or Claude 3.5 Sonnet (quality) OR Llama 3.1-70B (cost)

#### 5.2 Prompt Engineering

```python
SYSTEM_PROMPT = """You are an NYU Research Scholar Search Assistant. Your role is to help users find relevant faculty members and their research.

INSTRUCTIONS:
1. Always base your responses on the provided context
2. When recommending scholars, explain WHY they match the query
3. Include relevant details: research areas, recent publications, contact info
4. If the context doesn't contain enough information, say so clearly
5. Format responses clearly with scholar name, relevance, and key details

RESPONSE FORMAT:
For each relevant scholar, provide:
- Name and Department
- Why they match the query
- Relevant publications/research
- Website link (if available)
"""

RAG_PROMPT_TEMPLATE = """
Based on the following context about NYU research scholars, answer the user's query.

CONTEXT:
{retrieved_context}

USER QUERY: {query}

Provide a helpful response that:
1. Identifies the most relevant scholar(s)
2. Explains their relevance to the query
3. Includes specific details from the context
4. Cites sources where possible

RESPONSE:
"""
```

#### 5.3 Response Generation with Grounding

```python
class ResponseGenerator:
    def __init__(self, llm_client, system_prompt: str):
        self.llm = llm_client
        self.system_prompt = system_prompt
    
    def generate(
        self, 
        query: str, 
        retrieved_docs: List[Document],
        temperature: float = 0.3  # Low for factual responses
    ) -> GeneratedResponse:
        # Build context from retrieved docs
        context = self._build_context(retrieved_docs)
        
        # Generate response
        response = self.llm.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": RAG_PROMPT_TEMPLATE.format(
                    retrieved_context=context,
                    query=query
                )}
            ],
            temperature=temperature
        )
        
        # Add source citations
        return GeneratedResponse(
            answer=response.choices[0].message.content,
            sources=[doc.source_url for doc in retrieved_docs],
            scholars=[doc.scholar_name for doc in retrieved_docs]
        )
    
    def _build_context(self, docs: List[Document]) -> str:
        context_parts = []
        for i, doc in enumerate(docs):
            context_parts.append(f"""
[Source {i+1}]
Scholar: {doc.scholar_name}
Department: {doc.metadata.get('department', 'N/A')}
Source: {doc.source_url}
Content: {doc.content}
---""")
        return "\n".join(context_parts)
```

---

### 6. API Design

#### 6.1 REST API Endpoints

```yaml
# OpenAPI-style specification
endpoints:
  # Main search endpoint
  POST /api/v1/search:
    description: Semantic search for scholars and their work
    request:
      query: string (required)
      filters:
        department: string[]
        research_area: string[]
        min_citations: int
      limit: int (default: 10)
      include_context: bool (default: true)
    response:
      scholars: Scholar[]
      answer: string  # LLM-generated response
      sources: Source[]
      query_metadata:
        processing_time_ms: int
        total_results: int

  # Scholar profile lookup
  GET /api/v1/scholars/{scholar_id}:
    description: Get detailed scholar profile
    response:
      scholar: Scholar
      publications: Publication[]
      research_summary: string

  # Autocomplete/suggestions
  GET /api/v1/suggest:
    description: Query suggestions and autocomplete
    request:
      partial_query: string
    response:
      suggestions: string[]
      popular_searches: string[]

  # Admin: Trigger re-indexing
  POST /api/v1/admin/reindex:
    description: Trigger content re-crawling
    request:
      scope: "all" | "scholar_id" | "department"
      target: string
```

#### 6.2 FastAPI Implementation Skeleton

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="NYU Scholar Search API", version="1.0.0")

class SearchRequest(BaseModel):
    query: str
    filters: Optional[dict] = None
    limit: int = 10
    include_context: bool = True

class SearchResponse(BaseModel):
    answer: str
    scholars: List[dict]
    sources: List[str]
    processing_time_ms: int

@app.post("/api/v1/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    start_time = time.time()
    
    # 1. Retrieve relevant documents
    retrieved_docs = retriever.retrieve(
        query=request.query,
        filters=request.filters,
        top_k=request.limit
    )
    
    # 2. Generate response
    response = generator.generate(
        query=request.query,
        retrieved_docs=retrieved_docs
    )
    
    processing_time = int((time.time() - start_time) * 1000)
    
    return SearchResponse(
        answer=response.answer,
        scholars=response.scholars,
        sources=response.sources,
        processing_time_ms=processing_time
    )

@app.get("/api/v1/health")
async def health():
    return {"status": "healthy"}
```

---

### 7. Evaluation & Testing

#### 7.1 Evaluation Metrics

| Metric | What it Measures | Target |
|--------|------------------|--------|
| **Retrieval Recall@K** | % of relevant docs in top-K | >80% |
| **Retrieval MRR** | Mean Reciprocal Rank | >0.7 |
| **Answer Relevance** | LLM-judged relevance (1-5) | >4.0 |
| **Faithfulness/Grounding** | Is answer supported by context? | >95% |
| **Answer Correctness** | Factual accuracy | >90% |
| **Latency P50/P95** | Response time | <2s / <5s |

#### 7.2 Evaluation Framework

```python
class RAGEvaluator:
    def __init__(self, test_dataset: List[dict]):
        """
        test_dataset format:
        [
            {
                "query": "Who works on NLP at NYU?",
                "expected_scholars": ["Dr. Smith", "Dr. Johnson"],
                "expected_topics": ["NLP", "language models"],
                "ground_truth_answer": "..."
            }
        ]
        """
        self.test_dataset = test_dataset
    
    def evaluate_retrieval(self, retriever) -> dict:
        metrics = {"recall@5": [], "recall@10": [], "mrr": []}
        for sample in self.test_dataset:
            results = retriever.retrieve(sample["query"], top_k=10)
            # Calculate metrics...
        return {k: np.mean(v) for k, v in metrics.items()}
    
    def evaluate_generation(self, pipeline) -> dict:
        """Use LLM-as-judge for quality assessment"""
        metrics = {"relevance": [], "faithfulness": [], "correctness": []}
        for sample in self.test_dataset:
            response = pipeline.run(sample["query"])
            # Use GPT-4 to judge quality...
        return {k: np.mean(v) for k, v in metrics.items()}
    
    def check_hallucination(self, answer: str, context: str) -> bool:
        """Verify all claims in answer are grounded in context"""
        pass
```

#### 7.3 Testing Checklist

- [ ] Unit tests for each component (embedder, retriever, generator)
- [ ] Integration tests for full RAG pipeline
- [ ] Evaluation on held-out test set
- [ ] Hallucination detection tests
- [ ] Latency benchmarks under load
- [ ] Edge case handling (empty results, long queries, ambiguous queries)

---

### 8. Infrastructure & Deployment

#### 8.1 POC Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Local/Dev Machine                  │
│                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │ FastAPI App │  │ Chroma DB   │  │ SQLite      │ │
│  │ (localhost) │  │ (local)     │  │ (metadata)  │ │
│  └─────────────┘  └─────────────┘  └─────────────┘ │
│                                                     │
│   External APIs: OpenAI (embeddings + LLM)          │
└─────────────────────────────────────────────────────┘
```

**POC Stack**:
- Python + FastAPI
- Chroma (local vector store)
- SQLite (metadata)
- OpenAI APIs
- Streamlit or Gradio (quick UI)

#### 8.2 Production Architecture

```
                    ┌─────────────────┐
                    │   CloudFlare    │
                    │   (CDN + WAF)   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Load Balancer  │
                    │   (AWS ALB)     │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
    ┌────▼────┐         ┌────▼────┐        ┌────▼────┐
    │ API Pod │         │ API Pod │        │ API Pod │
    │ (K8s)   │         │ (K8s)   │        │ (K8s)   │
    └────┬────┘         └────┬────┘        └────┬────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
         ┌────▼────┐   ┌─────▼─────┐  ┌─────▼─────┐
         │ Qdrant  │   │ PostgreSQL│  │   Redis   │
         │ Cluster │   │   (RDS)   │  │  (Cache)  │
         └─────────┘   └───────────┘  └───────────┘

    ┌─────────────────────────────────────────────────┐
    │            Background Workers (K8s Jobs)         │
    │  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
    │  │ Crawler  │  │ Embedder │  │ Index Updater│   │
    │  └──────────┘  └──────────┘  └──────────────┘   │
    └─────────────────────────────────────────────────┘
```

#### 8.3 Cost Estimates

| Component | POC (Monthly) | Production (Monthly) |
|-----------|---------------|----------------------|
| Compute (API servers) | $0 (local) | $200-500 (3x t3.medium) |
| Vector DB | $0 (Chroma) | $70-200 (Pinecone/self-hosted) |
| PostgreSQL | $0 (SQLite) | $50-100 (RDS) |
| OpenAI Embeddings | ~$5 (initial indexing) | $20-50 |
| OpenAI LLM | $20-50 | $100-500 (depends on traffic) |
| **Total** | **~$25-55** | **~$440-1350** |

---

### 9. Extensibility Design

The system is designed with extensibility in mind:

#### 9.1 Plugin Architecture

```python
# Abstract interfaces for swappable components
from abc import ABC, abstractmethod

class DataSourcePlugin(ABC):
    """Add new data sources easily"""
    @abstractmethod
    def fetch(self) -> List[Document]: pass
    @abstractmethod
    def get_source_type(self) -> str: pass

class EmbeddingPlugin(ABC):
    """Swap embedding providers"""
    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]: pass

class LLMPlugin(ABC):
    """Swap LLM providers"""
    @abstractmethod
    def generate(self, prompt: str) -> str: pass

class RetrieverPlugin(ABC):
    """Custom retrieval strategies"""
    @abstractmethod
    def retrieve(self, query: str, k: int) -> List[Document]: pass
```

#### 9.2 Future Extension Points

| Extension | Effort | Value |
|-----------|--------|-------|
| Add Google Scholar integration | Medium | High - more citation data |
| Multi-university support | Medium | High - broader coverage |
| Real-time alerts for new publications | Medium | Medium - proactive notifications |
| Conversational interface (multi-turn) | Low | Medium - better UX |
| Research collaboration finder | High | High - network analysis |
| Publication similarity search | Low | Medium - "papers like this" |
| Department-level analytics | Medium | Medium - admin insights |

#### 9.3 Configuration-Driven Design

```yaml
# config.yaml - Easy to modify without code changes
data_sources:
  - type: "website_catalog"
    url: "https://cs.nyu.edu/people/faculty"
    crawl_depth: 3
    cadence: "weekly"
  
  - type: "semantic_scholar"
    query_template: "author:{scholar_name} institution:NYU"
    cadence: "monthly"

embedding:
  provider: "openai"  # or "local", "cohere"
  model: "text-embedding-3-small"
  
retrieval:
  vector_top_k: 50
  final_top_k: 10
  reranker: "cross-encoder"
  ranking_weights:
    semantic: 0.5
    recency: 0.25
    citations: 0.25

llm:
  provider: "openai"
  model: "gpt-4o-mini"
  temperature: 0.3
  max_tokens: 1000
```

---

### 10. Implementation Roadmap

#### Phase 1: POC (2-3 weeks)
- [ ] Set up basic project structure
- [ ] Implement catalog page scraper
- [ ] Scrape 10-20 faculty websites
- [ ] Set up Chroma + OpenAI embeddings
- [ ] Implement basic RAG pipeline
- [ ] Create simple Streamlit UI
- [ ] Manual testing with sample queries

#### Phase 2: Enhanced POC (2-3 weeks)
- [ ] Add metadata filtering
- [ ] Implement re-ranking
- [ ] Add evaluation framework
- [ ] Improve prompts based on testing
- [ ] Add basic error handling
- [ ] Deploy to cloud (single instance)

#### Phase 3: Production-Ready (4-6 weeks)
- [ ] Switch to production vector DB
- [ ] Implement scheduled crawling
- [ ] Add caching layer
- [ ] Implement monitoring/logging
- [ ] Add authentication
- [ ] Load testing + optimization
- [ ] CI/CD pipeline

#### Phase 4: Scale & Extend (ongoing)
- [ ] Multi-university support
- [ ] Advanced analytics
- [ ] User feedback loop
- [ ] A/B testing framework

---

## Quick Start: POC Setup

```bash
# 1. Create project
mkdir nyu-scholar-search && cd nyu-scholar-search
python -m venv venv && source venv/bin/activate  # or venv\Scripts\activate on Windows

# 2. Install dependencies
pip install fastapi uvicorn openai chromadb beautifulsoup4 requests langchain pydantic

# 3. Project structure
mkdir -p src/{ingestion,retrieval,generation,api}
touch src/__init__.py src/config.py src/main.py

# 4. Set environment variables
echo "OPENAI_API_KEY=sk-..." > .env

# 5. Run
uvicorn src.main:app --reload
```

---

## Key Design Decisions Summary

| Decision | POC Choice | Production Choice | Rationale |
|----------|------------|-------------------|-----------|
| Vector DB | Chroma | Qdrant/Pinecone | Simplicity → Scale |
| Embeddings | OpenAI small | OpenAI large or BGE | Cost → Quality |
| LLM | GPT-4o-mini | GPT-4o | Cost → Quality |
| Chunking | Fixed 800 tokens | Semantic + Hierarchical | Simple → Accurate |
| Retrieval | Vector only | Hybrid + Reranking | Simple → Complete |
| Hosting | Local | K8s on AWS/GCP | None → Scalable |
