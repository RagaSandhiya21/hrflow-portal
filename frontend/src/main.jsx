import React from 'react'
import ReactDOM from 'react-dom/client'
import { PublicClientApplication } from '@azure/msal-browser'
import { MsalProvider } from '@azure/msal-react'
import App from './App'
import './index.css'
import { msalConfig, USE_MOCK_SSO } from './auth/msalConfig'

function Root({ msalInstance }) {
  const app = <App />
  return USE_MOCK_SSO ? app : <MsalProvider instance={msalInstance}>{app}</MsalProvider>
}

async function bootstrap() {
  let msalInstance = null

  // MSAL only needs to be instantiated for real Entra ID SSO. In mock-SSO
  // mode (the default until you've registered an Azure app — see
  // src/auth/msalConfig.js) we skip it entirely so the app runs without any
  // Azure configuration at all.
  if (!USE_MOCK_SSO) {
    msalInstance = new PublicClientApplication(msalConfig)
    // MSAL Browser v3 introduced a required async initialize() step that
    // must complete before the instance is safe to use for anything else —
    // including reading a pending redirect response. Constructing the
    // instance with `new PublicClientApplication(...)` alone (what this
    // file used to do) does NOT perform that step; skipping it — or not
    // awaiting it before the app renders and MsalProvider/our own routing
    // start touching the URL — is a documented cause of MSAL silently
    // failing to read the #code=... hash correctly after a redirect, which
    // surfaces as "hash_empty_error" even though the hash is genuinely
    // present in the address bar at that point.
    await msalInstance.initialize()
  }

  ReactDOM.createRoot(document.getElementById('root')).render(
    <React.StrictMode>
      <Root msalInstance={msalInstance} />
    </React.StrictMode>
  )
}

bootstrap()
