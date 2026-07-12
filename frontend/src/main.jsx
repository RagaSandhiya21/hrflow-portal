import React from 'react'
import ReactDOM from 'react-dom/client'
import { PublicClientApplication } from '@azure/msal-browser'
import { MsalProvider } from '@azure/msal-react'
import App from './App'
import './index.css'
import { msalConfig, USE_MOCK_SSO } from './auth/msalConfig'

// MSAL only needs to be instantiated for real Entra ID SSO. In mock-SSO
// mode (the default until you've registered an Azure app — see
// src/auth/msalConfig.js) we skip it entirely so the app runs without any
// Azure configuration at all.
const msalInstance = USE_MOCK_SSO ? null : new PublicClientApplication(msalConfig)

function Root() {
  const app = <App />
  return USE_MOCK_SSO ? app : <MsalProvider instance={msalInstance}>{app}</MsalProvider>
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
)
