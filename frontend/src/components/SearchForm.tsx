import { useState } from 'react'

interface SearchFormProps {
  onSearch: (query: string) => void
  loading: boolean
}

function SearchForm({ onSearch, loading }: SearchFormProps) {
  const [query, setQuery] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (query.trim()) {
      onSearch(query)
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{ marginBottom: '30px' }}>
      <label htmlFor="search-query" style={{ display: 'block', marginBottom: '10px', fontWeight: 'bold' }}>
        What are you looking for?
      </label>
      <div style={{ display: 'flex', gap: '10px' }}>
        <input
          id="search-query"
          type="text"
          placeholder="e.g., climate change, data science, social networks"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          disabled={loading}
          style={{ flex: 1 }}
        />
        <button type="submit" disabled={loading || !query.trim()}>
          {loading ? 'Searching...' : 'Search'}
        </button>
      </div>
    </form>
  )
}

export default SearchForm
