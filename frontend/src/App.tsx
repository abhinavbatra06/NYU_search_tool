import { useState, useEffect } from 'react'
import LoginGate from './components/LoginGate'
import SearchUI from './components/SearchUI'
import { isAuthenticated, supabase } from './lib/supabase'

function App() {
  const [loggedIn, setLoggedIn] = useState(false)
  const [loading, setLoading] = useState(true)

  // Check if user is already logged in when app loads
  useEffect(() => {
    let isMounted = true

    const initializeAuth = async () => {
      const authenticated = await isAuthenticated()
      if (isMounted) {
        setLoggedIn(authenticated)
        setLoading(false)
      }
    }

    initializeAuth()

    if (!supabase) {
      return () => {
        isMounted = false
      }
    }

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      if (isMounted) {
        setLoggedIn(Boolean(session))
      }
    })

    return () => {
      isMounted = false
      subscription.unsubscribe()
    }
  }, [])

  const handleLogin = () => {
    setLoggedIn(true)
  }

  const handleLogout = () => {
    setLoggedIn(false)
  }

  if (loading) {
    return (
      <div className="container">
        <p className="loading">Loading...</p>
      </div>
    )
  }

  if (!loggedIn) {
    return <LoginGate onLoginSuccess={handleLogin} />
  }

  return <SearchUI onLogout={handleLogout} />
}

export default App
