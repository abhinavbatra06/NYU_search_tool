// Simple API client for the backend search endpoint
import { getAuthToken } from './supabase'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
const API_BASE = `${API_BASE_URL}/api/v1`

export interface SearchResult {
  content: string
  faculty: {
    name: string
    faculty_id: string
    chunk_type: string
    url?: string
    paper_title?: string
    year?: number
    relevance_score: number
  }
  score: number
}

export interface SearchResponse {
  results: SearchResult[]
  answer: string
  query: string
  timestamp: string
}

// Make a search request to the backend
export async function searchFaculty(
  query: string,
  useHybrid: boolean = true
): Promise<SearchResponse> {
  const token = await getAuthToken()
  if (!token) {
    throw new Error('Not authenticated. Please sign in again.')
  }

  const response = await fetch(`${API_BASE}/search`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify({
      query: query,
      n_results: 5,
      use_hybrid: useHybrid,
    }),
  })

  if (!response.ok) {
    const error = await response.text()
    throw new Error(`Search failed: ${error}`)
  }

  const data = await response.json()
  return data
}

// Check if the backend is healthy
export async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/health`)
    return response.ok
  } catch {
    return false
  }
}
