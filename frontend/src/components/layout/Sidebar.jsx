import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, Calendar, FileText, User, MessageSquare,
  ClipboardList, Monitor, Clock, LogOut, Shield, Users,
} from 'lucide-react'
import { useAuth } from '../../context/AuthContext'

// `roles`: only these roles ever see the item (existing behaviour).
// `hideForSharedAdmin`: hidden for shared HR/IT Admin accounts (is_shared_admin) —
// these are functional role accounts with no personal HR data, so "Leave",
// "Payslips", "Attendance", "My Profile" make no sense for them.
// `hideForRoles`: hidden for specific roles regardless of shared-admin status.
const NAV = [
  { to: '/',                 icon: LayoutDashboard, label: 'Dashboard',           roles: null },
  { to: '/leave',            icon: Calendar,        label: 'Leave',                roles: null, hideForSharedAdmin: true },
  { to: '/payslips',         icon: FileText,        label: 'Payslips',             roles: null, hideForSharedAdmin: true },
  { to: '/attendance',       icon: Clock,           label: 'Attendance',           roles: null, hideForSharedAdmin: true },
  { to: '/attendance/admin', icon: Shield,          label: 'Attendance Admin',     roles: ['hr_admin','super_admin'] },
  { to: '/employees',        icon: Users,           label: 'Employee Management',  roles: ['hr_admin','super_admin'] },
  { to: '/profile',          icon: User,            label: 'My Profile',           roles: null, hideForRoles: ['it_admin'] },
  { to: '/hr-requests',      icon: ClipboardList,   label: 'HR Requests',          roles: null, hideForRoles: ['it_admin'] },
  { to: '/it-requests',      icon: Monitor,         label: 'IT Requests',          roles: null, hideForRoles: ['hr_admin'] },
  { to: '/chatbot',          icon: MessageSquare,   label: 'Policy AI',            roles: null, hideForRoles: ['it_admin'] },
]

export default function Sidebar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() { logout(); navigate('/login') }

  const visibleNav = NAV.filter(n => {
    if (n.roles && !n.roles.includes(user?.role)) return false
    if (n.hideForSharedAdmin && user?.is_shared_admin) return false
    if (n.hideForRoles && n.hideForRoles.includes(user?.role)) return false
    return true
  }).map(n => {
    // HR Admin (shared account) doesn't chat with the bot or have personal
    // escalations — it only manages the queue/policy docs — so relabel the
    // nav entry to reflect what's actually behind it for that role.
    if (n.to === '/chatbot' && user?.is_shared_admin) return { ...n, label: 'Escalations & Policy Docs' }
    // Likewise, HR Admin's shared account has no personal profile — /profile
    // for them is only the change-request approval queue.
    if (n.to === '/profile' && user?.is_shared_admin) return { ...n, label: 'Profile Approvals' }
    return n
  })

  return (
    <aside className="w-64 shrink-0 bg-brand-600 text-white flex flex-col h-screen sticky top-0">
      {/* Logo */}
      <div className="px-6 py-5 border-b border-brand-500">
        <span className="text-xl font-bold tracking-tight">
          HR<span className="text-brand-200">Flow</span>
        </span>
        <p className="text-xs text-brand-200 mt-0.5">Employee Self-Service</p>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-0.5">
        {visibleNav.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors
               ${isActive
                 ? 'bg-white/15 text-white'
                 : 'text-brand-100 hover:bg-white/10 hover:text-white'}`
            }
          >
            <Icon className="w-4 h-4 shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* User footer */}
      <div className="px-4 py-4 border-t border-brand-500">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-8 h-8 rounded-full bg-brand-400 flex items-center justify-center text-sm font-semibold">
            {user?.first_name?.[0]}{user?.last_name?.[0]}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">{user?.full_name}</p>
            <p className="text-xs text-brand-200 capitalize">{user?.role?.replace(/_/g, ' ')}</p>
          </div>
        </div>
        <button onClick={handleLogout}
          className="flex items-center gap-2 w-full px-3 py-2 rounded-xl text-sm
                     text-brand-100 hover:bg-white/10 hover:text-white transition-colors">
          <LogOut className="w-4 h-4" />
          Sign out
        </button>
      </div>
    </aside>
  )
}
