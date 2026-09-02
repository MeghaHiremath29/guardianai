import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { fetchCurrentUser, login as loginRequest, tokenStorage, type UserOut } from '../services/api'

interface AuthContextValue {
  user: UserOut | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const bootstrap = async () => {
      const token = tokenStorage.getAccess()
      if (!token) {
        setIsLoading(false)
        return
      }
      try {
        const currentUser = await fetchCurrentUser()
        setUser(currentUser)
      } catch {
        tokenStorage.clear()
      } finally {
        setIsLoading(false)
      }
    }
    bootstrap()
  }, [])

  const login = async (email: string, password: string) => {
    const tokens = await loginRequest(email, password)
    tokenStorage.set(tokens.access_token, tokens.refresh_token)
    const currentUser = await fetchCurrentUser()
    setUser(currentUser)
  }

  const logout = () => {
    tokenStorage.clear()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, isLoading, isAuthenticated: !!user, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
