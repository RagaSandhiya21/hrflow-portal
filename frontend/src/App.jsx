import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
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
  return (
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
}
