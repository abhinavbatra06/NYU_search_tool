import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string | undefined
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined

const isSupabaseConfigured = Boolean(supabaseUrl && supabaseAnonKey)
const MIN_PASSWORD_LENGTH = 8

export const supabase = isSupabaseConfigured
  ? createClient(supabaseUrl as string, supabaseAnonKey as string)
  : null

export function hasSupabaseConfig(): boolean {
  return isSupabaseConfigured
}

function assertSupabaseConfigured(): void {
  if (!supabase) {
    throw new Error('Supabase is not configured. Check VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY.')
  }
}

function assertNyuEmail(email: string): void {
  if (!email.toLowerCase().endsWith('@nyu.edu')) {
    throw new Error('Only @nyu.edu email addresses are allowed.')
  }
}

function assertPasswordStrength(password: string): void {
  if (password.length < MIN_PASSWORD_LENGTH) {
    throw new Error(`Password must be at least ${MIN_PASSWORD_LENGTH} characters.`)
  }
}

function getRedirectToUrl(): string {
  if (typeof window === 'undefined') {
    return ''
  }

  return `${window.location.origin}`
}

export function isRecoveryFlowFromUrl(): boolean {
  if (typeof window === 'undefined') {
    return false
  }

  const hashParams = new URLSearchParams(window.location.hash.replace(/^#/, ''))
  const queryParams = new URLSearchParams(window.location.search)
  const hashType = hashParams.get('type')
  const queryType = queryParams.get('type')

  return hashType === 'recovery' || queryType === 'recovery'
}

export async function isAuthenticated(): Promise<boolean> {
  if (!supabase) {
    return false
  }

  const { data, error } = await supabase.auth.getSession()
  if (error) {
    return false
  }

  return Boolean(data.session)
}

export async function getAuthToken(): Promise<string | null> {
  if (!supabase) {
    return null
  }

  const { data, error } = await supabase.auth.getSession()
  if (error || !data.session) {
    return null
  }

  return data.session.access_token
}

export async function signUp(email: string, password: string): Promise<string> {
  assertSupabaseConfigured()
  assertNyuEmail(email)
  assertPasswordStrength(password)

  const { error } = await supabase.auth.signUp({
    email,
    password,
    options: {
      emailRedirectTo: getRedirectToUrl(),
    },
  })

  if (error) {
    throw error
  }

  return 'Account created! Check your email to confirm your address, then sign in.'
}

export async function signIn(email: string, password: string): Promise<void> {
  assertSupabaseConfigured()
  assertNyuEmail(email)

  const { error } = await supabase.auth.signInWithPassword({ email, password })

  if (error) {
    throw error
  }
}

export async function sendPasswordReset(email: string): Promise<string> {
  assertSupabaseConfigured()
  assertNyuEmail(email)

  const { error } = await supabase.auth.resetPasswordForEmail(email, {
    redirectTo: getRedirectToUrl(),
  })

  if (error) {
    throw error
  }

  return 'If an account exists for this email, a password reset link has been sent.'
}

export async function updatePassword(newPassword: string): Promise<string> {
  assertSupabaseConfigured()
  assertPasswordStrength(newPassword)

  const { error } = await supabase.auth.updateUser({ password: newPassword })

  if (error) {
    throw error
  }

  return 'Password updated successfully. You can now sign in.'
}

export async function logout(): Promise<void> {
  if (!supabase) {
    return
  }

  const { error } = await supabase.auth.signOut()
  if (error) {
    throw error
  }
}
