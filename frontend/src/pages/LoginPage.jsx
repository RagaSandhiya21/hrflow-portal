import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMsal } from '@azure/msal-react'
import { useAuth } from '../context/AuthContext'
import { Alert, Spinner } from '../components/ui'
import { USE_MOCK_SSO, loginRequest } from '../auth/msalConfig'

// Individual people only — HR Admin / IT Admin are shared functional
// accounts (see backend: employees.is_shared_admin), never a named person,
// so they don't belong in a "pick a person" list. In production they're
// reached by being a member of the mapped Entra ID security group; in this
// dev-mock picker they're offered as generic role buttons instead.
const DEMO_PEOPLE = [
  { email: 'kavya.manager@psiog.com',  role: 'Manager',  name: 'Kavya Subramaniam' },
  { email: 'rohan.employee@psiog.com', role: 'Employee', name: 'Rohan Iyer' },
  { email: 'sneha.employee@psiog.com', role: 'Employee', name: 'Sneha Nair' },
]
const DEMO_SHARED_ACCOUNTS = [
  { email: 'hr.admin@psiog.com', role: 'HR Admin', name: 'HR Admin (shared)' },
  { email: 'it.admin@psiog.com', role: 'IT Admin', name: 'IT Admin (shared)' },
]

function MockLoginForm() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleLogin(e) {
    e.preventDefault()
    if (!email.trim()) return
    setLoading(true)
    setError('')
    try {
      await login(email.trim())
      navigate('/', { replace: true })
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed — is this email in the employees table?')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <Alert type="error" message={error} onDismiss={() => setError('')} />

      <form onSubmit={handleLogin} className="mt-4 space-y-4">
        <div>
          <label className="label">Work email</label>
          <input
            type="email"
            className="input"
            placeholder="you@psiog.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoFocus
            required
          />
        </div>
        <button type="submit" className="btn-primary w-full justify-center py-2.5" disabled={loading}>
          {loading ? <Spinner size="sm" /> : 'Continue'}
        </button>
      </form>

      <div className="mt-6 pt-5 border-t border-gray-100">
        <p className="text-xs text-gray-400 mb-3 font-medium uppercase tracking-wide">Demo individual accounts</p>
        <div className="space-y-1">
          {DEMO_PEOPLE.map((u) => (
            <button key={u.email}
              onClick={() => { setEmail(u.email); setError('') }}
              className="w-full flex items-center justify-between px-3 py-2 rounded-lg
                         text-left text-sm hover:bg-brand-50 transition-colors group">
              <span>
                <span className="font-medium text-gray-700">{u.name}</span>
                <span className="text-xs text-gray-400 ml-2">{u.email}</span>
              </span>
              <span className="text-xs text-brand-600 font-medium px-2 py-0.5 rounded-full bg-brand-50 group-hover:bg-brand-100">
                {u.role}
              </span>
            </button>
          ))}
        </div>

        <p className="text-xs text-gray-400 mt-4 mb-3 font-medium uppercase tracking-wide">
          Demo shared admin accounts
        </p>
        <div className="space-y-1">
          {DEMO_SHARED_ACCOUNTS.map((u) => (
            <button key={u.email}
              onClick={() => { setEmail(u.email); setError('') }}
              className="w-full flex items-center justify-between px-3 py-2 rounded-lg
                         text-left text-sm hover:bg-amber-50 transition-colors group">
              <span>
                <span className="font-medium text-gray-700">{u.name}</span>
                <span className="text-xs text-gray-400 ml-2">{u.email}</span>
              </span>
              <span className="text-xs text-amber-700 font-medium px-2 py-0.5 rounded-full bg-amber-50 group-hover:bg-amber-100">
                {u.role}
              </span>
            </button>
          ))}
        </div>
        <p className="text-[11px] text-gray-400 mt-3 leading-relaxed">
          In production, HR Admin / IT Admin aren't logins for one person — any real
          staff member added to the matching Entra ID security group signs into the
          same shared account (see <code>ENTRA_HR_ADMIN_GROUP_ID</code> /{' '}
          <code>ENTRA_IT_ADMIN_GROUP_ID</code> in backend/.env.example).
        </p>
      </div>
    </>
  )
}

function MicrosoftLoginButton() {
  // `accounts`/`inProgress` come from MsalProvider, which automatically
  // processes the redirect response (calls handleRedirectPromise()
  // internally) whenever the page reloads after Microsoft sends the user
  // back here — see the effect below.
  const { instance, accounts, inProgress } = useMsal()
  const { ssoLogin } = useAuth()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // loginRedirect (full-page redirect) rather than loginPopup: popups hit a
  // known MSAL.js "hash_empty_error" on some static hosts, because the
  // popup's own page load can clear window.location.hash (via client-side
  // routing) before MSAL gets a chance to read the auth response out of it.
  // Redirect flow avoids that whole class of timing issue — MsalProvider
  // reads the response once, on the full page reload, before our router
  // does anything else.
  useEffect(() => {
    if (inProgress !== 'none' || accounts.length === 0) return
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setError('')
      try {
        const result = await instance.acquireTokenSilent({ ...loginRequest, account: accounts[0] })
        if (cancelled) return
        await ssoLogin(result.idToken)
        navigate('/', { replace: true })
      } catch (err) {
        if (!cancelled) setError(err.response?.data?.detail || err.message || 'Microsoft sign-in failed')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [inProgress, accounts, instance, ssoLogin, navigate])

  function handleMicrosoftLogin() {
    setError('')
    setLoading(true)
    instance.loginRedirect(loginRequest)
    // Execution stops here — the browser navigates away to Microsoft's
    // sign-in page, then back to this same page once signed in, at which
    // point the effect above picks up the result.
  }

  return (
    <>
      <Alert type="error" message={error} onDismiss={() => setError('')} />
      <button
        onClick={handleMicrosoftLogin}
        disabled={loading}
        className="btn-primary w-full justify-center py-2.5 flex items-center gap-2"
      >
        {loading ? <Spinner size="sm" /> : (
          <>
            <svg width="16" height="16" viewBox="0 0 21 21" aria-hidden="true">
              <rect x="1" y="1" width="9" height="9" fill="#f25022" />
              <rect x="11" y="1" width="9" height="9" fill="#7fba00" />
              <rect x="1" y="11" width="9" height="9" fill="#00a4ef" />
              <rect x="11" y="11" width="9" height="9" fill="#ffb900" />
            </svg>
            Sign in with Microsoft
          </>
        )}
      </button>
      <p className="text-[11px] text-gray-400 mt-3 leading-relaxed">
        HR/IT staff who are members of the HR Admin / IT Admin Entra ID group are
        signed into that shared functional account automatically — there's no
        separate login for it.
      </p>
    </>
  )
}

export default function LoginPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-brand-800 to-brand-600 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-white tracking-tight">
            HR<span className="text-brand-200">Flow</span>
          </h1>
          <p className="text-brand-200 mt-2 text-sm">Employee Self-Service Portal</p>
        </div>

        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-1">Sign in</h2>
          <p className="text-sm text-gray-500 mb-6">
            {USE_MOCK_SSO
              ? 'Dev mode: pick a demo account below (set VITE_USE_MOCK_SSO=false once Entra ID is configured).'
              : 'Sign in with your organisation Microsoft account.'}
          </p>
          {USE_MOCK_SSO ? <MockLoginForm /> : <MicrosoftLoginButton />}
        </div>
      </div>
    </div>
  )
}
