import { useState, useEffect } from 'react'
import { format, parseISO } from 'date-fns'
import { Plus } from 'lucide-react'
import { itRequestApi } from '../../api/services'
import { useAuth } from '../../context/AuthContext'
import { PageSpinner, StatusBadge, Modal, Alert, FormField, EmptyState, Table } from '../../components/ui'

const REQUEST_TYPES = [
  'hardware_issue','software_install','access_request','vpn_issue',
  'password_reset','email_setup','device_replacement','other',
]
const PRIORITY_COLORS = { high: 'badge-red', normal: 'badge-blue', low: 'badge-gray' }

export default function ITRequestsPage() {
  const { isITAdmin, isHRAdmin, user } = useAuth()
  const isSharedAdmin = !!user?.is_shared_admin
  const [tab, setTab] = useState(isSharedAdmin ? 'queue' : 'mine')
  const [myReqs, setMyReqs] = useState([])
  const [queue, setQueue] = useState([])
  const [loading, setLoading] = useState(true)
  const [raiseOpen, setRaiseOpen] = useState(false)
  const [statusTarget, setStatusTarget] = useState(null)
  const [error, setError] = useState(''); const [success, setSuccess] = useState('')

  const canSeeQueue = isITAdmin() || isHRAdmin()

  async function reload() {
    setLoading(true)
    try {
      // A shared IT Admin account has no personal requests to raise/track —
      // it only manages the queue (see employees.is_shared_admin).
      if (!isSharedAdmin) {
        const r = await itRequestApi.myRequests()
        setMyReqs(r.data)
      }
      if (canSeeQueue) { const q = await itRequestApi.queue(); setQueue(q.data) }
    } finally { setLoading(false) }
  }
  useEffect(() => { reload() }, [])

  async function updateStatus(id, status, notes = '') {
    try {
      await itRequestApi.updateStatus(id, { status, notes })
      setStatusTarget(null); setSuccess('Status updated.'); reload()
    } catch (e) { setError(e.response?.data?.detail || 'Failed') }
  }

  if (loading) return <PageSpinner />

  const tabs = isSharedAdmin
    ? [{ key: 'queue', label: `IT Queue (${queue.length})` }]
    : [
        { key: 'mine', label: 'My Requests' },
        ...(canSeeQueue ? [{ key: 'queue', label: `IT Queue (${queue.length})` }] : []),
      ]
  const rows = tab === 'mine' ? myReqs : queue

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="page-title mb-0">IT Requests</h1>
        {!isSharedAdmin && (
          <button className="btn-primary" onClick={() => setRaiseOpen(true)}>
            <Plus className="w-4 h-4" /> New Request
          </button>
        )}
      </div>

      <Alert type="error" message={error} onDismiss={() => setError('')} />
      <Alert type="success" message={success} onDismiss={() => setSuccess('')} />

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

      {rows.length === 0
        ? <EmptyState title="No IT requests" description="Raise a ticket for hardware issues, software installs, access requests, and more." />
        : (
          <Table headers={['Subject', 'Type', 'Priority', 'Status', 'Raised', ...(tab === 'queue' ? ['Employee', 'Actions'] : [])]}>
            {rows.map(r => (
              <tr key={r.it_request_id} className="hover:bg-gray-50">
                <td className="table-td">
                  <p className="font-medium text-gray-900">{r.subject}</p>
                  <p className="text-xs text-gray-400 mt-0.5 max-w-xs truncate">{r.description}</p>
                </td>
                <td className="table-td">
                  <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-md">
                    {r.request_type.replace(/_/g, ' ')}
                  </span>
                </td>
                <td className="table-td">
                  <span className={`badge text-xs ${PRIORITY_COLORS[r.priority] || 'badge-gray'}`}>{r.priority}</span>
                </td>
                <td className="table-td"><StatusBadge status={r.status} /></td>
                <td className="table-td text-gray-400 text-xs">
                  {r.raised_at ? format(parseISO(r.raised_at), 'dd MMM yyyy') : '—'}
                </td>
                {tab === 'queue' && <td className="table-td font-medium">{r.employee_name}</td>}
                {tab === 'queue' && isITAdmin() && (
                  <td className="table-td">
                    <button className="btn-secondary py-1 text-xs"
                      onClick={() => setStatusTarget(r)}>Update</button>
                  </td>
                )}
              </tr>
            ))}
          </Table>
        )}

      <RaiseModal open={raiseOpen} onClose={() => setRaiseOpen(false)}
        onSuccess={() => { setRaiseOpen(false); setSuccess('IT request raised.'); reload() }} />

      <StatusModal open={!!statusTarget} req={statusTarget} onClose={() => setStatusTarget(null)}
        onSubmit={updateStatus} />
    </div>
  )
}

