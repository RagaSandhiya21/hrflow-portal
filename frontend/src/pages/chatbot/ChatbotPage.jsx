import { useState, useEffect, useRef } from 'react'
import { format } from 'date-fns'
import {
  Send, AlertTriangle, CheckCircle, FileText, ArrowUp, RefreshCw, Upload, MessageSquareDiff,
} from 'lucide-react'
import { chatbotApi } from '../../api/services'
import { useAuth } from '../../context/AuthContext'
import { EmptyState, StatusBadge, Modal, Alert, FormField } from '../../components/ui'

export default function ChatbotPage() {
  const { isHRAdmin, user } = useAuth()
  const isSharedAdmin = !!user?.is_shared_admin
  const [tab, setTab] = useState(isSharedAdmin ? 'escalations' : 'chat')
  const [messages, setMessages] = useState([])
  const [sessionId, setSessionId] = useState(null)
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [policyDocs, setPolicyDocs] = useState([])
  const [escalations, setEscalations] = useState([])
  const [myEscalations, setMyEscalations] = useState([])
  const [uploadOpen, setUploadOpen] = useState(false)
  const [respondTarget, setRespondTarget] = useState(null)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  async function loadData() {
    const r = await chatbotApi.policyDocs()
    setPolicyDocs(r.data)
    const me = await chatbotApi.myEscalations()
    setMyEscalations(me.data)
    if (isHRAdmin()) {
      const q = await chatbotApi.escalationQueue()
      setEscalations(q.data)
    }
  }

  useEffect(() => { loadData() }, [])
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  async function ask(queryText) {
    if (!queryText.trim()) return
    setMessages(m => [...m, { role: 'user', text: queryText, ts: new Date() }])
    setQuery(''); setLoading(true)
    try {
      const res = await chatbotApi.query({ session_id: sessionId, query_text: queryText })
      const d = res.data
      if (!sessionId) setSessionId(d.session_id)
      setMessages(m => [...m, {
        role: 'bot', text: d.answer, confidence: d.confidence_score,
        grounded: d.is_grounded, sources: d.source_documents,
        category: d.query_category, queryId: d.query_id, ts: new Date(),
      }])
    } catch {
      setMessages(m => [...m, { role: 'error', text: 'Something went wrong. Please try again.', ts: new Date() }])
    } finally { setLoading(false); inputRef.current?.focus() }
  }

  async function escalate(queryId) {
    try {
      await chatbotApi.escalate({ query_id: queryId, reason: 'low_confidence' })
      setSuccess('Escalated to HR — check "My Escalations" tab for their response.')
      setMessages(m => m.map(msg => msg.queryId === queryId ? { ...msg, escalated: true } : msg))
      loadData()
    } catch (e) { setError(e.response?.data?.detail || 'Escalation failed') }
  }

  async function handleRespond(escalationId, responseText) {
    try {
      const form = new FormData()
      form.append('response_text', responseText)
      await chatbotApi.respondToEscalation(escalationId, form)
      setRespondTarget(null)
      setSuccess('Response sent — the employee can now see your answer.')
      loadData()
    } catch (e) { setError(e.response?.data?.detail || 'Failed to send response') }
  }

  const myAnsweredEscalations = myEscalations.filter(e => e.status === 'resolved' && e.resolution_notes)
  const myOpenEscalations = myEscalations.filter(e => e.status !== 'resolved')

  const tabs = [
    // A shared HR Admin account doesn't personally ask policy questions or
    // have its own escalation history (see employees.is_shared_admin) — it
    // only manages the escalation queue and policy documents.
    ...(!isSharedAdmin ? [
      { key: 'chat', label: 'Policy AI' },
      { key: 'my_escalations', label: `My Escalations (${myEscalations.length})` },
    ] : []),
    ...(isHRAdmin() ? [
      { key: 'escalations', label: `HR Queue (${escalations.length})` },
      { key: 'docs', label: 'Policy Documents' },
    ] : []),
  ]

  return (
    <div>
      <div className="mb-6">
        <h1 className="page-title mb-1">Policy AI Chatbot</h1>
        <p className="text-sm text-gray-500">
          Ask about HR policies. Low-confidence answers can be escalated to HR for a direct response.
        </p>
      </div>

      <Alert type="error" message={error} onDismiss={() => setError('')} />
      <Alert type="success" message={success} onDismiss={() => setSuccess('')} />

      <div className="flex gap-1 bg-gray-100 p-1 rounded-xl mb-4 flex-wrap">
        {tabs.map(t => (
          <button key={t.key}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors
              ${tab === t.key ? 'bg-white shadow text-gray-900' : 'text-gray-500 hover:text-gray-700'}`}
            onClick={() => setTab(t.key)}>{t.label}</button>
        ))}
      </div>

      {/* ── CHAT TAB ── */}
      {tab === 'chat' && (
        <div className="flex gap-5 items-start">
          <div className="flex-1 card p-0 overflow-hidden flex flex-col" style={{ height: '72vh' }}>
            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              {messages.length === 0 && (
                <div className="flex flex-col items-center justify-center h-full text-center text-gray-400 gap-3">
                  <div className="w-16 h-16 rounded-2xl bg-brand-50 flex items-center justify-center">
                    <FileText className="w-8 h-8 text-brand-400" />
                  </div>
                  <div>
                    <p className="font-medium text-gray-600">Ask me anything about HR policies</p>
                    <p className="text-sm mt-1">I'll search the indexed documents and show my confidence level.</p>
                  </div>
                  <div className="grid grid-cols-2 gap-2 mt-2 w-full max-w-sm">
                    {[
                      'How many days of casual leave do I get?',
                      'What is the PF deduction rate?',
                      'Can I carry over privilege leave?',
                      'What are the working hours?',
                    ].map(q => (
                      <button key={q}
                        className="text-xs text-left p-2.5 rounded-xl bg-gray-50 hover:bg-brand-50
                                   hover:text-brand-700 border border-gray-100 hover:border-brand-200
                                   transition-all text-gray-600"
                        onClick={() => ask(q)}>{q}</button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  {msg.role === 'user' && (
                    <div className="max-w-md bg-brand-600 text-white px-4 py-3 rounded-2xl rounded-br-md text-sm">
                      {msg.text}
                    </div>
                  )}
                  {msg.role === 'bot' && (
                    <div className="max-w-2xl space-y-2">
                      <div className="bg-white border border-gray-100 shadow-sm px-4 py-3 rounded-2xl rounded-bl-md text-sm text-gray-800 whitespace-pre-wrap">
                        {msg.text}
                      </div>
                      <div className="flex items-center gap-2 flex-wrap px-1">
                        {msg.grounded
                          ? <span className="flex items-center gap-1 text-xs text-green-600 font-medium">
                              <CheckCircle className="w-3.5 h-3.5" /> Grounded · {Math.round(msg.confidence * 100)}% confidence
                            </span>
                          : <span className="flex items-center gap-1 text-xs text-yellow-600 font-medium">
                              <AlertTriangle className="w-3.5 h-3.5" /> Low confidence ({Math.round(msg.confidence * 100)}%)
                            </span>
                        }
                        {msg.sources?.length > 0 && (
                          <span className="text-xs text-gray-400">· {msg.sources.join(', ')}</span>
                        )}
                        {msg.category && (
                          <span className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded-md">
                            {msg.category.replace(/_/g, ' ')}
                          </span>
                        )}
                      </div>
                      {!msg.grounded && !msg.escalated && (
                        <div className="flex gap-2 px-1">
                          <button className="flex items-center gap-1 text-xs text-gray-500 hover:text-brand-600"
                            onClick={() => {
                              const prev = messages.slice(0, i).reverse().find(m => m.role === 'user')
                              if (prev) ask(prev.text)
                            }}>
                            <RefreshCw className="w-3.5 h-3.5" /> Try again
                          </button>
                          <button className="flex items-center gap-1 text-xs text-yellow-600 hover:text-yellow-700"
                            onClick={() => escalate(msg.queryId)}>
                            <ArrowUp className="w-3.5 h-3.5" /> Escalate to HR
                          </button>
                        </div>
                      )}
                      {msg.escalated && (
                        <span className="text-xs text-yellow-600 px-1 flex items-center gap-1">
                          <CheckCircle className="w-3.5 h-3.5" /> Escalated — check "My Escalations" for HR's response
                        </span>
                      )}
                    </div>
                  )}
                  {msg.role === 'error' && (
                    <div className="max-w-md bg-red-50 border border-red-100 text-red-700 px-4 py-3 rounded-2xl text-sm">
                      {msg.text}
                    </div>
                  )}
                </div>
              ))}

              {loading && (
                <div className="flex justify-start">
                  <div className="bg-white border border-gray-100 shadow-sm px-4 py-3 rounded-2xl rounded-bl-md">
                    <div className="flex gap-1">
                      {[0, 1, 2].map(i => (
                        <div key={i} className="w-2 h-2 bg-brand-300 rounded-full animate-bounce"
                          style={{ animationDelay: `${i * 150}ms` }} />
                      ))}
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <div className="border-t border-gray-100 p-4 bg-gray-50">
              <div className="flex gap-2">
                <input ref={inputRef} className="input flex-1"
                  placeholder="Ask about leave, payroll, code of conduct…"
                  value={query} onChange={e => setQuery(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && !e.shiftKey && !loading && ask(query)}
                  disabled={loading} />
                <button className="btn-primary px-3 py-2" onClick={() => ask(query)}
                  disabled={loading || !query.trim()}>
                  <Send className="w-4 h-4" />
                </button>
              </div>
              <p className="text-xs text-gray-400 mt-2">
                Searching {policyDocs.length} indexed policy documents.
                Escalate low-confidence answers to HR for a direct response.
              </p>
            </div>
          </div>

          {/* Sidebar */}
          <div className="w-52 shrink-0 space-y-2">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Indexed Documents</p>
            {policyDocs.map(d => (
              <div key={d.document_id} className="card py-2.5 px-3 text-xs">
                <FileText className="w-3.5 h-3.5 text-brand-500 mb-1" />
                <p className="font-medium text-gray-700 leading-tight">{d.document_name}</p>
                <p className="text-gray-400 mt-0.5">{d.document_type?.replace(/_/g, ' ')}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── MY ESCALATIONS TAB (employee sees HR responses here) ── */}
      {tab === 'my_escalations' && (
        <div className="space-y-4">
          {myEscalations.length === 0
            ? <EmptyState title="No escalations yet"
                description="When you escalate a chatbot question, HR's response will appear here." />
            : <>
                {myOpenEscalations.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Waiting for HR response</p>
                    {myOpenEscalations.map(e => (
                      <div key={e.escalation_id} className="card mb-2">
                        <div className="flex items-center gap-2 mb-2">
                          <StatusBadge status={e.status} />
                          <span className="text-xs text-gray-400">
                            Escalated {e.escalated_at ? format(new Date(e.escalated_at), 'dd MMM yyyy HH:mm') : ''}
                          </span>
                        </div>
                        <div className="bg-gray-50 rounded-xl p-3">
                          <p className="text-xs text-gray-400 mb-1">Your question</p>
                          <p className="text-sm text-gray-800 font-medium">{e.escalated_query}</p>
                        </div>
                        <p className="text-xs text-yellow-600 mt-2">⏳ Waiting for HR to respond…</p>
                      </div>
                    ))}
                  </div>
                )}

                {myAnsweredEscalations.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-gray-500 uppercase mb-2">HR has responded</p>
                    {myAnsweredEscalations.map(e => (
                      <div key={e.escalation_id} className="card mb-2 border-green-100">
                        <div className="flex items-center gap-2 mb-3">
                          <StatusBadge status="approved" />
                          <span className="text-xs text-gray-400">
                            Answered {e.resolved_at ? format(new Date(e.resolved_at), 'dd MMM yyyy HH:mm') : ''}
                          </span>
                        </div>
                        <div className="bg-gray-50 rounded-xl p-3 mb-3">
                          <p className="text-xs text-gray-400 mb-1">Your question</p>
                          <p className="text-sm text-gray-700 font-medium">{e.escalated_query}</p>
                        </div>
                        <div className="bg-green-50 border border-green-100 rounded-xl p-3">
                          <p className="text-xs text-green-600 font-semibold mb-1">
                            ✓ HR Response
                          </p>
                          <p className="text-sm text-gray-800 whitespace-pre-wrap">{e.resolution_notes}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </>
          }
        </div>
      )}

      {/* ── HR QUEUE TAB (HR Admin responds to escalations) ── */}
      {tab === 'escalations' && isHRAdmin() && (
        <div>
          {escalations.length === 0
            ? <EmptyState title="No open escalations"
                description="When employees escalate chatbot questions, they appear here for you to answer." />
            : <div className="space-y-3">
                {escalations.map(e => (
                  <div key={e.escalation_id} className="card">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2 flex-wrap">
                          <StatusBadge status={e.status} />
                          <span className="text-xs font-semibold text-brand-600 bg-brand-50 px-2 py-0.5 rounded-full">
                            {e.employee_name || 'Unknown'}
                          </span>
                          <span className="text-xs text-gray-400">
                            {e.escalated_at ? format(new Date(e.escalated_at), 'dd MMM yyyy HH:mm') : ''}
                          </span>
                        </div>
                        <div className="bg-gray-50 rounded-xl p-3">
                          <p className="text-xs text-gray-400 mb-1 font-medium">Employee's question</p>
                          <p className="text-sm text-gray-800 font-medium">{e.escalated_query}</p>
                        </div>
                        <p className="text-xs text-gray-400 mt-2">
                          Reason: {e.escalation_reason?.replace(/_/g, ' ')}
                        </p>
                      </div>
                      <button className="btn-primary text-xs py-1.5 shrink-0 flex items-center gap-1"
                        onClick={() => setRespondTarget(e)}>
                        <MessageSquareDiff className="w-3.5 h-3.5" /> Send Answer
                      </button>
                    </div>
                  </div>
                ))}
              </div>
          }
        </div>
      )}

      {/* ── POLICY DOCS TAB ── */}
      {tab === 'docs' && isHRAdmin() && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-gray-900">Indexed Policy Documents</h2>
            <button className="btn-primary" onClick={() => setUploadOpen(true)}>
              <Upload className="w-4 h-4" /> Upload Document
            </button>
          </div>
          <div className="grid gap-3">
            {policyDocs.map(d => (
              <div key={d.document_id} className="card flex items-center gap-4">
                <div className="p-3 bg-brand-50 rounded-xl">
                  <FileText className="w-5 h-5 text-brand-600" />
                </div>
                <div className="flex-1">
                  <p className="font-medium text-gray-900">{d.document_name}</p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {d.document_type?.replace(/_/g, ' ')} · Doc #{d.document_id}
                  </p>
                </div>
                <span className={`badge ${d.indexed_in_chromadb ? 'badge-green' : 'badge-yellow'}`}>
                  {d.indexed_in_chromadb ? 'ChromaDB' : 'Keyword search'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Respond Modal */}
      <RespondModal
        open={!!respondTarget}
        escalation={respondTarget}
        onClose={() => setRespondTarget(null)}
        onSubmit={handleRespond}
      />

      {/* Upload Modal */}
      <UploadModal
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onSuccess={() => { setUploadOpen(false); setSuccess('Document uploaded and indexed!'); loadData() }}
      />
    </div>
  )
}

function RespondModal({ open, escalation, onClose, onSubmit }) {
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)
  if (!escalation) return null
  async function send() {
    if (!text.trim()) return
    setLoading(true)
    await onSubmit(escalation.escalation_id, text)
    setText(''); setLoading(false)
  }
  return (
    <Modal open={open} onClose={onClose} title="Send HR Response"
      footer={<>
        <button className="btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn-primary" onClick={send} disabled={loading || !text.trim()}>
          {loading ? 'Sending…' : 'Send Answer'}
        </button>
      </>}>
      <div className="bg-gray-50 rounded-xl p-3 mb-2">
        <p className="text-xs text-gray-400 mb-1 font-medium">
          Question from {escalation.employee_name}
        </p>
        <p className="text-sm text-gray-800 font-medium">{escalation.escalated_query}</p>
      </div>
      <FormField label="Your answer" required>
        <textarea className="input" rows={6} value={text} onChange={e => setText(e.target.value)}
          placeholder="Type your HR response here — the employee will see this immediately in their 'My Escalations' tab…"
          autoFocus />
      </FormField>
    </Modal>
  )
}

function UploadModal({ open, onClose, onSuccess }) {
  const [name, setName] = useState('')
  const [type, setType] = useState('leave_policy')
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  async function upload() {
    if (!name || !file) return setError('Document name and file are required')
    setLoading(true); setError('')
    try {
      const form = new FormData()
      form.append('document_name', name)
      form.append('document_type', type)
      form.append('file', file)
      const token = localStorage.getItem('hrflow_token')
      const res = await fetch('/api/chatbot/policy-docs/upload', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      })
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Upload failed') }
      onSuccess()
    } catch (e) { setError(e.message || 'Upload failed') }
    finally { setLoading(false) }
  }
  return (
    <Modal open={open} onClose={onClose} title="Upload Policy Document"
      footer={<>
        <button className="btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn-primary" onClick={upload} disabled={loading}>
          {loading ? 'Uploading…' : 'Upload & Index'}
        </button>
      </>}>
      <Alert type="info" message="Upload a PDF or plain text (.txt) file. PDFs are extracted via PyMuPDF; the content is then chunked and indexed for chatbot search." />
      <Alert type="error" message={error} onDismiss={() => setError('')} />
      <FormField label="Document Name" required>
        <input className="input" value={name} onChange={e => setName(e.target.value)}
          placeholder="e.g. Leave Policy 2026" />
      </FormField>
      <FormField label="Document Type" required>
        <select className="input" value={type} onChange={e => setType(e.target.value)}>
          {['leave_policy','compensation_policy','code_of_conduct','it_policy','attendance_policy','other'].map(t => (
            <option key={t} value={t}>{t.replace(/_/g,' ')}</option>
          ))}
        </select>
      </FormField>
      <FormField label="File (PDF or .txt)" required>
        <input type="file" accept=".pdf,.txt" className="input py-1.5"
          onChange={e => setFile(e.target.files?.[0] || null)} />
      </FormField>
      {file && <p className="text-xs text-gray-500">Selected: {file.name} ({(file.size/1024).toFixed(1)} KB)</p>}
    </Modal>
  )
}
