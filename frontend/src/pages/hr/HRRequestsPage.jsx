import { useState, useEffect } from 'react'
import { format, parseISO } from 'date-fns'
import { Plus, Send, ChevronDown, ChevronUp } from 'lucide-react'
import { hrRequestApi } from '../../api/services'
import { useAuth } from '../../context/AuthContext'
import { PageSpinner, StatusBadge, Modal, Alert, FormField, EmptyState, Table } from '../../components/ui'

const STATUS_OPTIONS = ['open', 'in_progress', 'pending_info', 'resolved', 'closed', 'cancelled']
const PRIORITY_COLORS = { high: 'badge-red', normal: 'badge-blue', low: 'badge-gray' }

export default function HRRequestsPage() {
  const { isHRAdmin, user } = useAuth()
  const isSharedAdmin = !!user?.is_shared_admin
  const [tab, setTab] = useState(isSharedAdmin ? 'queue' : 'mine')
  const [cats, setCats] = useState([])
  const [myReqs, setMyReqs] = useState([])
  const [queue, setQueue] = useState([])
  const [loading, setLoading] = useState(true)
  const [raiseOpen, setRaiseOpen] = useState(false)
  const [expanded, setExpanded] = useState(null)
  const [comments, setComments] = useState({})
  const [error, setError] = useState(''); const [success, setSuccess] = useState('')

  async function reload() {
    setLoading(true)
    try {
      const catsRes = await hrRequestApi.categories()
      setCats(catsRes.data)
      // A shared HR Admin account has no personal requests to raise/track —
      // it only manages the queue (see employees.is_shared_admin).
      if (!isSharedAdmin) {
        const m = await hrRequestApi.myRequests()
        setMyReqs(m.data)
      }
      if (isHRAdmin()) { const q = await hrRequestApi.queue(); setQueue(q.data) }
    } finally { setLoading(false) }
  }
  useEffect(() => { reload() }, [])

  async function loadComments(id) {
    const r = await hrRequestApi.comments(id)
    setComments(p => ({ ...p, [id]: r.data }))
  }

  async function toggleExpand(id) {
    if (expanded === id) { setExpanded(null); return }
    setExpanded(id)
    if (!comments[id]) await loadComments(id)
  }

  async function updateStatus(id, status) {
    try {
      await hrRequestApi.updateStatus(id, { status })
      setSuccess('Status updated.'); reload()
    } catch (e) { setError(e.response?.data?.detail || 'Failed') }
  }

  if (loading) return <PageSpinner />
  const tabs = isSharedAdmin
    ? [{ key: 'queue', label: `HR Queue (${queue.length})` }]
    : [{ key: 'mine', label: 'My Requests' }, ...(isHRAdmin() ? [{ key: 'queue', label: `HR Queue (${queue.length})` }] : [])]
  const rows = tab === 'mine' ? myReqs : queue

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="page-title mb-0">HR Requests</h1>
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
        ? <EmptyState title="No requests yet" description="Raise a request for any HR-related query or document." />
        : <div className="space-y-2">
            {rows.map(r => (
              <div key={r.hr_request_id} className="card p-0 overflow-hidden">
                <div className="px-5 py-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="font-semibold text-gray-900">{r.subject}</p>
                        <span className={`badge text-xs ${PRIORITY_COLORS[r.priority] || 'badge-gray'}`}>{r.priority}</span>
                        <StatusBadge status={r.status} />
                      </div>
                      <p className="text-xs text-gray-400 mt-1">
                        {r.category_name} · #{r.hr_request_id}
                        {tab === 'queue' && r.employee_name && ` · ${r.employee_name}`}
                        {r.raised_at && ` · ${format(parseISO(r.raised_at), 'dd MMM yyyy')}`}
                      </p>
                    </div>
                    <div className="flex gap-2 shrink-0">
                      {isHRAdmin() && r.status !== 'resolved' && r.status !== 'closed' && (
                        <select className="input text-xs py-1 w-36"
                          value={r.status}
                          onChange={e => updateStatus(r.hr_request_id, e.target.value)}>
                          {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>)}
                        </select>
                      )}
                      <button className="btn-secondary py-1 text-xs"
                        onClick={() => toggleExpand(r.hr_request_id)}>
                        {expanded === r.hr_request_id ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>
                </div>

                {expanded === r.hr_request_id && (
                  <div className="border-t border-gray-100 bg-gray-50 px-5 py-4">
                    <p className="text-sm text-gray-700 mb-3">{r.description}</p>
                    <CommentThread requestId={r.hr_request_id} comments={comments[r.hr_request_id] || []}
                      onCommented={async () => await loadComments(r.hr_request_id)} isHRAdmin={isHRAdmin()} />
                  </div>
                )}
              </div>
            ))}
          </div>}

      <RaiseModal open={raiseOpen} onClose={() => setRaiseOpen(false)} cats={cats}
        onSuccess={() => { setRaiseOpen(false); setSuccess('Request raised.'); reload() }} />
    </div>
  )
}