function RaiseModal({ open, onClose, onSuccess }) {
  const [form, setForm] = useState({ request_type: '', subject: '', description: '', priority: 'normal' })
  const [loading, setLoading] = useState(false); const [error, setError] = useState('')
  const f = k => v => setForm(p => ({ ...p, [k]: v }))
  async function submit() {
    if (!form.request_type || !form.subject || !form.description) return setError('Fill in all required fields')
    setLoading(true); setError('')
    try { await itRequestApi.raise(form); onSuccess() }
    catch (e) { setError(e.response?.data?.detail || 'Failed') }
    finally { setLoading(false) }
  }
  return (
    <Modal open={open} onClose={onClose} title="Raise IT Request"
      footer={<><button className="btn-secondary" onClick={onClose}>Cancel</button>
               <button className="btn-primary" onClick={submit} disabled={loading}>Submit</button></>}>
      <Alert type="error" message={error} onDismiss={() => setError('')} />
      <FormField label="Request Type" required>
        <select className="input" value={form.request_type} onChange={e => f('request_type')(e.target.value)}>
          <option value="">Select type…</option>
          {REQUEST_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g,' ')}</option>)}
        </select>
      </FormField>
      <FormField label="Subject" required>
        <input className="input" value={form.subject} onChange={e => f('subject')(e.target.value)} placeholder="Brief description…" />
      </FormField>
      <FormField label="Priority">
        <select className="input" value={form.priority} onChange={e => f('priority')(e.target.value)}>
          <option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option>
        </select>
      </FormField>
      <FormField label="Details" required>
        <textarea className="input" rows={4} value={form.description} onChange={e => f('description')(e.target.value)}
          placeholder="Describe the issue or request in detail…" />
      </FormField>
    </Modal>
  )
}

function StatusModal({ open, req, onClose, onSubmit }) {
  const [status, setStatus] = useState('')
  const [notes, setNotes] = useState('')
  if (!req) return null
  const options = ['open','in_progress','on_hold','resolved','closed']
  return (
    <Modal open={open} onClose={onClose} title={`Update #${req.it_request_id} — ${req.subject}`}
      footer={<><button className="btn-secondary" onClick={onClose}>Cancel</button>
               <button className="btn-primary" onClick={() => onSubmit(req.it_request_id, status, notes)}
                 disabled={!status}>Update</button></>}>
      <p className="text-xs text-gray-500 mb-3">Raised by <strong>{req.employee_name}</strong> · Current: <StatusBadge status={req.status} /></p>
      <FormField label="New Status" required>
        <select className="input" value={status} onChange={e => setStatus(e.target.value)}>
          <option value="">Select status…</option>
          {options.map(s => <option key={s} value={s}>{s.replace(/_/g,' ')}</option>)}
        </select>
      </FormField>
      <FormField label="Notes">
        <textarea className="input" rows={3} value={notes} onChange={e => setNotes(e.target.value)} placeholder="Optional update notes…" />
      </FormField>
    </Modal>
  )
}
