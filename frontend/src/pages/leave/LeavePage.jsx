import { useState, useEffect } from 'react'
import { format, parseISO } from 'date-fns'
import { Plus, CheckCircle, XCircle, Undo2 } from 'lucide-react'
import { leaveApi } from '../../api/services'
import { useAuth } from '../../context/AuthContext'
import {
  PageSpinner, StatusBadge, Modal, Alert, EmptyState, FormField, Table, Confirm,
} from '../../components/ui'

export default function LeavePage() {
  const { isManager } = useAuth()
  const [tab, setTab] = useState('mine')
  const [types, setTypes] = useState([])
  const [balances, setBalances] = useState([])
  const [myReqs, setMyReqs] = useState([])
  const [teamReqs, setTeamReqs] = useState([])
  const [loading, setLoading] = useState(true)
  const [applyOpen, setApplyOpen] = useState(false)
  const [decideOpen, setDecideOpen] = useState(null)   // { req, action }
  const [withdrawTarget, setWithdrawTarget] = useState(null)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  async function reload() {
    setLoading(true)
    try {
      const [t, b, m] = await Promise.all([leaveApi.types(), leaveApi.balances(new Date().getFullYear()), leaveApi.myRequests()])
      setTypes(t.data); setBalances(b.data); setMyReqs(m.data)
      if (isManager()) {
        const tr = await leaveApi.teamRequests()
        setTeamReqs(tr.data)
      }
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to load leave data')
    } finally { setLoading(false) }
  }
  useEffect(() => { reload() }, [])

  async function handleDecide(action, comments) {
    try {
      await leaveApi.decide(decideOpen.req.leave_request_id, { decision: action, comments })
      setDecideOpen(null); setSuccess(`Request ${action}.`); reload()
    } catch (e) { setError(e.response?.data?.detail || 'Failed') }
  }

  async function handleWithdraw() {
    try {
      await leaveApi.withdraw(withdrawTarget.leave_request_id)
      setWithdrawTarget(null); setSuccess('Request withdrawn.'); reload()
    } catch (e) { setError(e.response?.data?.detail || 'Failed') }
  }

  if (loading) return <PageSpinner />

  const tabs = [{ key: 'mine', label: 'My Requests' }, ...(isManager() ? [{ key: 'team', label: 'Team Approvals' }] : [])]

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="page-title mb-0">Leave Management</h1>
        <button className="btn-primary" onClick={() => setApplyOpen(true)}>
          <Plus className="w-4 h-4" /> Apply Leave
        </button>
      </div>

      <Alert type="error" message={error} onDismiss={() => setError('')} />
      <Alert type="success" message={success} onDismiss={() => setSuccess('')} />

      {/* Balances */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-6">
        {balances.map((b) => (
          <div key={b.leave_type_id} className="card py-4 text-center">
            <p className="text-3xl font-bold text-brand-600">{b.available_days ?? 0}</p>
            <p className="text-xs font-medium text-gray-600 mt-1">{b.leave_type_name}</p>
            <p className="text-xs text-gray-400">{b.used_days} used</p>
          </div>
        ))}
      </div>

      {/* Tabs */}
      {tabs.length > 1 && (
        <div className="flex gap-1 bg-gray-100 p-1 rounded-xl mb-4 w-fit">
          {tabs.map(t => (
            <button key={t.key}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors
                ${tab === t.key ? 'bg-white shadow text-gray-900' : 'text-gray-500 hover:text-gray-700'}`}
              onClick={() => setTab(t.key)}>{t.label}</button>
          ))}
        </div>
      )}

      {/* Requests table */}
      {tab === 'mine' && (
        <Table headers={['Leave Type', 'Dates', 'Days', 'Status', 'Reason', 'Actions']}
          empty={myReqs.length === 0 && <EmptyState title="No leave requests yet" />}>
          {myReqs.map((r) => (
            <tr key={r.leave_request_id} className="hover:bg-gray-50">
              <td className="table-td font-medium">{r.leave_type_name}</td>
              <td className="table-td">
                {format(parseISO(r.start_date), 'dd MMM')}
                {r.start_date !== r.end_date && ` – ${format(parseISO(r.end_date), 'dd MMM yyyy')}`}
              </td>
              <td className="table-td">{r.number_of_days}d</td>
              <td className="table-td"><StatusBadge status={r.status} /></td>
              <td className="table-td max-w-xs truncate text-gray-400">{r.reason || '—'}</td>
              <td className="table-td">
                {r.status === 'pending' && (
                  <button className="text-xs text-red-600 hover:text-red-700"
                    onClick={() => setWithdrawTarget(r)}>Withdraw</button>
                )}
              </td>
            </tr>
          ))}
        </Table>
      )}

      {tab === 'team' && (
        <Table headers={['Employee', 'Leave Type', 'Dates', 'Days', 'Reason', 'Actions']}
          empty={teamReqs.length === 0 && <EmptyState title="No pending team requests" />}>
          {teamReqs.map((r) => (
            <tr key={r.leave_request_id} className="hover:bg-gray-50">
              <td className="table-td font-medium">{r.employee_name}</td>
              <td className="table-td">{r.leave_type_name}</td>
              <td className="table-td">
                {format(parseISO(r.start_date), 'dd MMM')} – {format(parseISO(r.end_date), 'dd MMM yyyy')}
              </td>
              <td className="table-td">{r.number_of_days}d</td>
              <td className="table-td max-w-xs truncate text-gray-400">{r.reason || '—'}</td>
              <td className="table-td">
                <div className="flex gap-2">
                  <button className="text-xs text-green-600 hover:text-green-700 flex items-center gap-1"
                    onClick={() => setDecideOpen({ req: r, action: 'approved' })}>
                    <CheckCircle className="w-3.5 h-3.5" /> Approve
                  </button>
                  <button className="text-xs text-red-600 hover:text-red-700 flex items-center gap-1"
                    onClick={() => setDecideOpen({ req: r, action: 'rejected' })}>
                    <XCircle className="w-3.5 h-3.5" /> Reject
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </Table>
      )}

      {/* Apply Modal */}
      <ApplyModal
        open={applyOpen}
        onClose={() => setApplyOpen(false)}
        types={types}
        balances={balances}
        onSuccess={() => { setApplyOpen(false); setSuccess('Leave applied!'); reload() }}
      />

      {/* Decision Modal */}
      <DecisionModal
        open={!!decideOpen}
        onClose={() => setDecideOpen(null)}
        action={decideOpen?.action}
        req={decideOpen?.req}
        onSubmit={handleDecide}
      />

      {/* Withdraw confirm */}
      <Confirm
        open={!!withdrawTarget}
        onClose={() => setWithdrawTarget(null)}
        onConfirm={handleWithdraw}
        title="Withdraw Leave Request"
        message="Are you sure you want to withdraw this request? This cannot be undone."
        confirmLabel="Withdraw"
        danger
      />
    </div>
  )
}

function ApplyModal({ open, onClose, types, balances, onSuccess }) {
  const [form, setForm] = useState({ leave_type_id: '', start_date: '', end_date: '', is_half_day: false, reason: '' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const f = (k) => (v) => setForm(p => ({ ...p, [k]: v }))

  const balance = balances.find(b => b.leave_type_id === Number(form.leave_type_id))
  const selectedType = types.find(t => t.leave_type_id === Number(form.leave_type_id))

  async function submit() {
    if (!form.leave_type_id || !form.start_date || !form.end_date) {
      return setError('Fill in all required fields')
    }
    setLoading(true); setError('')
    try {
      await leaveApi.apply({
        leave_type_id: Number(form.leave_type_id),
        start_date: form.start_date,
        end_date: form.end_date,
        is_half_day: form.is_half_day,
        reason: form.reason,
      })
      setForm({ leave_type_id: '', start_date: '', end_date: '', is_half_day: false, reason: '' })
      onSuccess()
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to apply')
    } finally { setLoading(false) }
  }

  return (
    <Modal open={open} onClose={onClose} title="Apply for Leave"
      footer={<>
        <button className="btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn-primary" onClick={submit} disabled={loading}>Submit</button>
      </>}>
      <Alert type="error" message={error} onDismiss={() => setError('')} />

      <FormField label="Leave Type" required>
        <select className="input" value={form.leave_type_id} onChange={e => f('leave_type_id')(e.target.value)}>
          <option value="">Select type…</option>
          {types.map(t => <option key={t.leave_type_id} value={t.leave_type_id}>{t.leave_type_name}</option>)}
        </select>
      </FormField>

      {balance && (
        <p className="text-xs text-brand-600 font-medium">
          Available: {balance.available_days} day(s) — {balance.used_days} used this year
        </p>
      )}

      {selectedType?.half_day_allowed && (
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input type="checkbox" checked={form.is_half_day} onChange={e => f('is_half_day')(e.target.checked)} />
          Half-day
        </label>
      )}

      <div className="grid grid-cols-2 gap-3">
        <FormField label="From" required>
          <input type="date" className="input" value={form.start_date} onChange={e => {
            f('start_date')(e.target.value)
            if (!form.end_date || form.end_date < e.target.value) f('end_date')(e.target.value)
          }} />
        </FormField>
        <FormField label="To" required>
          <input type="date" className="input" value={form.end_date} min={form.start_date}
            onChange={e => f('end_date')(e.target.value)} />
        </FormField>
      </div>

      <FormField label="Reason">
        <textarea className="input" rows={3} value={form.reason} onChange={e => f('reason')(e.target.value)}
          placeholder="Optional reason…" />
      </FormField>
    </Modal>
  )
}

function DecisionModal({ open, onClose, action, req, onSubmit }) {
  const [comments, setComments] = useState('')
  if (!req) return null
  return (
    <Modal open={open} onClose={onClose}
      title={`${action === 'approved' ? 'Approve' : 'Reject'} Leave Request`}
      footer={<>
        <button className="btn-secondary" onClick={onClose}>Cancel</button>
        <button className={action === 'approved' ? 'btn-primary' : 'btn-danger'}
          onClick={() => onSubmit(action, comments)}>
          {action === 'approved' ? 'Approve' : 'Reject'}
        </button>
      </>}>
      <p className="text-sm text-gray-600">
        <strong>{req.employee_name}</strong> — {req.leave_type_name}<br />
        {req.start_date} to {req.end_date} ({req.number_of_days} day{req.number_of_days !== 1 ? 's' : ''})
      </p>
      {req.reason && <p className="text-xs text-gray-400 italic">Reason: {req.reason}</p>}
      <FormField label="Comments">
        <textarea className="input" rows={3} value={comments} onChange={e => setComments(e.target.value)}
          placeholder="Optional comments…" />
      </FormField>
    </Modal>
  )
}
