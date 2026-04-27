import { useState, useRef, useEffect } from 'react'
import { searchFaculty, SearchResponse } from '../lib/api'

interface Turn {
  query: string
  response: SearchResponse | null
  error: string | null
}

const EXAMPLES = [
  'Who works on urban inequality?',
  'Faculty researching climate and cities',
  'Experts in machine learning and society',
  'Qualitative sociology researchers',
]

// Render answer text: convert markdown links [text](url) to <a> tags and newlines to <p>
function AnswerText({ text }: { text: string }) {
  const linkRegex = /\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g
  const paragraphs = text.split(/\n+/).filter(p => p.trim())

  return (
    <div className="answer-text">
      {paragraphs.map((para, i) => {
        const parts: React.ReactNode[] = []
        let last = 0
        let match: RegExpExecArray | null
        linkRegex.lastIndex = 0
        while ((match = linkRegex.exec(para)) !== null) {
          if (match.index > last) parts.push(para.slice(last, match.index))
          parts.push(
            <a key={match.index} href={match[2]} target="_blank" rel="noopener noreferrer">
              {match[1]}
            </a>
          )
          last = match.index + match[0].length
        }
        if (last < para.length) parts.push(para.slice(last))
        return <p key={i}>{parts}</p>
      })}
    </div>
  )
}

function FacultyChips({ results, max, label }: { results: SearchResponse['results'], max: number, label: string }) {
  const seen = new Set<string>()
  const unique = results.filter(r => {
    if (seen.has(r.faculty.name)) return false
    seen.add(r.faculty.name)
    return true
  }).slice(0, max)

  if (unique.length === 0) return null

  return (
    <div>
      <div className="faculty-section-label">{label}</div>
      <div className="faculty-list">
        {unique.map((r, i) =>
          r.faculty.url ? (
            <a key={i} href={r.faculty.url} target="_blank" rel="noopener noreferrer" className="faculty-link">
              {r.faculty.name} ↗
            </a>
          ) : (
            <span key={i} className="faculty-no-link">{r.faculty.name}</span>
          )
        )}
      </div>
    </div>
  )
}

function MoreFacultyChips({ results }: { results: SearchResponse['results'] }) {
  const [open, setOpen] = useState(false)

  // Deduplicate all, skip first 5
  const seen = new Set<string>()
  const all = results.filter(r => {
    if (seen.has(r.faculty.name)) return false
    seen.add(r.faculty.name)
    return true
  })
  const extra = all.slice(5, 8)

  if (extra.length === 0) return null

  return (
    <div style={{ marginTop: '8px' }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          background: 'none',
          border: 'none',
          color: 'var(--text-muted)',
          fontSize: '12px',
          cursor: 'pointer',
          padding: '4px 0',
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
        }}
      >
        {open ? '▲ Hide' : `▼ ${extra.length} more result${extra.length > 1 ? 's' : ''}`}
      </button>
      {open && (
        <div className="faculty-list" style={{ marginTop: '8px' }}>
          {extra.map((r, i) =>
            r.faculty.url ? (
              <a key={i} href={r.faculty.url} target="_blank" rel="noopener noreferrer" className="faculty-link" style={{ opacity: 0.75 }}>
                {r.faculty.name} ↗
              </a>
            ) : (
              <span key={i} className="faculty-no-link" style={{ opacity: 0.75 }}>{r.faculty.name}</span>
            )
          )}
        </div>
      )}
    </div>
  )
}

function SearchUI() {
  const [turns, setTurns] = useState<Turn[]>([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [turns, loading])

  const submit = async (q: string) => {
    const trimmed = q.trim()
    if (!trimmed || loading) return
    setQuery('')
    setLoading(true)
    setTurns(prev => [...prev, { query: trimmed, response: null, error: null }])

    try {
      const response = await searchFaculty(trimmed)
      setTurns(prev => {
        const next = [...prev]
        next[next.length - 1] = { query: trimmed, response, error: null }
        return next
      })
    } catch (err) {
      setTurns(prev => {
        const next = [...prev]
        next[next.length - 1] = {
          query: trimmed,
          response: null,
          error: err instanceof Error ? err.message : 'Unknown error',
        }
        return next
      })
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit(query)
    }
  }

  return (
    <div className="app-shell">
      {/* Header */}
      <header className="app-header">
        <span className="nyu-wordmark">NYU</span>
        <span className="app-title">Faculty Research Search</span>
        <span style={{
          marginLeft: 'auto',
          fontSize: '11px',
          fontWeight: 600,
          background: 'rgba(255,255,255,0.15)',
          border: '1px solid rgba(255,255,255,0.3)',
          borderRadius: '12px',
          padding: '3px 10px',
          letterSpacing: '0.5px',
          textTransform: 'uppercase',
          opacity: 0.85,
        }}>
          Each search is independent
        </span>
      </header>

      {/* Chat area */}
      <div className="chat-area">
        <div className="chat-inner">
          {turns.length === 0 && !loading && (
            <div className="empty-state">
              <h2>Find NYU Faculty by Research Interest</h2>
              <p>Ask a research question or describe a topic to find matching faculty.</p>
              <div className="example-chips">
                {EXAMPLES.map(ex => (
                  <button key={ex} className="chip" onClick={() => submit(ex)}>
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          )}

          {turns.map((turn, i) => (
            <div key={i}>
              <div className="turn-query">
                <div className="turn-query-bubble">{turn.query}</div>
              </div>

              {turn.error && (
                <div className="error-bubble">{turn.error}</div>
              )}

              {turn.response && (
                <>
                  {!turn.response.answer.startsWith('I can only help') && (
                    <FacultyChips results={turn.response.results} max={5} label="Top Matches" />
                  )}
                  <div style={{ marginTop: '16px' }}>
                    <div className="answer-card">
                      <div className="answer-label">AI Summary</div>
                      <AnswerText text={turn.response.answer || 'No answer generated.'} />
                      <div style={{ marginTop: '14px', paddingTop: '12px', borderTop: '1px solid #e2d0f0', fontSize: '12px', color: '#999' }}>
                        AI-generated summary — results may be incomplete or inaccurate. Always verify directly with faculty profiles.
                      </div>
                    </div>
                  </div>
                  {!turn.response.answer.startsWith('I can only help') && (
                    <MoreFacultyChips results={turn.response.results} />
                  )}
                </>
              )}
            </div>
          ))}

          {loading && (
            <div className="loading-turn">
              <div className="dot-pulse">
                <span /><span /><span />
              </div>
              Searching faculty...
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input bar */}
      <div className="input-bar">
        <div className="input-bar-inner">
          <input
            className="search-input"
            type="text"
            placeholder="Ask about a research topic, method, or interest..."
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
            autoFocus
          />
          <button
            className="send-btn"
            onClick={() => submit(query)}
            disabled={loading || !query.trim()}
            aria-label="Search"
          >
            ↑
          </button>
        </div>
        <div className="input-hint">Each search is independent — previous results are not carried forward</div>
      </div>
    </div>
  )
}

export default SearchUI
