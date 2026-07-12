import { useState, useEffect } from 'react'
import { format, startOfMonth, endOfMonth, eachDayOfInterval, parseISO, isSameDay } from 'date-fns'
import { ChevronLeft, ChevronRight, Plus, Trash2, Calendar } from 'lucide-react'
import { attendanceApi, holidayApi } from '../../api/services'
import { useAuth } from '../../context/AuthContext'

export default function AttendancePage() {
  const { isManager, isHRAdmin } = useAuth()
  const today = new Date()
  const [year, setYear] = useState(today.getFullYear())
  const [month, setMonth] = useState(today.getMonth() + 1)
  const [records, setRecords] = useState([])
  const [summary, setSummary] = useState(null)
  const [myRegs, setMyRegs] = useState([])
  const [regQueue, setRegQueue] = useState([])
  const [holidays, setHolidays] = useState([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('calendar')
  const [regOpen, setRegOpen] = useState(false)
  const [holidayOpen, setHolidayOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  async function reload() {
    setLoading(true)
    try {
      const [r, s, mr, h] = await Promise.all([
        attendanceApi.myRecords(year, month),
        attendanceApi.summary(year, month),
        attendanceApi.myRegularisations(),
        holidayApi.list(year),
      ])
      setRecords(r.data); setSummary(s.data); setMyRegs(mr.data); setHolidays(h.data)
      if (isManager() || isHRAdmin()) {
        const q = await attendanceApi.regQueue(); setRegQueue(q.data)
      }
    } finally { setLoading(false) }
  }
  useEffect(() => { reload() }, [year, month])

  function prevMonth() { if (month === 1) { setYear(y => y-1); setMonth(12) } else setMonth(m => m-1) }
  function nextMonth() { if (month === 12) { setYear(y => y+1); setMonth(1) } else setMonth(m => m+1) }
  function recordForDay(d) { return records.find(r => isSameDay(parseISO(r.attendance_date), d)) }
  function holidayForDay(d) { return holidays.find(h => isSameDay(parseISO(h.holiday_date), d)) }

  async function decideReg(id, decision) {
    try { await attendanceApi.decideReg(id, { decision }); setSuccess(`Regularisation ${decision}.`); reload() }
    catch (e) { setError(e.response?.data?.detail || 'Failed') }
  }

  async function handleDeleteHoliday() {
    try { await holidayApi.delete(deleteTarget.holiday_id); setDeleteTarget(null); setSuccess('Holiday removed.'); reload() }
    catch (e) { setError(e.response?.data?.detail || 'Failed') }
  }

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="w-8 h-8 border-2 border-brand-200 border-t-brand-600 rounded-full animate-spin" />
    </div>
  )

  const monthStart = startOfMonth(new Date(year, month - 1))
  const days = eachDayOfInterval({ start: monthStart, end: endOfMonth(monthStart) })
  const startPad = monthStart.getDay()

  const STATUS_COLORS = {
    present:  'bg-green-100 text-green-700',
    wfh:      'bg-blue-100 text-blue-700',
    absent:   'bg-red-100 text-red-700',
    on_leave: 'bg-yellow-100 text-yellow-800',
    half_day: 'bg-purple-100 text-purple-700',
  }

  const tabs = [
    { key: 'calendar', label: 'My Calendar' },
    { key: 'regs', label: `My Regularisations (${myRegs.length})` },
    ...(isManager() || isHRAdmin() ? [{ key: 'queue', label: `Approval Queue (${regQueue.length})` }] : []),
    ...(isHRAdmin() ? [{ key: 'holidays', label: `Holidays (${holidays.length})` }] : []),
  ]

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Attendance</h1>
        <div className="flex gap-2">
          {isHRAdmin() && (
            <button onClick={() => { setTab('holidays'); setHolidayOpen(true) }}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-gray-300 bg-white text-gray-700 text-sm font-medium hover:bg-gray-50 transition-colors">
              <Calendar className="w-4 h-4" /> Add Holiday
            </button>
          )}
          <button onClick={() => setRegOpen(true)}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 transition-colors">
            <Plus className="w-4 h-4" /> Regularise
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 flex items-center gap-2 bg-red-50 border border-red-200 text-red-800 rounded-lg p-3 text-sm">
          <span className="flex-1">{error}</span>
          <button onClick={() => setError('')} className="opacity-60 hover:opacity-100">✕</button>
        </div>
      )}
      {success && (
        <div className="mb-4 flex items-center gap-2 bg-green-50 border border-green-200 text-green-800 rounded-lg p-3 text-sm">
          <span className="flex-1">{success}</span>
          <button onClick={() => setSuccess('')} className="opacity-60 hover:opacity-100">✕</button>
        </div>
      )}

      {/* Summary */}
      {summary && (
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-3 mb-6">
          {[
            { label: 'Present',  value: summary.days_present,         color: 'text-green-600' },
            { label: 'WFH',      value: summary.days_wfh,             color: 'text-blue-600' },
            { label: 'On Leave', value: summary.days_on_leave,        color: 'text-yellow-600' },
            { label: 'Absent',   value: summary.days_absent,          color: 'text-red-600' },
            { label: 'Late',     value: summary.late_arrivals,        color: 'text-orange-600' },
            { label: 'Hours',    value: `${summary.total_hours_worked}h`, color: 'text-brand-600' },
          ].map(s => (
            <div key={s.label} className="bg-white rounded-2xl shadow-sm border border-gray-100 py-3 text-center">
              <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
              <p className="text-xs text-gray-500 mt-0.5">{s.label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 p-1 rounded-xl mb-4 flex-wrap">
        {tabs.map(t => (
          <button key={t.key}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors
              ${tab === t.key ? 'bg-white shadow text-gray-900' : 'text-gray-500 hover:text-gray-700'}`}
            onClick={() => setTab(t.key)}>{t.label}</button>
        ))}
      </div>

      {/* ── CALENDAR ── */}
      {tab === 'calendar' && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
          <div className="flex items-center justify-between mb-4">
            <button onClick={prevMonth} className="p-2 rounded-lg border border-gray-300 bg-white hover:bg-gray-50 transition-colors">
              <ChevronLeft className="w-4 h-4" />
            </button>
            <h2 className="font-semibold text-gray-900 text-lg">{format(new Date(year, month-1), 'MMMM yyyy')}</h2>
            <button onClick={nextMonth} className="p-2 rounded-lg border border-gray-300 bg-white hover:bg-gray-50 transition-colors">
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          {/* Day headers */}
          <div className="grid grid-cols-7 mb-1">
            {['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].map((d, i) => (
              <div key={d} className={`text-center text-xs font-semibold py-2
                ${i === 0 || i === 6 ? 'text-red-400' : 'text-gray-400'}`}>{d}</div>
            ))}
          </div>

          {/* Grid */}
          <div className="grid grid-cols-7 gap-1">
            {Array.from({ length: startPad }).map((_, i) => <div key={`pad-${i}`} />)}
            {days.map(day => {
              const rec     = recordForDay(day)
              const holiday = holidayForDay(day)
              const isWeekend = day.getDay() === 0 || day.getDay() === 6
              const isTodayDay= isSameDay(day, today)
              const isPast  = day <= today

              let label = null, colorCls = ''

              if (isWeekend) {
                colorCls = 'bg-gray-100 text-gray-400'
                label = day.getDay() === 0 ? 'Sun' : 'Sat'
              } else if (holiday) {
                colorCls = 'bg-orange-100 text-orange-700'
                const n = holiday.holiday_name
                label = n.length > 7 ? n.slice(0, 7) + '…' : n
              } else if (rec) {
                colorCls = STATUS_COLORS[rec.status] || 'bg-gray-100 text-gray-500'
                label = rec.status === 'present' ? (rec.is_late ? 'Late' : 'P')
                      : rec.status === 'wfh'      ? 'WFH'
                      : rec.status === 'on_leave'  ? 'Leave'
                      : rec.status === 'absent'    ? 'A'
                      : rec.status === 'half_day'  ? '½'
                      : rec.status
              }

              return (
                <div key={day.toISOString()}
                  title={holiday?.holiday_name || rec?.status || ''}
                  className={`rounded-xl p-1.5 min-h-[68px] flex flex-col items-center
                    ${isWeekend ? 'bg-gray-50' : 'bg-white'}
                    ${isTodayDay ? 'ring-2 ring-brand-500' : 'border border-gray-100'}`}>
                  <span className={`text-xs font-medium mb-1
                    ${isTodayDay ? 'text-brand-600 font-bold' : isWeekend ? 'text-gray-400' : 'text-gray-600'}`}>
                    {format(day, 'd')}
                  </span>
                  {label && (
                    <span className={`text-xs px-1 py-0.5 rounded-md font-medium text-center leading-tight w-full text-center ${colorCls}`}>
                      {label}
                    </span>
                  )}
                  {!label && isPast && !isWeekend && (
                    <span className="text-xs text-gray-200">—</span>
                  )}
                </div>
              )
            })}
          </div>

          {/* Legend */}
          <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t border-gray-100">
            {[
              ['Present (P)', 'bg-green-100 text-green-700'],
              ['WFH', 'bg-blue-100 text-blue-700'],
              ['On Leave', 'bg-yellow-100 text-yellow-700'],
              ['Absent (A)', 'bg-red-100 text-red-700'],
              ['Holiday', 'bg-orange-100 text-orange-700'],
              ['Weekend', 'bg-gray-100 text-gray-400'],
            ].map(([l, c]) => (
              <span key={l} className={`text-xs px-2 py-1 rounded-md font-medium ${c}`}>{l}</span>
            ))}
          </div>
        </div>
      )}

      {/* ── MY REGULARISATIONS ── */}
      {tab === 'regs' && (
        myRegs.length === 0
          ? <div className="flex flex-col items-center justify-center py-16 text-gray-400">
              <p className="font-medium text-gray-600">No regularisation requests</p>
            </div>
          : <div className="overflow-x-auto rounded-xl border border-gray-100">
              <table className="w-full divide-y divide-gray-100">
                <thead className="bg-gray-50">
                  <tr>
                    {['Date','Requested Status','Reason','Status','Submitted'].map(h => (
                      <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50 bg-white">
                  {myRegs.map(r => (
                    <tr key={r.regularisation_id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium">{format(parseISO(r.attendance_date), 'dd MMM yyyy')}</td>
                      <td className="px-4 py-3 text-sm">{r.requested_status || '—'}</td>
                      <td className="px-4 py-3 text-sm text-gray-400 max-w-xs truncate">{r.reason}</td>
                      <td className="px-4 py-3 text-sm">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium
                          ${r.status === 'approved' ? 'bg-green-100 text-green-800'
                          : r.status === 'rejected' ? 'bg-red-100 text-red-800'
                          : 'bg-yellow-100 text-yellow-800'}`}>{r.status}</span>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-400">
                        {r.requested_at ? format(parseISO(r.requested_at), 'dd MMM yyyy') : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
      )}

      {/* ── APPROVAL QUEUE ── */}
      {tab === 'queue' && (
        regQueue.length === 0
          ? <div className="flex flex-col items-center justify-center py-16 text-gray-400">
              <p className="font-medium text-gray-600">No pending regularisations</p>
            </div>
          : <div className="overflow-x-auto rounded-xl border border-gray-100">
              <table className="w-full divide-y divide-gray-100">
                <thead className="bg-gray-50">
                  <tr>
                    {['Employee','Date','Reason','Actions'].map(h => (
                      <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50 bg-white">
                  {regQueue.map(r => (
                    <tr key={r.regularisation_id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium">{r.employee_name}</td>
                      <td className="px-4 py-3 text-sm">{format(parseISO(r.attendance_date), 'dd MMM yyyy')}</td>
                      <td className="px-4 py-3 text-sm text-gray-500 max-w-xs truncate">{r.reason}</td>
                      <td className="px-4 py-3 text-sm">
                        <div className="flex gap-2">
                          <button className="text-xs text-green-600 hover:text-green-700 font-medium"
                            onClick={() => decideReg(r.regularisation_id, 'approved')}>Approve</button>
                          <button className="text-xs text-red-600 hover:text-red-700 font-medium"
                            onClick={() => decideReg(r.regularisation_id, 'rejected')}>Reject</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
      )}

      {/* ── HOLIDAYS (HR Admin) ── */}
      {tab === 'holidays' && isHRAdmin() && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="font-semibold text-gray-900">Holiday Calendar — {year}</h2>
              <p className="text-xs text-gray-500 mt-0.5">Holidays appear in orange in all employees' calendars</p>
            </div>
            <button onClick={() => setHolidayOpen(true)}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 transition-colors">
              <Plus className="w-4 h-4" /> Add Holiday
            </button>
          </div>

          {holidays.length === 0
            ? <div className="flex flex-col items-center justify-center py-16 text-gray-400">
                <Calendar className="w-12 h-12 mb-3 text-gray-300" />
                <p className="font-medium text-gray-600">No holidays added yet</p>
                <p className="text-sm text-gray-400 mt-1">Add public and company holidays to reflect in all calendars</p>
              </div>
            : <div className="overflow-x-auto rounded-xl border border-gray-100">
                <table className="w-full divide-y divide-gray-100">
                  <thead className="bg-gray-50">
                    <tr>
                      {['Date','Day','Holiday Name','Type','Remove'].map(h => (
                        <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50 bg-white">
                    {holidays.map(h => (
                      <tr key={h.holiday_id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm font-medium">{format(parseISO(h.holiday_date), 'dd MMM yyyy')}</td>
                        <td className="px-4 py-3 text-sm text-gray-500">{format(parseISO(h.holiday_date), 'EEEE')}</td>
                        <td className="px-4 py-3 text-sm font-medium text-orange-700">{h.holiday_name}</td>
                        <td className="px-4 py-3 text-sm">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium
                            ${h.holiday_type === 'public' ? 'bg-blue-100 text-blue-800'
                            : h.holiday_type === 'company' ? 'bg-brand-100 text-brand-800'
                            : 'bg-gray-100 text-gray-600'}`}>{h.holiday_type}</span>
                        </td>
                        <td className="px-4 py-3 text-sm">
                          <button className="text-red-400 hover:text-red-600 transition-colors"
                            onClick={() => setDeleteTarget(h)}>
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
          }
        </div>
      )}

      {/* ── MODALS ── */}
      {regOpen && <RegularisationModal onClose={() => setRegOpen(false)}
        onSuccess={() => { setRegOpen(false); setSuccess('Regularisation request submitted.'); reload() }} />}

      {holidayOpen && <AddHolidayModal onClose={() => setHolidayOpen(false)}
        onSuccess={() => { setHolidayOpen(false); setSuccess('Holiday added — visible in all employee calendars.'); reload() }} />}

      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-6">
            <h2 className="text-base font-semibold text-gray-900 mb-2">Remove Holiday</h2>
            <p className="text-sm text-gray-600 mb-4">
              Remove <strong>"{deleteTarget.holiday_name}"</strong> ({format(parseISO(deleteTarget.holiday_date), 'dd MMM yyyy')}) from the holiday calendar?
            </p>
            <div className="flex justify-end gap-3">
              <button className="px-4 py-2 rounded-lg border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50"
                onClick={() => setDeleteTarget(null)}>Cancel</button>
              <button className="px-4 py-2 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700"
                onClick={handleDeleteHoliday}>Remove</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function RegularisationModal({ onClose, onSuccess }) {
  const [form, setForm] = useState({ attendance_date: '', requested_check_in: '', requested_check_out: '', requested_status: 'present', reason: '' })
  const [loading, setLoading] = useState(false); const [error, setError] = useState('')
  const f = k => v => setForm(p => ({ ...p, [k]: v }))
  async function submit() {
    if (!form.attendance_date || !form.reason) return setError('Date and reason are required')
    setLoading(true); setError('')
    try {
      await attendanceApi.regularise({
        attendance_date: form.attendance_date,
        requested_check_in:  form.requested_check_in  ? `${form.attendance_date}T${form.requested_check_in}:00`  : null,
        requested_check_out: form.requested_check_out ? `${form.attendance_date}T${form.requested_check_out}:00` : null,
        requested_status: form.requested_status,
        reason: form.reason,
      })
      onSuccess()
    } catch (e) { setError(e.response?.data?.detail || 'Failed') }
    finally { setLoading(false) }
  }
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold">Request Attendance Regularisation</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">✕</button>
        </div>
        <div className="px-6 py-4 space-y-4">
          {error && <div className="bg-red-50 border border-red-200 text-red-800 rounded-lg p-3 text-sm">{error}</div>}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Date <span className="text-red-500">*</span></label>
            <input type="date" className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              value={form.attendance_date} max={new Date().toISOString().split('T')[0]}
              onChange={e => f('attendance_date')(e.target.value)} />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Requested Status</label>
            <select className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              value={form.requested_status} onChange={e => f('requested_status')(e.target.value)}>
              <option value="present">Present</option>
              <option value="wfh">WFH</option>
              <option value="half_day">Half Day</option>
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Check-in time</label>
              <input type="time" className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                value={form.requested_check_in} onChange={e => f('requested_check_in')(e.target.value)} />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Check-out time</label>
              <input type="time" className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                value={form.requested_check_out} onChange={e => f('requested_check_out')(e.target.value)} />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Reason <span className="text-red-500">*</span></label>
            <textarea rows={3} className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              value={form.reason} onChange={e => f('reason')(e.target.value)}
              placeholder="Explain why attendance needs correction…" />
          </div>
        </div>
        <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-100 bg-gray-50 rounded-b-2xl">
          <button className="px-4 py-2 rounded-lg border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50" onClick={onClose}>Cancel</button>
          <button className="px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
            onClick={submit} disabled={loading}>{loading ? 'Submitting…' : 'Submit'}</button>
        </div>
      </div>
    </div>
  )
}

function AddHolidayModal({ onClose, onSuccess }) {
  const [form, setForm] = useState({ holiday_date: '', holiday_name: '', holiday_type: 'public' })
  const [loading, setLoading] = useState(false); const [error, setError] = useState('')
  const f = k => v => setForm(p => ({ ...p, [k]: v }))
  async function submit() {
    if (!form.holiday_date || !form.holiday_name) return setError('Date and name are required')
    setLoading(true); setError('')
    try { await holidayApi.add(form); onSuccess() }
    catch (e) { setError(e.response?.data?.detail || 'Failed') }
    finally { setLoading(false) }
  }
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold">Add Holiday</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">✕</button>
        </div>
        <div className="px-6 py-4 space-y-4">
          {error && <div className="bg-red-50 border border-red-200 text-red-800 rounded-lg p-3 text-sm">{error}</div>}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Date <span className="text-red-500">*</span></label>
            <input type="date" className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              value={form.holiday_date} onChange={e => f('holiday_date')(e.target.value)} />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Holiday Name <span className="text-red-500">*</span></label>
            <input className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              value={form.holiday_name} onChange={e => f('holiday_name')(e.target.value)}
              placeholder="e.g. Diwali, Christmas, Company Foundation Day" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Type</label>
            <select className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              value={form.holiday_type} onChange={e => f('holiday_type')(e.target.value)}>
              <option value="public">Public Holiday</option>
              <option value="company">Company Holiday</option>
              <option value="optional">Optional Holiday</option>
            </select>
          </div>
        </div>
        <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-100 bg-gray-50 rounded-b-2xl">
          <button className="px-4 py-2 rounded-lg border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50" onClick={onClose}>Cancel</button>
          <button className="px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
            onClick={submit} disabled={loading}>{loading ? 'Adding…' : 'Add Holiday'}</button>
        </div>
      </div>
    </div>
  )
}
