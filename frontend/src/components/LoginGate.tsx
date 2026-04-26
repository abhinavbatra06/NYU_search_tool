import { useState } from 'react'
import { hasSupabaseConfig, signIn, signUp } from '../lib/supabase'

interface LoginGateProps {
  onLoginSuccess: () => void
}

type Mode = 'signin' | 'signup'

function LoginGate({ onLoginSuccess: _onLoginSuccess }: LoginGateProps) {
  const [mode, setMode] = useState<Mode>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setMessage('')
    setLoading(true)

    try {
      if (!hasSupabaseConfig()) {
        throw new Error('Supabase is not configured in frontend/.env.local')
      }

      if (!email.trim() || !password.trim()) {
        throw new Error('Please enter your email and password.')
      }

      if (mode === 'signup') {
        const msg = await signUp(email.trim(), password)
        setMessage(msg)
      } else {
        await signIn(email.trim(), password)
        // onAuthStateChange in App.tsx handles the session transition automatically
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="container" style={{ maxWidth: '400px', marginTop: '50px' }}>
      <h1>NYU Faculty Search</h1>
      <p style={{ marginBottom: '20px', color: '#666' }}>
        {mode === 'signin' ? 'Sign in with your NYU email to search faculty.' : 'Create an account with your NYU email.'}
      </p>

      <form onSubmit={handleSubmit}>
        <label htmlFor="email" style={{ display: 'block', marginBottom: '8px', fontWeight: 'bold' }}>
          NYU Email
        </label>
        <input
          id="email"
          type="email"
          placeholder="netid@nyu.edu"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          disabled={loading}
          style={{ width: '100%', marginBottom: '16px' }}
        />

        <label htmlFor="password" style={{ display: 'block', marginBottom: '8px', fontWeight: 'bold' }}>
          Password
        </label>
        <input
          id="password"
          type="password"
          placeholder={mode === 'signup' ? 'Create a password' : 'Your password'}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          disabled={loading}
          style={{ width: '100%', marginBottom: '20px' }}
        />

        {error && <div className="error">{error}</div>}
        {message && <div className="loading" style={{ color: '#2a7a2a' }}>{message}</div>}

        <button type="submit" disabled={loading} style={{ width: '100%' }}>
          {loading ? 'Please wait...' : mode === 'signin' ? 'Sign In' : 'Create Account'}
        </button>
      </form>

      <p style={{ marginTop: '20px', fontSize: '13px', color: '#666', textAlign: 'center' }}>
        {mode === 'signin' ? (
          <>No account? <button onClick={() => { setMode('signup'); setError(''); setMessage('') }} style={{ background: 'none', border: 'none', color: '#0066cc', cursor: 'pointer', padding: 0, fontSize: '13px' }}>Create one</button></>
        ) : (
          <>Already have an account? <button onClick={() => { setMode('signin'); setError(''); setMessage('') }} style={{ background: 'none', border: 'none', color: '#0066cc', cursor: 'pointer', padding: 0, fontSize: '13px' }}>Sign in</button></>
        )}
      </p>

      <p style={{ marginTop: '8px', fontSize: '11px', color: '#999', textAlign: 'center' }}>
        Access restricted to @nyu.edu addresses.
      </p>
    </div>
  )
}

export default LoginGate
