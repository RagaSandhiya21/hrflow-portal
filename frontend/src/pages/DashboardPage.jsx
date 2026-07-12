import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  Calendar, FileText, Clock, ClipboardList, Monitor,
  MessageSquare, AlertCircle, CheckCircle, User,
} from 'lucide-react'
import { dashboardApi } from '../api/services'
import { PageSpinner } from '../components/ui'
import { useAuth } from '../context/AuthContext'

function StatCard({ icon: Icon, label, value, sub, to, color = 'brand' }) {
  const colors = {
    brand:  'bg-brand-50 text-brand-600',
    green:  'bg-green-50 text-green-600',
    yellow: 'bg-yellow-50 text-yellow-600',
    blue:   'bg-blue-50 text-blue-600',
    red:    'bg-red-50 text-red-600',
    orange: 'bg-orange-50 text-orange-600',
  }
  const card = (
    <div className="card hover:shadow-md transition-shadow flex items-start gap-4 group h-full">
      <div className={`p-3 rounded-xl shrink-0 ${colors[color]}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">{label}</p>
        <p className="text-2xl font-bold text-gray-900 mt-0.5">{value}</p>
        {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  )
  return to ? <Link to={to}>{card}</Link> : card
}

export default function DashboardPage() {
  const { user, isHRAdmin, isManager, isITAdmin } = useAuth()
  const isSharedAdmin = !!user?.is_shared_admin
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    dashboardApi.summary().then(r => setData(r.data)).finally(() => setLoading(false))
  }, [])

  if (loading) return <PageSpinner />

  const att = data?.attendance_summary || {}
  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">
          {greeting}, {user?.first_name} 👋
        </h1>
        <p className="text-gray-500 mt-1 text-sm capitalize">
          {user?.role?.replace(/_/g, ' ')} · Here's your portal overview
        </p>
      </div>

      {/* HR Admin alert — pending change requests */}
      {isHRAdmin() && data?.pending_change_requests > 0 && (
        <Link to="/profile">
          <div className="mb-6 flex items-center gap-3 bg-yellow-50 border border-yellow-200 rounded-2xl px-5 py-4">
            <AlertCircle className="w-5 h-5 text-yellow-600 shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-yellow-800">
                {data.pending_change_requests} employee profile change request{data.pending_change_requests > 1 ? 's' : ''} pending your review
              </p>
              <p className="text-xs text-yellow-600 mt-0.5">
                Bank details, PAN, Aadhaar updates waiting for HR approval
              </p>
            </div>
            <span className="text-xs font-medium text-yellow-700 bg-yellow-100 px-3 py-1.5 rounded-lg whitespace-nowrap">
              Review now →
            </span>
          </div>
        </Link>
      )}

      {/* Pending approvals alert for manager */}
      {isManager() && data?.pending_approvals > 0 && (
        <Link to="/leave">
          <div className="mb-6 flex items-center gap-3 bg-orange-50 border border-orange-200 rounded-2xl px-5 py-4">
            <AlertCircle className="w-5 h-5 text-orange-600 shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-orange-800">
                {data.pending_approvals} leave request{data.pending_approvals > 1 ? 's' : ''} pending your approval
              </p>
            </div>
            <span className="text-xs font-medium text-orange-700 bg-orange-100 px-3 py-1.5 rounded-lg whitespace-nowrap">
              Approve now →
            </span>
          </div>
        </Link>
      )}

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {!isSharedAdmin && (
          <StatCard icon={Calendar} label="Pending Leave" value={data?.pending_leave_requests ?? 0}
            to="/leave" color="yellow" sub="requests waiting" />
        )}
        {!isITAdmin() && (
          <StatCard icon={ClipboardList} label="Open HR Requests" value={data?.open_hr_requests ?? 0}
            to="/hr-requests" color="blue" sub="tickets open" />
        )}
        {!isHRAdmin() && (
          <StatCard icon={Monitor} label="Open IT Requests" value={data?.open_it_requests ?? 0}
            to="/it-requests" color="brand" sub="tickets open" />
        )}
        {!isSharedAdmin && data?.latest_payslip_month && (
          <StatCard icon={FileText} label="Latest Payslip" value={data.latest_payslip_month}
            to="/payslips" color="green" sub="tap to download" />
        )}
      </div>

      {/* Attendance summary for this month — personal data, not shown for shared admin accounts */}
      {!isSharedAdmin && (
      <div className="card mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-gray-900">
            Attendance — {new Date().toLocaleString('default', { month: 'long', year: 'numeric' })}
          </h2>
          <Link to="/attendance" className="text-xs text-brand-600 hover:text-brand-700 font-medium">
            View calendar →
          </Link>
        </div>
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
          {[
            { label: 'Present',  value: att.days_present   ?? 0, color: 'text-green-600',  bg: 'bg-green-50' },
            { label: 'WFH',      value: att.days_wfh        ?? 0, color: 'text-blue-600',   bg: 'bg-blue-50' },
            { label: 'On Leave', value: att.days_on_leave   ?? 0, color: 'text-yellow-600', bg: 'bg-yellow-50' },
            { label: 'Absent',   value: att.days_absent     ?? 0, color: 'text-red-600',    bg: 'bg-red-50' },
            { label: 'Late',     value: att.late_arrivals   ?? 0, color: 'text-orange-600', bg: 'bg-orange-50' },
            { label: 'Hours',    value: `${att.total_hours_worked ?? 0}h`, color: 'text-brand-600', bg: 'bg-brand-50' },
          ].map(s => (
            <div key={s.label} className={`${s.bg} rounded-xl py-3 text-center`}>
              <p className={`text-xl font-bold ${s.color}`}>{s.value}</p>
              <p className="text-xs text-gray-500 mt-0.5">{s.label}</p>
            </div>
          ))}
        </div>
        {(att.days_present === 0 && att.days_absent === 0 && att.days_wfh === 0) && (
          <p className="text-xs text-gray-400 text-center mt-3">
            No attendance records yet for this month. Records are updated daily.
          </p>
        )}
      </div>
      )}

      {/* Leave balances */}
      {data?.leave_balances?.length > 0 && (
        <div className="card mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-gray-900">
              Leave Balances — {new Date().getFullYear()}
            </h2>
            <Link to="/leave" className="text-xs text-brand-600 hover:text-brand-700 font-medium">
              Apply leave →
            </Link>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {data.leave_balances.map((b) => (
              <div key={b.leave_code} className="bg-gray-50 rounded-xl p-4 text-center">
                <p className="text-2xl font-bold text-brand-600">{b.available_days}</p>
                <p className="text-xs text-gray-500 mt-1 font-medium leading-tight">{b.leave_type_name}</p>
                <p className="text-xs text-gray-400">{b.leave_code}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Quick actions */}
      <div className="card">
        <h2 className="text-base font-semibold text-gray-900 mb-4">Quick actions</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { to: '/leave',       icon: Calendar,       label: 'Apply Leave',      hide: isSharedAdmin },
            { to: '/payslips',    icon: FileText,        label: 'View Payslip',     hide: isSharedAdmin },
            { to: '/hr-requests', icon: ClipboardList,   label: 'Raise HR Request', hide: isSharedAdmin || isITAdmin() },
            { to: '/chatbot',     icon: MessageSquare,   label: 'Ask Policy AI',    hide: isITAdmin() },
          ].filter(a => !a.hide).map(({ to, icon: Icon, label }) => (
            <Link key={to} to={to}
              className="flex flex-col items-center gap-2 p-4 rounded-xl border border-gray-100
                         hover:border-brand-200 hover:bg-brand-50 transition-all group text-center">
              <div className="p-2 rounded-lg bg-gray-100 group-hover:bg-brand-100 transition-colors">
                <Icon className="w-5 h-5 text-gray-600 group-hover:text-brand-600" />
              </div>
              <span className="text-xs font-medium text-gray-600 group-hover:text-brand-700">{label}</span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  )
}
