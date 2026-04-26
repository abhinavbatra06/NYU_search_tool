import { useEffect, useState } from 'react'
import {
  hasSupabaseConfig,
  isRecoveryFlowFromUrl,
  sendPasswordReset,
  signIn,
  signUp,
  updatePassword,
} from '../lib/supabase'

interface LoginGateProps {
  onLoginSuccess: () => void
}

type Mode = 'signin' | 'signup'
type ExtendedMode = Mode | 'forgot' | 'reset'

function LoginGate({ onLoginSuccess: _onLoginSuccess }: LoginGateProps) {
  const [mode, setMode] = useState<ExtendedMode>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (isRecoveryFlowFromUrl()) {
      setMode('reset')
      setMessage('Set your new password below.')
      setError('')
    }
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setMessage('')
    setLoading(true)

    try {
      if (!hasSupabaseConfig()) {
        throw new Error('Supabase is not configured in frontend/.env.local')
      }

      if ((mode === 'signin' || mode === 'signup') && (!email.trim() || !password.trim())) {
        throw new Error('Please enter your email and password.')
      }

      if (mode === 'signup') {
        const msg = await signUp(email.trim(), password)
        setMessage(msg)
      } else if (mode === 'signin') {
        await signIn(email.trim(), password)
        // onAuthStateChange in App.tsx handles the session transition automatically
      } else if (mode === 'forgot') {
        if (!email.trim()) {
          throw new Error('Please enter your NYU email.')
        }
        const msg = await sendPasswordReset(email.trim())
        setMessage(msg)
      } else if (mode === 'reset') {
        if (!password.trim() || !confirmPassword.trim()) {
          throw new Error('Please enter and confirm your new password.')
        }
        if (password !== confirmPassword) {
          throw new Error('Passwords do not match.')
        }

        const msg = await updatePassword(password)
        setMessage(msg)
        setMode('signin')
        setPassword('')
        setConfirmPassword('')
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
        {mode === 'signin' && 'Sign in with your NYU email to search faculty.'}
        {mode === 'signup' && 'Create an account with your NYU email.'}
        {mode === 'forgot' && 'Enter your NYU email to receive a password reset link.'}
        {mode === 'reset' && 'Create a new password for your account.'}
      </p>

      <form onSubmit={handleSubmit}>
        {mode !== 'reset' && (
          <>
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
          </>
        )}

        <label htmlFor="password" style={{ display: 'block', marginBottom: '8px', fontWeight: 'bold' }}>
          {mode === 'reset' ? 'New Password' : 'Password'}
        </label>
        <input
          id="password"
          type="password"
          placeholder={mode === 'signup' || mode === 'reset' ? 'Create a password' : 'Your password'}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          disabled={loading}
          style={{ width: '100%', marginBottom: '20px' }}
        />

        {mode === 'reset' && (
          <>
            <label htmlFor="confirm-password" style={{ display: 'block', marginBottom: '8px', fontWeight: 'bold' }}>
              Confirm New Password
            </label>
            <input
              id="confirm-password"
              type="password"
              placeholder="Re-enter new password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              disabled={loading}
              style={{ width: '100%', marginBottom: '20px' }}
            />
          </>
        )}

        {error && <div className="error">{error}</div>}
        {message && <div className="loading" style={{ color: '#2a7a2a' }}>{message}</div>}

        <button type="submit" disabled={loading} style={{ width: '100%' }}>
          {loading && 'Please wait...'}
          {!loading && mode === 'signin' && 'Sign In'}
          {!loading && mode === 'signup' && 'Create Account'}
          {!loading && mode === 'forgot' && 'Send Reset Link'}
          {!loading && mode === 'reset' && 'Update Password'}
        </button>
      </form>

      {mode === 'signin' && (
        <p style={{ marginTop: '10px', fontSize: '13px', textAlign: 'center' }}>
          <button
            onClick={() => { setMode('forgot'); setError(''); setMessage(''); setPassword('') }}
            style={{ background: 'none', border: 'none', color: '#0066cc', cursor: 'pointer', padding: 0, fontSize: '13px' }}
          >
            Forgot password?
          </button>
        </p>
      )}

      <p style={{ marginTop: '20px', fontSize: '13px', color: '#666', textAlign: 'center' }}>
        {mode === 'signin' ? (
          <>No account? <button onClick={() => { setMode('signup'); setError(''); setMessage('') }} style={{ background: 'none', border: 'none', color: '#0066cc', cursor: 'pointer', padding: 0, fontSize: '13px' }}>Create one</button></>
        ) : mode === 'signup' ? (
          <>Already have an account? <button onClick={() => { setMode('signin'); setError(''); setMessage('') }} style={{ background: 'none', border: 'none', color: '#0066cc', cursor: 'pointer', padding: 0, fontSize: '13px' }}>Sign in</button></>
        ) : (
          <>Back to sign in? <button onClick={() => { setMode('signin'); setError(''); setMessage(''); setPassword(''); setConfirmPassword('') }} style={{ background: 'none', border: 'none', color: '#0066cc', cursor: 'pointer', padding: 0, fontSize: '13px' }}>Sign in</button></>
        )}
      </p>

      <p style={{ marginTop: '8px', fontSize: '11px', color: '#999', textAlign: 'center' }}>
        Access restricted to @nyu.edu addresses. Minimum password length: 8 characters.
      </p>

      <p style={{ marginTop: '8px', fontSize: '11px', color: '#999', textAlign: 'center' }}>
        For password reset links, add your site URL to Supabase Auth Redirect URLs.
      </p>
    </div>
  )
}

export default LoginGate
