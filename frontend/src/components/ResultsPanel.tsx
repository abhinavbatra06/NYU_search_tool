import { SearchResponse } from '../lib/api'

interface ResultsPanelProps {
  results: SearchResponse
}

function ResultsPanel({ results }: ResultsPanelProps) {
  return (
    <div>
      <h2>Answer</h2>
      <div style={{ backgroundColor: 'white', padding: '15px', borderRadius: '4px', marginBottom: '30px', lineHeight: '1.6' }}>
        {results.answer || 'No answer generated for this query.'}
      </div>

      <h2>Faculty Results ({results.results.length})</h2>
      {results.results.length === 0 ? (
        <p style={{ color: '#999' }}>No faculty found matching your search.</p>
      ) : (
        <div>
          {results.results.map((result, index) => (
            <div key={index} style={{ backgroundColor: 'white', padding: '15px', marginBottom: '15px', borderRadius: '4px', borderLeft: '4px solid #0066cc' }}>
              <h3 style={{ marginBottom: '5px' }}>{result.faculty.name}</h3>
              <p style={{ marginBottom: '10px', fontSize: '14px', color: '#666' }}>
                Faculty ID: {result.faculty.faculty_id} • Relevance: {(result.score * 100).toFixed(0)}%
              </p>

              {result.faculty.paper_title && (
                <p style={{ marginBottom: '10px' }}>
                  <strong>Paper:</strong> {result.faculty.paper_title}
                  {result.faculty.year && ` (${result.faculty.year})`}
                </p>
              )}

              <p style={{ marginBottom: '10px', fontSize: '14px', color: '#555' }}>
                {result.content.substring(0, 200)}...
              </p>

              {result.faculty.url && (
                <a
                  href={result.faculty.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: '#0066cc', textDecoration: 'none' }}
                >
                  View full profile →
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default ResultsPanel
