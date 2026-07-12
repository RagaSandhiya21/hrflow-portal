import { useState, useEffect } from 'react'
import { format, parseISO } from 'date-fns'
import { Edit2, Plus, Lock, AlertCircle, Trash2 } from 'lucide-react'
import { profileApi } from '../../api/services'
import { useAuth } from '../../context/AuthContext'
import {
  PageSpinner, StatusBadge, Modal, Alert, FormField, EmptyState, Table, Confirm,
} from '../../components/ui'

export default function ProfilePage() {
  const { user, isHRAdmin } = useAuth()
  const [profile, setProfile]       = useState(null)
  const [loading, setLoading]       = useState(true)
  const [tab, setTab]               = useState(isHRAdmin() ? 'pending' : 'myprofile')
  const [contactOpen, setContactOpen]   = useState(false)
  const [addressOpen, setAddressOpen]   = useState(false)
  const [changeReqOpen, setChangeReqOpen] = useState(false)
  const [emergencyModal, setEmergencyModal] = useState(null) // { mode: 'add'|'edit', contact? }
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [changeReqs, setChangeReqs]     = useState([])
  const [pendingReqs, setPendingReqs]   = useState([])
  const [error, setError]   = useState('')
  const [success, setSuccess] = useState('')

  async function reload() {
    setLoading(true)
    try {
      if (user?.is_shared_admin) {
        // Shared HR Admin account: no personal profile to fetch — just the
        // approvals queue. A minimal placeholder keeps `profile` non-null so
        // the page renders without needing every field below to be optional.
        const pr = await profileApi.pendingChangeRequests()
        setPendingReqs(pr.data)
        setProfile({ employee: user, addresses: [], emergency_contacts: [], identity_masked: {} })
      } else {
        const [p, cr] = await Promise.all([profileApi.me(), profileApi.myChangeRequests()])
        setProfile(p.data)
        setChangeReqs(cr.data)
      }
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to load profile')
    } finally { setLoading(false) }
  }
  useEffect(() => { reload() }, [])

  async function decideChange(id, decision) {
    try {
      await profileApi.decideChangeRequest(id, { decision })
      setSuccess(`Request ${decision}.`)
      reload()
    } catch (e) { setError(e.response?.data?.detail || 'Failed') }
  }

  if (loading) return <PageSpinner />
  if (!profile) return (
    <div className="space-y-4">
      <Alert type="error" message={error || 'Failed to load profile'} onDismiss={() => setError('')} />
      <button className="btn-secondary" onClick={reload}>Retry</button>
    </div>
  )

  const emp      = profile.employee
  const identity = profile.identity_masked

  const tabs = [
    ...(isHRAdmin() ? [{ key: 'pending', label: `Pending Approvals (${pendingReqs.length})` }] : []),
    ...(!user?.is_shared_admin ? [
      { key: 'myprofile', label: 'My Profile' },
      { key: 'mychanges', label: `My Change Requests (${changeReqs.length})` },
    ] : []),
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Profile</h1>
      </div>

      <Alert type="error"   message={error}   onDismiss={() => setError('')} />
      <Alert type="success" message={success} onDismiss={() => setSuccess('')} />

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 p-1 rounded-xl w-fit flex-wrap">
        {tabs.map(t => (
          <button key={t.key}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors
              ${tab === t.key ? 'bg-white shadow text-gray-900' : 'text-gray-500 hover:text-gray-700'}`}
            onClick={() => setTab(t.key)}>{t.label}</button>
        ))}
      </div>

      {/* ── HR ADMIN: PENDING CHANGE REQUESTS ── */}
      {tab === 'pending' && isHRAdmin() && (
        <div>
          {pendingReqs.length === 0 ? (
            <div className="card text-center py-12">
              <p className="text-gray-500 font-medium">No pending change requests</p>
              <p className="text-sm text-gray-400 mt-1">
                When employees request changes to bank details, PAN, or Aadhaar, they appear here.
              </p>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-2 bg-yellow-50 border border-yellow-200 rounded-xl px-4 py-3 mb-4">
                <AlertCircle className="w-4 h-4 text-yellow-600 shrink-0" />
                <p className="text-sm text-yellow-800 font-medium">
                  {pendingReqs.length} request{pendingReqs.length > 1 ? 's' : ''} waiting for your approval
                </p>
              </div>
              <div className="space-y-3">
                {pendingReqs.map(cr => (
                  <div key={cr.change_request_id} className="card">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2 flex-wrap">
                          <span className="font-semibold text-gray-900">{cr.employee_name}</span>
                          <StatusBadge status={cr.status} />
                          <span className="text-xs text-gray-400">
                            {cr.requested_at ? format(parseISO(cr.requested_at), 'dd MMM yyyy HH:mm') : ''}
                          </span>
                        </div>
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
                          <div className="bg-gray-50 rounded-lg p-3">
                            <p className="text-xs text-gray-400 mb-1">Field</p>
                            <p className="font-medium text-gray-800 capitalize">
                              {cr.field_name.replace(/_/g, ' ')}
                            </p>
                          </div>
                          <div className="bg-gray-50 rounded-lg p-3">
                            <p className="text-xs text-gray-400 mb-1">Current value</p>
                            <p className="font-mono text-gray-500">{cr.old_value || '—'}</p>
                          </div>
                          <div className="bg-brand-50 rounded-lg p-3">
                            <p className="text-xs text-brand-600 mb-1">Requested new value</p>
                            <p className="font-mono font-semibold text-brand-800">{cr.new_value}</p>
                          </div>
                        </div>
                        {cr.reason && (
                          <p className="text-xs text-gray-400 mt-2 italic">Reason: {cr.reason}</p>
                        )}
                      </div>
                      <div className="flex flex-col gap-2 shrink-0">
                        <button
                          className="px-4 py-2 rounded-lg bg-green-600 text-white text-xs font-medium hover:bg-green-700 transition-colors"
                          onClick={() => decideChange(cr.change_request_id, 'approved')}>
                          Approve
                        </button>
                        <button
                          className="px-4 py-2 rounded-lg bg-red-50 text-red-600 border border-red-200 text-xs font-medium hover:bg-red-100 transition-colors"
                          onClick={() => decideChange(cr.change_request_id, 'rejected')}>
                          Reject
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {/* ── MY PROFILE TAB ── */}
      {tab === 'myprofile' && (
        <div className="space-y-6">
          {/* Personal info */}
          <div className="card">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-4">
                <div className="w-16 h-16 rounded-2xl bg-brand-100 flex items-center justify-center text-2xl font-bold text-brand-700">
                  {emp.first_name?.[0]}{emp.last_name?.[0]}
                </div>
                <div>
                  <h2 className="text-xl font-bold text-gray-900">{emp.full_name}</h2>
                  <p className="text-sm text-gray-500">
                    {emp.employee_code} · <StatusBadge status={emp.employment_status} />
                  </p>
                </div>
              </div>
              <button className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border border-gray-300 bg-white text-gray-700 text-xs font-medium hover:bg-gray-50 transition-colors"
                onClick={() => setContactOpen(true)}>
                <Edit2 className="w-3.5 h-3.5" /> Edit
              </button>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm">
              {[
                ['Email', emp.email],
                ['Phone', emp.phone || '—'],
                ['Role', emp.role?.replace(/_/g, ' ')],
                ['Designation', emp.designation_title || 'Not assigned'],
                ['Department', emp.department_name || 'Not assigned'],
                ['Team', emp.team_name || 'Not assigned'],
                ['Manager', emp.manager_name || 'Not assigned'],
                ['Date of Joining', emp.date_of_joining ? format(parseISO(emp.date_of_joining), 'dd MMM yyyy') : '—'],
              ].map(([k, v]) => (
                <div key={k}>
                  <p className="text-xs text-gray-400">{k}</p>
                  <p className="font-medium text-gray-800 mt-0.5 capitalize">{v}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Addresses */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900">Addresses</h3>
              <button className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-gray-300 bg-white text-gray-700 text-xs font-medium hover:bg-gray-50"
                onClick={() => setAddressOpen(true)}>
                <Plus className="w-3.5 h-3.5" /> Add / Update
              </button>
            </div>
            {profile.addresses.length === 0
              ? <p className="text-sm text-gray-400">No addresses on file.</p>
              : <div className="grid gap-3">
                  {profile.addresses.map((a, i) => (
                    <div key={i} className="bg-gray-50 rounded-xl p-4 text-sm">
                      <p className="text-xs font-semibold text-brand-600 uppercase mb-1">{a.address_type}</p>
                      <p>{a.address_line1}{a.address_line2 ? `, ${a.address_line2}` : ''}</p>
                      <p className="text-gray-500">{a.city}, {a.state} — {a.pincode}</p>
                    </div>
                  ))}
                </div>
            }
          </div>

          {/* Emergency contacts */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900">Emergency Contacts</h3>
              <button className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-gray-300 bg-white text-gray-700 text-xs font-medium hover:bg-gray-50"
                onClick={() => setEmergencyModal({ mode: 'add' })}>
                <Plus className="w-3.5 h-3.5" /> Add Contact
              </button>
            </div>
            {profile.emergency_contacts.length === 0
              ? <p className="text-sm text-gray-400">No emergency contacts on file.</p>
              : <div className="grid gap-3">
                  {profile.emergency_contacts.map((c) => (
                    <div key={c.contact_id} className="flex items-center justify-between bg-gray-50 rounded-xl p-4 text-sm">
                      <div>
                        <p className="font-medium text-gray-900">
                          {c.contact_name}
                          {c.is_primary && <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">Primary</span>}
                        </p>
                        <p className="text-gray-500 text-xs mt-0.5">{c.relationship} · {c.phone}</p>
                      </div>
                      <div className="flex gap-2 shrink-0">
                        <button className="p-1.5 rounded-lg border border-gray-300 bg-white text-gray-500 hover:bg-gray-100"
                          onClick={() => setEmergencyModal({ mode: 'edit', contact: c })}>
                          <Edit2 className="w-3.5 h-3.5" />
                        </button>
                        <button className="p-1.5 rounded-lg border border-gray-300 bg-white text-red-500 hover:bg-red-50"
                          onClick={() => setDeleteTarget(c)}>
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
            }
          </div>

          {/* PAN / Bank — masked, with change-request button */}
          <div className="card">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Lock className="w-4 h-4 text-gray-400" />
                <h3 className="font-semibold text-gray-900">Identity & Bank Details</h3>
              </div>
              <button
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-gray-300 bg-white text-gray-700 text-xs font-medium hover:bg-gray-50"
                onClick={() => setChangeReqOpen(true)}>
                Request Change
              </button>
            </div>
            <p className="text-xs text-yellow-700 bg-yellow-50 rounded-lg px-3 py-2 mb-4">
              Sensitive fields are shown masked. Changes require HR approval and are tracked in the audit log.
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm">
              {[
                ['PAN', identity?.pan_number],
                ['Aadhaar', identity?.aadhaar_number],
                ['Bank', identity?.bank_name],
                ['IFSC', identity?.bank_ifsc],
                ['Account No.', identity?.bank_account_number],
              ].map(([k, v]) => (
                <div key={k}>
                  <p className="text-xs text-gray-400">{k}</p>
                  <p className="font-mono text-gray-800 mt-0.5">{v || '—'}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── MY CHANGE REQUESTS TAB ── */}
      {tab === 'mychanges' && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm text-gray-500">
              Track your submitted change requests and see HR's decisions.
            </p>
            <button
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 transition-colors"
              onClick={() => setChangeReqOpen(true)}>
              <Plus className="w-4 h-4" /> New Request
            </button>
          </div>
          {changeReqs.length === 0 ? (
            <div className="card text-center py-12">
              <p className="text-gray-500 font-medium">No change requests yet</p>
              <p className="text-sm text-gray-400 mt-1">
                Use "Request Change" to update your bank details, PAN, or Aadhaar — these require HR approval.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {changeReqs.map(cr => (
                <div key={cr.change_request_id} className="card">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="font-medium text-gray-900 capitalize">
                          {cr.field_name.replace(/_/g, ' ')}
                        </span>
                        <StatusBadge status={cr.status} />
                      </div>
                      <div className="grid grid-cols-2 gap-3 text-sm">
                        <div className="bg-gray-50 rounded-lg p-2.5">
                          <p className="text-xs text-gray-400 mb-0.5">Old value</p>
                          <p className="font-mono text-gray-500 text-xs">{cr.old_value || '—'}</p>
                        </div>
                        <div className="bg-brand-50 rounded-lg p-2.5">
                          <p className="text-xs text-brand-600 mb-0.5">New value</p>
                          <p className="font-mono text-brand-800 text-xs font-semibold">{cr.new_value}</p>
                        </div>
                      </div>
                      {cr.reason && <p className="text-xs text-gray-400 mt-2 italic">Reason: {cr.reason}</p>}
                      {cr.reviewer_notes && (
                        <p className="text-xs text-gray-600 mt-2 bg-gray-50 rounded p-2">
                          HR note: {cr.reviewer_notes}
                        </p>
                      )}
                    </div>
                    <p className="text-xs text-gray-400 whitespace-nowrap">
                      {cr.requested_at ? format(parseISO(cr.requested_at), 'dd MMM yyyy') : ''}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Modals */}
      <ContactModal open={contactOpen} onClose={() => setContactOpen(false)} current={emp}
        onSuccess={() => { setContactOpen(false); setSuccess('Contact updated.'); reload() }} />
      <AddressModal open={addressOpen} onClose={() => setAddressOpen(false)}
        onSuccess={() => { setAddressOpen(false); setSuccess('Address saved.'); reload() }} />
      <ChangeRequestModal open={changeReqOpen} onClose={() => setChangeReqOpen(false)}
        onSuccess={() => { setChangeReqOpen(false); setSuccess('Change request submitted — pending HR review.'); reload() }} />
      {emergencyModal && (
        <EmergencyContactModal
          mode={emergencyModal.mode}
          contact={emergencyModal.contact}
          onClose={() => setEmergencyModal(null)}
          onSuccess={() => {
            setEmergencyModal(null)
            setSuccess(emergencyModal.mode === 'add' ? 'Emergency contact added.' : 'Emergency contact updated.')
            reload()
          }}
        />
      )}
      <Confirm
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title="Remove emergency contact?"
        message={`This will permanently remove ${deleteTarget?.contact_name} from your emergency contacts.`}
        confirmLabel="Remove"
        danger
        onConfirm={async () => {
          try {
            await profileApi.deleteEmergencyContact(deleteTarget.contact_id)
            setDeleteTarget(null)
            setSuccess('Emergency contact removed.')
            reload()
          } catch (e) {
            setError(e.response?.data?.detail || 'Failed to remove contact')
            setDeleteTarget(null)
          }
        }}
      />
    </div>
  )
}

function ContactModal({ open, onClose, current, onSuccess }) {
  const [phone, setPhone] = useState(current?.phone || '')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  async function save() {
    setLoading(true); setError('')
    try { await profileApi.updateContact({ phone }); onSuccess() }
    catch (e) { setError(e.response?.data?.detail || 'Failed') }
    finally { setLoading(false) }
  }
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold">Edit Contact Info</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">✕</button>
        </div>
        <div className="px-6 py-4 space-y-4">
          {error && <div className="bg-red-50 border border-red-200 text-red-800 rounded-lg p-3 text-sm">{error}</div>}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Phone</label>
            <input className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              value={phone} onChange={e => setPhone(e.target.value)} />
          </div>
        </div>
        <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-100 bg-gray-50 rounded-b-2xl">
          <button className="px-4 py-2 rounded-lg border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50" onClick={onClose}>Cancel</button>
          <button className="px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
            onClick={save} disabled={loading}>{loading ? 'Saving…' : 'Save'}</button>
        </div>
      </div>
    </div>
  )
}

function EmergencyContactModal({ mode, contact, onClose, onSuccess }) {
  const [form, setForm] = useState({
    contact_name: contact?.contact_name || '',
    relationship: contact?.relationship || '',
    phone: contact?.phone || '',
    alternate_phone: contact?.alternate_phone || '',
    is_primary: contact?.is_primary || false,
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const f = k => v => setForm(p => ({ ...p, [k]: v }))

  async function save() {
    if (!form.contact_name.trim() || !form.phone.trim()) return setError('Name and phone are required')
    setLoading(true); setError('')
    try {
      if (mode === 'edit') await profileApi.updateEmergencyContact(contact.contact_id, form)
      else await profileApi.addEmergencyContact(form)
      onSuccess()
    } catch (e) { setError(e.response?.data?.detail || 'Failed to save contact') }
    finally { setLoading(false) }
  }

  return (
    <Modal open onClose={onClose} title={mode === 'edit' ? 'Edit Emergency Contact' : 'Add Emergency Contact'}
      footer={<>
        <button className="btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn-primary" onClick={save} disabled={loading}>{loading ? 'Saving…' : 'Save'}</button>
      </>}>
      <Alert type="error" message={error} onDismiss={() => setError('')} />
      <FormField label="Name" required>
        <input className="input" value={form.contact_name} onChange={e => f('contact_name')(e.target.value)} />
      </FormField>
      <FormField label="Relationship">
        <input className="input" placeholder="e.g. mother, spouse, sibling"
          value={form.relationship} onChange={e => f('relationship')(e.target.value)} />
      </FormField>
      <FormField label="Phone" required>
        <input className="input" value={form.phone} onChange={e => f('phone')(e.target.value)} />
      </FormField>
      <FormField label="Alternate Phone">
        <input className="input" value={form.alternate_phone} onChange={e => f('alternate_phone')(e.target.value)} />
      </FormField>
      <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
        <input type="checkbox" checked={form.is_primary} onChange={e => f('is_primary')(e.target.checked)} />
        Set as primary emergency contact
      </label>
    </Modal>
  )
}

function AddressModal({ open, onClose, onSuccess }) {
  const [form, setForm] = useState({ address_type: 'current', address_line1: '', address_line2: '', city: '', state: '', country: 'India', pincode: '' })
  const [loading, setLoading] = useState(false); const [error, setError] = useState('')
  const f = k => v => setForm(p => ({ ...p, [k]: v }))
  async function save() {
    setLoading(true); setError('')
    try { await profileApi.upsertAddress(form); onSuccess() }
    catch (e) { setError(e.response?.data?.detail || 'Failed') }
    finally { setLoading(false) }
  }
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold">Add / Update Address</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">✕</button>
        </div>
        <div className="px-6 py-4 space-y-4">
          {error && <div className="bg-red-50 border border-red-200 text-red-800 rounded-lg p-3 text-sm">{error}</div>}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Type</label>
            <select className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              value={form.address_type} onChange={e => f('address_type')(e.target.value)}>
              <option value="current">Current</option>
              <option value="permanent">Permanent</option>
              <option value="other">Other</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Line 1 *</label>
            <input className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              value={form.address_line1} onChange={e => f('address_line1')(e.target.value)} />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Line 2</label>
            <input className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              value={form.address_line2} onChange={e => f('address_line2')(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">City *</label>
              <input className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                value={form.city} onChange={e => f('city')(e.target.value)} />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">State *</label>
              <input className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                value={form.state} onChange={e => f('state')(e.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Country</label>
              <input className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                value={form.country} onChange={e => f('country')(e.target.value)} />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Pincode</label>
              <input className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                value={form.pincode} onChange={e => f('pincode')(e.target.value)} />
            </div>
          </div>
        </div>
        <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-100 bg-gray-50 rounded-b-2xl">
          <button className="px-4 py-2 rounded-lg border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50" onClick={onClose}>Cancel</button>
          <button className="px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
            onClick={save} disabled={loading}>{loading ? 'Saving…' : 'Save'}</button>
        </div>
      </div>
    </div>
  )
}

function ChangeRequestModal({ open, onClose, onSuccess }) {
  const FIELDS = ['bank_account_number','bank_name','bank_ifsc','bank_branch','pan_number','aadhaar_number']
  const GROUPS = {
    bank_account_number: 'bank', bank_name: 'bank', bank_ifsc: 'bank',
    bank_branch: 'bank', pan_number: 'identity', aadhaar_number: 'identity',
  }
  const [form, setForm] = useState({ field_name: '', new_value: '', reason: '' })
  const [loading, setLoading] = useState(false); const [error, setError] = useState('')
  const f = k => v => setForm(p => ({ ...p, [k]: v }))
  async function save() {
    if (!form.field_name || !form.new_value) return setError('Fill in all required fields')
    setLoading(true); setError('')
    try {
      await profileApi.submitChangeRequest({
        field_group: GROUPS[form.field_name],
        field_name: form.field_name,
        new_value: form.new_value,
        reason: form.reason,
      })
      onSuccess()
    } catch (e) { setError(e.response?.data?.detail || 'Failed') }
    finally { setLoading(false) }
  }
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold">Request Field Change</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">✕</button>
        </div>
        <div className="px-6 py-4 space-y-4">
          <div className="bg-blue-50 border border-blue-100 rounded-lg p-3 text-sm text-blue-800">
            Changes to sensitive fields require HR approval before taking effect.
          </div>
          {error && <div className="bg-red-50 border border-red-200 text-red-800 rounded-lg p-3 text-sm">{error}</div>}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Field to change *</label>
            <select className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              value={form.field_name} onChange={e => f('field_name')(e.target.value)}>
              <option value="">Select field…</option>
              {FIELDS.map(fi => <option key={fi} value={fi}>{fi.replace(/_/g, ' ')}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">New value *</label>
            <input className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              value={form.new_value} onChange={e => f('new_value')(e.target.value)} />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Reason</label>
            <textarea rows={2} className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              value={form.reason} onChange={e => f('reason')(e.target.value)} />
          </div>
        </div>
        <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-100 bg-gray-50 rounded-b-2xl">
          <button className="px-4 py-2 rounded-lg border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50" onClick={onClose}>Cancel</button>
          <button className="px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
            onClick={save} disabled={loading}>{loading ? 'Submitting…' : 'Submit'}</button>
        </div>
      </div>
    </div>
  )
}
