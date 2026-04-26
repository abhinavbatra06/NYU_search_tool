import { useState } from 'react'
import { searchFaculty, SearchResponse } from '../lib/api'
import { logout } from '../lib/supabase'
import SearchForm from './SearchForm'
import ResultsPanel from './ResultsPanel'

interface SearchUIProps {
  onLogout: () => void
}

function SearchUI({ onLogout }: SearchUIProps) {
  const [results, setResults] = useState<SearchResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSearch = async (query: string) => {
    setError('')
    setLoading(true)
    setResults(null)

    try {
      const response = await searchFaculty(query)
      setResults(response)
    } catch (err) {
      setError(`Search failed: ${err instanceof Error ? err.message : 'Unknown error'}`)
    } finally {
      setLoading(false)
    }
  }

  const handleLogout = async () => {
    await logout()
    onLogout()
  }

  return (
    <div className="container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px' }}>
        <h1>Faculty Search</h1>
        <button onClick={handleLogout} style={{ backgroundColor: '#999' }}>
          Logout
        </button>
      </div>

      <SearchForm onSearch={handleSearch} loading={loading} />

      {error && <div className="error">{error}</div>}

      {loading && <div className="loading">Searching...</div>}

      {results && <ResultsPanel results={results} />}
    </div>
  )
}

export default SearchUI
