import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string | undefined
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined

const isSupabaseConfigured = Boolean(supabaseUrl && supabaseAnonKey)

export const supabase = isSupabaseConfigured
  ? createClient(supabaseUrl as string, supabaseAnonKey as string)
  : null

export function hasSupabaseConfig(): boolean {
  return isSupabaseConfigured
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
  if (!supabase) {
    throw new Error('Supabase is not configured. Check VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY.')
  }

  if (!email.endsWith('@nyu.edu')) {
    throw new Error('Only @nyu.edu email addresses are allowed.')
  }

  const { error } = await supabase.auth.signUp({ email, password })

  if (error) {
    throw error
  }

  return 'Account created! Check your email to confirm your address, then sign in.'
}

export async function signIn(email: string, password: string): Promise<void> {
  if (!supabase) {
    throw new Error('Supabase is not configured. Check VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY.')
  }

  if (!email.endsWith('@nyu.edu')) {
    throw new Error('Only @nyu.edu email addresses are allowed.')
  }

  const { error } = await supabase.auth.signInWithPassword({ email, password })

  if (error) {
    throw error
  }
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
