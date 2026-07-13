import { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react'
import { useMsal } from '@azure/msal-react'
import { authApi } from '../api/services'
import { USE_MOCK_SSO } from '../auth/msalConfig'

const AuthContext = createContext(null)

const WS_BASE = (import.meta.env.VITE_API_URL || '/api').replace(/^http/, 'ws')

export function AuthProvider({ children }) {
  // useMsal() requires an MsalProvider ancestor, which only exists in real
  // SSO mode (see main.jsx) — USE_MOCK_SSO is fixed for the whole app
  // lifetime (never toggles at runtime), so this conditional call is safe
  // despite normally violating the rules of hooks.
  // eslint-disable-next-line react-hooks/rules-of-hooks
  const msal = USE_MOCK_SSO ? null : useMsal()

  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem('hrflow_user')) } catch { return null }
  })
  const [token, setToken] = useState(() => localStorage.getItem('hrflow_token'))
  // Only meaningful when `user.is_shared_admin` is true: WHO is actually
  // signed into the shared HR Admin / IT Admin account right now (see
  // backend/app/routers/auth.py). The account itself is never a person.
  const [actingIdentity, setActingIdentity] = useState(() => {
    try { return JSON.parse(localStorage.getItem('hrflow_acting')) } catch { return null }
  })
  const [liveNotification, setLiveNotification] = useState(null)
  const wsRef = useRef(null)

  const applySession = useCallback((access_token, employee, acting_display_name, acting_email) => {
    localStorage.setItem('hrflow_token', access_token)
    localStorage.setItem('hrflow_user', JSON.stringify(employee))
    const acting = employee.is_shared_admin ? { name: acting_display_name, email: acting_email } : null
    localStorage.setItem('hrflow_acting', JSON.stringify(acting))
    setToken(access_token)
    setUser(employee)
    setActingIdentity(acting)
    return employee
  }, [])

  // Dev-only mock SSO (email picker) — see backend/app/security.py.
  const login = useCallback(async (email) => {
    const res = await authApi.login(email)
    const { access_token, employee, acting_display_name, acting_email } = res.data
    return applySession(access_token, employee, acting_display_name, acting_email)
  }, [applySession])

  // Real Microsoft Entra ID SSO — id_token comes from MSAL.js after a
  // successful Microsoft sign-in (see LoginPage.jsx).
  const ssoLogin = useCallback(async (idToken) => {
    const res = await authApi.ssoLogin(idToken)
    const { access_token, employee, acting_display_name, acting_email } = res.data
    return applySession(access_token, employee, acting_display_name, acting_email)
  }, [applySession])

  const logout = useCallback(() => {
    localStorage.removeItem('hrflow_token')
    localStorage.removeItem('hrflow_user')
    localStorage.removeItem('hrflow_acting')
    setToken(null)
    setUser(null)
    setActingIdentity(null)
    wsRef.current?.close()
    // Clear MSAL's own cached account too — without this, the moment the
    // app lands back on /login, MicrosoftLoginButton's effect sees MSAL
    // still has an account cached and silently signs back in via
    // acquireTokenSilent, making "Sign Out" look like it does nothing at
    // all. `onRedirectNavigate: () => false` tells MSAL to clear its local
    // cache without actually navigating to Microsoft's global sign-out page
    // — this signs out of *this app* only, not the person's whole Microsoft
    // session (which is what "Sign Out" should mean here, and avoids
    // needing a separate registered post-logout redirect URI).
    if (msal?.instance) {
      const account = msal.accounts[0]
      msal.instance.logoutRedirect({
        account,
        onRedirectNavigate: () => false,
      })
    }
  }, [msal])

  // Real-time in-portal notifications (FastAPI WebSocket) — falls back to
  // nothing if the socket can't connect; the polling GET /notifications
  // endpoint still works either way.
  useEffect(() => {
    if (!token) return
    const ws = new WebSocket(`${WS_BASE}/notifications/ws?token=${encodeURIComponent(token)}`)
    ws.onmessage = (evt) => {
      try { setLiveNotification(JSON.parse(evt.data)) } catch { /* ignore malformed frame */ }
    }
    wsRef.current = ws
    return () => ws.close()
  }, [token])

  const isRole = useCallback((...roles) => user && roles.includes(user.role), [user])
  const isManager  = useCallback(() => isRole('manager', 'hr_admin', 'super_admin'), [isRole])
  const isHRAdmin  = useCallback(() => isRole('hr_admin', 'super_admin'), [isRole])
  const isITAdmin  = useCallback(() => isRole('it_admin', 'super_admin'), [isRole])

  return (
    <AuthContext.Provider value={{
      user, token, actingIdentity, liveNotification,
      login, ssoLogin, logout, isRole, isManager, isHRAdmin, isITAdmin,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
