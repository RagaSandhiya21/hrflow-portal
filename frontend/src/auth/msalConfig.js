/**
 * Microsoft Entra ID SSO configuration (MSAL.js).
 *
 * Fill in VITE_ENTRA_TENANT_ID and VITE_ENTRA_CLIENT_ID in frontend/.env
 * once you've registered this app in your Azure tenant (Entra ID -> App
 * registrations -> New registration; add a SPA redirect URI pointing at
 * this app's URL, e.g. http://localhost:5173).
 *
 * Until those are set, VITE_USE_MOCK_SSO=true (the default) keeps the
 * dev-only email picker on the Login screen working instead — see
 * LoginPage.jsx and backend/app/security.py.
 */
export const USE_MOCK_SSO = (import.meta.env.VITE_USE_MOCK_SSO ?? 'true') === 'true'

const tenantId = import.meta.env.VITE_ENTRA_TENANT_ID || ''
const clientId = import.meta.env.VITE_ENTRA_CLIENT_ID || ''

export const msalConfig = {
  auth: {
    clientId,
    authority: `https://login.microsoftonline.com/${tenantId}`,
    redirectUri: window.location.origin,
  },
  cache: {
    cacheLocation: 'sessionStorage',
    storeAuthStateInCookie: false,
  },
}

// `openid profile email` gets us the id_token claims the backend needs
// (oid/email/name). Add your Entra ID group-claim configuration in the app
// registration's "Token configuration" so `groups` shows up too — see
// backend/app/security.py::extract_identity for why that matters (it's how
// the shared HR Admin / IT Admin accounts are resolved).
//
// prompt: 'select_account' stops MSAL from silently reusing whichever
// Microsoft account is already cached in the browser session — without it,
// clicking "Sign in with Microsoft" a second time (e.g. testing as a
// different employee) just re-signs-in as whoever was last active instead
// of letting the person choose.
export const loginRequest = {
  scopes: ['openid', 'profile', 'email'],
  prompt: 'select_account',
}