function CommentThread({ requestId, comments, onCommented, isHRAdmin }) {
  const [text, setText] = useState('')
  const [internal, setInternal] = useState(false)
  const [loading, setLoading] = useState(false)
  async function send() {
    if (!text.trim()) return
    setLoading(true)
    try {
      await hrRequestApi.addComment(requestId, { comment_text: text.trim(), is_internal: internal })
      setText(''); await onCommented()
    } finally { setLoading(false) }
  }
  return (
    <div>
      <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Comments ({comments.length})</p>
      <div className="space-y-2 mb-3 max-h-48 overflow-y-auto">
        {comments.map(c => (
          <div key={c.comment_id} className={`rounded-lg px-3 py-2 text-sm ${c.is_internal ? 'bg-yellow-50 border border-yellow-100' : 'bg-white border border-gray-100'}`}>
            <div className="flex justify-between text-xs text-gray-400 mb-0.5">
              <span className="font-medium text-gray-700">{c.commenter_name}</span>
              <span className="flex gap-1">
                {c.is_internal && <span className="badge badge-yellow">internal</span>}
                {c.created_at && format(parseISO(c.created_at), 'dd MMM HH:mm')}
              </span>
            </div>
            <p className="text-gray-700">{c.comment_text}</p>
          </div>
        ))}
        {comments.length === 0 && <p className="text-xs text-gray-400">No comments yet.</p>}
      </div>
      <div className="flex gap-2">
        <input className="input flex-1 text-sm py-1.5" value={text} onChange={e => setText(e.target.value)}
          placeholder="Add a comment…" onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()} />
        {isHRAdmin && (
          <label className="flex items-center gap-1 text-xs text-gray-500 whitespace-nowrap cursor-pointer">
            <input type="checkbox" checked={internal} onChange={e => setInternal(e.target.checked)} />
            Internal
          </label>
        )}
        <button className="btn-primary py-1.5 text-xs" onClick={send} disabled={loading}>
          <Send className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  )
}

function RaiseModal({ open, onClose, cats, onSuccess }) {
  const [form, setForm] = useState({ category_id: '', subject: '', description: '', priority: 'normal' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const f = k => v => setForm(p => ({ ...p, [k]: v }))
  async function submit() {
    if (!form.category_id || !form.subject || !form.description) return setError('Fill in all required fields')
    setLoading(true); setError('')
    try { await hrRequestApi.raise({ ...form, category_id: Number(form.category_id) }); onSuccess() }
    catch (e) { setError(e.response?.data?.detail || 'Failed') }
    finally { setLoading(false) }
  }
  return (
    <Modal open={open} onClose={onClose} title="Raise HR Request"
      footer={<><button className="btn-secondary" onClick={onClose}>Cancel</button><button className="btn-primary" onClick={submit} disabled={loading}>Submit</button></>}>
      <Alert type="error" message={error} onDismiss={() => setError('')} />
      <FormField label="Category" required>
        <select className="input" value={form.category_id} onChange={e => f('category_id')(e.target.value)}>
          <option value="">Select category…</option>
          {cats.map(c => <option key={c.category_id} value={c.category_id}>{c.category_name}</option>)}
        </select>
      </FormField>
      <FormField label="Subject" required>
        <input className="input" value={form.subject} onChange={e => f('subject')(e.target.value)} placeholder="Brief subject…" />
      </FormField>
      <FormField label="Priority" required>
        <select className="input" value={form.priority} onChange={e => f('priority')(e.target.value)}>
          <option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option>
        </select>
      </FormField>
      <FormField label="Description" required>
        <textarea className="input" rows={4} value={form.description} onChange={e => f('description')(e.target.value)} placeholder="Describe your request…" />
      </FormField>
    </Modal>
  )
}
