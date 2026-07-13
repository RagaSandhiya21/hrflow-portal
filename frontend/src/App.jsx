import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useMsal } from '@azure/msal-react'
import { AuthProvider, useAuth } from './context/AuthContext'
import { USE_MOCK_SSO } from './auth/msalConfig'
import AppLayout from './components/layout/AppLayout'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import LeavePage from './pages/leave/LeavePage'
import PayslipsPage from './pages/payslips/PayslipsPage'
import ProfilePage from './pages/profile/ProfilePage'
import HRRequestsPage from './pages/hr/HRRequestsPage'
import EmployeeManagementPage from './pages/hr/EmployeeManagementPage'
import AttendancePage from './pages/attendance/AttendancePage'
import AdminAttendancePage from './pages/attendance/AdminAttendancePage'
import ITRequestsPage from './pages/it/ITRequestsPage'
import ChatbotPage from './pages/chatbot/ChatbotPage'

// Waits for MSAL to finish processing any pending redirect response (the
// #code=... hash Microsoft appends to the URL after sign-in) before
// rendering ANY routes — including /login itself.
//
// Without this gate, RequireAuth's <Navigate to="/login" replace /> can
// fire before AuthContext's ssoLogin() has run (since that only starts once
// MsalProvider has already populated `accounts`, which itself takes a
// render cycle or two). That replace-navigation clears window.location.hash
// via history.replaceState() before MSAL ever gets to read it — producing
// MSAL's "hash_empty_error" on the very next login attempt, since the hash
// it needs is already gone by the time it looks. Gating on `inProgress`
// ensures MSAL's own internal handleRedirectPromise() completes first,
// before our router's guards get a chance to touch the URL at all.
function MsalRedirectGate({ children }) {
  const { inProgress } = useMsal()
  if (inProgress !== 'none') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 text-sm text-gray-500">
        Signing you in…
      </div>
    )
  }
  return children
}

function RequireAuth({ children }) {
  const { user } = useAuth()
  return user ? children : <Navigate to="/login" replace />
}

// Blocks shared HR/IT Admin accounts from personal-data pages (Leave,
// Payslips, Attendance, My Profile) — mirrors the backend's
// require_personal_employee guard, so navigating directly to the URL
// redirects instead of showing a raw 403 from the API.
// Blocks shared admin accounts from personal-data pages (Leave, Payslips,
// Attendance) — mirrors the backend's require_personal_employee guard.
// HR Admin is the one exception for /profile specifically: that route also
// hosts the (non-personal) profile-change-request APPROVAL queue, which is
// core HR Admin functionality — see RequireProfileAccess below.
function RequireNotSharedAdmin({ children }) {
  const { user } = useAuth()
  return user?.is_shared_admin ? <Navigate to="/" replace /> : children
}

// /profile specifically: personal self-service for real employees, OR the
// approval queue for HR Admin's shared account. Any other shared account
// (e.g. IT Admin) has no legitimate reason to be here.
function RequireProfileAccess({ children }) {
  const { user } = useAuth()
  if (user?.is_shared_admin && user?.role !== 'hr_admin') return <Navigate to="/" replace />
  return children
}

// Blocks a specific role from a page (e.g. IT Admin from Policy AI,
// HR Admin from IT Requests) — see Sidebar.jsx for the matching nav hiding.
function RequireNotITAdmin({ children }) {
  const { user } = useAuth()
  return user?.role === 'it_admin' ? <Navigate to="/" replace /> : children
}
function RequireNotHRAdmin({ children }) {
  const { user } = useAuth()
  return user?.role === 'hr_admin' ? <Navigate to="/" replace /> : children
}
function RequireHRAdmin({ children }) {
  const { user } = useAuth()
  return user?.role === 'hr_admin' || user?.role === 'super_admin' ? children : <Navigate to="/" replace />
}

export default function App() {
  const routes = (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<RequireAuth><AppLayout /></RequireAuth>}>
            <Route index element={<DashboardPage />} />
            <Route path="leave"            element={<RequireNotSharedAdmin><LeavePage /></RequireNotSharedAdmin>} />
            <Route path="payslips"         element={<RequireNotSharedAdmin><PayslipsPage /></RequireNotSharedAdmin>} />
            <Route path="profile"          element={<RequireProfileAccess><ProfilePage /></RequireProfileAccess>} />
            <Route path="hr-requests"      element={<RequireNotITAdmin><HRRequestsPage /></RequireNotITAdmin>} />
            <Route path="employees"        element={<RequireHRAdmin><EmployeeManagementPage /></RequireHRAdmin>} />
            <Route path="attendance"       element={<RequireNotSharedAdmin><AttendancePage /></RequireNotSharedAdmin>} />
            <Route path="attendance/admin" element={<AdminAttendancePage />} />
            <Route path="it-requests"      element={<RequireNotHRAdmin><ITRequestsPage /></RequireNotHRAdmin>} />
            <Route path="chatbot"          element={<RequireNotITAdmin><ChatbotPage /></RequireNotITAdmin>} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
  // In mock-SSO mode there's no MsalProvider ancestor (see main.jsx), so
  // MsalRedirectGate (which calls useMsal()) must not be used at all here —
  // only real Entra ID mode needs this hash-timing protection.
  return USE_MOCK_SSO ? routes : <MsalRedirectGate>{routes}</MsalRedirectGate>
}
