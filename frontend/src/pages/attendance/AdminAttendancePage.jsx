import { useState, useEffect } from 'react'
import { format, startOfMonth, endOfMonth, eachDayOfInterval, parseISO, isSameDay } from 'date-fns'
import { ChevronLeft, ChevronRight, Edit2, Search } from 'lucide-react'
import api from '../../api/client'
import { orgApi } from '../../api/services'
import { useAuth } from '../../context/AuthContext'
import { PageSpinner, Alert } from '../../components/ui'

const STATUS_COLORS = {
  present:  'bg-green-100 text-green-700 hover:bg-green-200',
  wfh:      'bg-blue-100 text-blue-700 hover:bg-blue-200',
  absent:   'bg-red-100 text-red-700 hover:bg-red-200',
  on_leave: 'bg-yellow-100 text-yellow-800 hover:bg-yellow-200',
  half_day: 'bg-purple-100 text-purple-700 hover:bg-purple-200',
  holiday:  'bg-orange-100 text-orange-700',
  weekend:  'bg-gray-100 text-gray-400',
}

const STATUS_OPTIONS = ['present','absent','wfh','on_leave','half_day']

export default function AdminAttendancePage() {
  const { isHRAdmin } = useAuth()
  const today = new Date()
  const [year, setYear]     = useState(today.getFullYear())
  const [month, setMonth]   = useState(today.getMonth() + 1)
  const [employees, setEmployees] = useState([])
  const [selectedEmp, setSelectedEmp] = useState(null)
  const [records, setRecords]   = useState([])
  const [holidays, setHolidays] = useState([])
  const [search, setSearch]     = useState('')
  const [loading, setLoading]   = useState(false)
  const [editModal, setEditModal] = useState(null)  // { date, currentStatus }
  const [error, setError]   = useState('')
  const [success, setSuccess] = useState('')

  // Employee search is on-demand (see searchEmployees below) — nothing to preload.
  useEffect(() => {}, [])

  async function searchEmployees(q) {
    if (!q.trim()) { setEmployees([]); return }
    try {
      const r = await orgApi.searchEmployees(q)
      setEmployees(r.data)
    } catch (e) { setError('Search failed') }
  }

  async function loadAttendance(empId) {
    setLoading(true)
    try {
      const [att, hols] = await Promise.all([
        api.get(`/attendance/admin/${empId}`, { params: { year, month } }),
        api.get('/attendance/holidays', { params: { year } }),
      ])
      setRecords(att.data)
      setHolidays(hols.data)
    } catch (e) { setError('Failed to load attendance') }
    finally { setLoading(false) }
  }

  useEffect(() => {
    if (selectedEmp) loadAttendance(selectedEmp.employee_id)
  }, [selectedEmp, year, month])

  function prevMonth() { if (month===1){setYear(y=>y-1);setMonth(12)}else setMonth(m=>m-1) }
  function nextMonth() { if (month===12){setYear(y=>y+1);setMonth(1)}else setMonth(m=>m+1) }

  function recordForDay(d) { return records.find(r => isSameDay(parseISO(r.attendance_date), d)) }
  function holidayForDay(d) { return holidays.find(h => isSameDay(parseISO(h.holiday_date), d)) }

  async function handleEdit(date, newStatus, reason, checkIn, checkOut) {
    try {
      await api.post('/attendance/admin/edit', {
        employee_id:     selectedEmp.employee_id,
        attendance_date: date,
        new_status:      newStatus,
        reason:          reason,
        check_in_time:   checkIn  ? `${date}T${checkIn}:00` : null,
        check_out_time:  checkOut ? `${date}T${checkOut}:00` : null,
      })
      setEditModal(null)
      setSuccess(`Attendance for ${format(parseISO(date), 'dd MMM yyyy')} updated to ${newStatus}`)
      loadAttendance(selectedEmp.employee_id)
    } catch (e) { setError(e.response?.data?.detail || 'Edit failed') }
  }

  if (!isHRAdmin()) return (
    <div className="text-center py-16 text-gray-500">Access restricted to HR Admins.</div>
  )

  const monthStart = startOfMonth(new Date(year, month - 1))
  const days = eachDayOfInterval({ start: monthStart, end: endOfMonth(monthStart) })
  const startPad = monthStart.getDay()

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">HR Admin — Attendance Management</h1>

      <Alert type="error"   message={error}   onDismiss={() => setError('')} />
      <Alert type="success" message={success} onDismiss={() => setSuccess('')} />

      {/* Employee search */}
      <div className="card mb-6">
        <h2 className="font-semibold text-gray-900 mb-3">Select Employee</h2>
        <div className="flex gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
            <input
              className="w-full pl-9 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              placeholder="Type employee name to search…"
              value={search}
              onChange={e => { setSearch(e.target.value); searchEmployees(e.target.value) }}
            />
          </div>
        </div>
        {employees.length > 0 && (
          <div className="mt-2 border border-gray-100 rounded-xl overflow-hidden">
            {employees.map(emp => (
              <button key={emp.employee_id}
                className={`w-full text-left px-4 py-3 text-sm hover:bg-brand-50 transition-colors
                  ${selectedEmp?.employee_id === emp.employee_id ? 'bg-brand-50 text-brand-700 font-medium' : 'text-gray-700'}`}
                onClick={() => { setSelectedEmp(emp); setSearch(emp.full_name); setEmployees([]) }}>
                {emp.full_name}
              </button>
            ))}
          </div>
        )}
        {selectedEmp && (
          <p className="mt-2 text-sm text-brand-600 font-medium">
            Viewing: {selectedEmp.full_name}
          </p>
        )}
      </div>

      {!selectedEmp && (
        <div className="text-center py-16 text-gray-400">
          <Edit2 className="w-12 h-12 mx-auto mb-3 text-gray-200" />
          <p className="font-medium text-gray-600">Search and select an employee to view and edit attendance</p>
        </div>
      )}

      {selectedEmp && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <button onClick={prevMonth} className="p-2 rounded-lg border border-gray-300 hover:bg-gray-50">
              <ChevronLeft className="w-4 h-4" />
            </button>
            <h2 className="font-semibold text-gray-900">
              {format(new Date(year, month-1), 'MMMM yyyy')}
            </h2>
            <button onClick={nextMonth} className="p-2 rounded-lg border border-gray-300 hover:bg-gray-50">
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          <p className="text-xs text-brand-600 bg-brand-50 rounded-lg px-3 py-2 mb-4">
            Click any working day to edit attendance. All edits are logged in the audit trail.
          </p>

          <div className="grid grid-cols-7 mb-1">
            {['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].map((d,i) => (
              <div key={d} className={`text-center text-xs font-semibold py-2 ${i===0||i===6?'text-red-400':'text-gray-400'}`}>{d}</div>
            ))}
          </div>

          {loading ? <PageSpinner /> : (
            <div className="grid grid-cols-7 gap-1">
              {Array.from({ length: startPad }).map((_,i) => <div key={`pad-${i}`} />)}
              {days.map(day => {
                const rec     = recordForDay(day)
                const holiday = holidayForDay(day)
                const isWeekend = day.getDay() === 0 || day.getDay() === 6
                const isTodayDay = isSameDay(day, today)

                let label='', colorCls='', clickable=false

                if (isWeekend) {
                  colorCls = STATUS_COLORS.weekend
                  label = day.getDay()===0?'Sun':'Sat'
                } else if (holiday) {
                  colorCls = STATUS_COLORS.holiday
                  label = holiday.holiday_name.length>7 ? holiday.holiday_name.slice(0,7)+'…' : holiday.holiday_name
                } else if (rec) {
                  colorCls = STATUS_COLORS[rec.status] || 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                  label = rec.status==='present'?(rec.is_late?'Late':'P')
                        : rec.status==='wfh'?'WFH'
                        : rec.status==='on_leave'?'Leave'
                        : rec.status==='absent'?'A'
                        : rec.status==='half_day'?'½'
                        : rec.status
                  clickable = true
                } else {
                  colorCls = 'bg-gray-50 text-gray-300 hover:bg-gray-100 border border-dashed border-gray-200'
                  label = '+'
                  clickable = true
                }

                return (
                  <button key={day.toISOString()}
                    disabled={isWeekend || !!holiday}
                    onClick={() => clickable && !isWeekend && !holiday && setEditModal({
                      date: day.toISOString().split('T')[0],
                      currentStatus: rec?.status || '',
                      currentCheckIn: rec?.check_in_time ? format(parseISO(rec.check_in_time),'HH:mm') : '',
                      currentCheckOut: rec?.check_out_time ? format(parseISO(rec.check_out_time),'HH:mm') : '',
                    })}
                    className={`rounded-xl p-1.5 min-h-[68px] flex flex-col items-center transition-colors
                      ${isTodayDay?'ring-2 ring-brand-500':'border border-transparent'}
                      ${clickable?'cursor-pointer':'cursor-default'}
                      ${colorCls}`}>
                    <span className={`text-xs font-medium mb-1 ${isTodayDay?'text-brand-600 font-bold':''}`}>
                      {format(day,'d')}
                    </span>
                    {label && (
                      <span className="text-xs font-medium leading-tight text-center">{label}</span>
                    )}
                  </button>
                )
              })}
            </div>
          )}

          {/* Legend */}
          <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t border-gray-100">
            {[
              ['Present (P)','bg-green-100 text-green-700'],
              ['WFH','bg-blue-100 text-blue-700'],
              ['On Leave','bg-yellow-100 text-yellow-700'],
              ['Absent (A)','bg-red-100 text-red-700'],
              ['Holiday','bg-orange-100 text-orange-700'],
              ['Not recorded (click to add)','bg-gray-50 text-gray-400 border border-dashed border-gray-200'],
            ].map(([l,c])=>(
              <span key={l} className={`text-xs px-2 py-1 rounded-md font-medium ${c}`}>{l}</span>
            ))}
          </div>
        </div>
      )}

      {editModal && (
        <EditModal
          date={editModal.date}
          currentStatus={editModal.currentStatus}
          currentCheckIn={editModal.currentCheckIn}
          currentCheckOut={editModal.currentCheckOut}
          employeeName={selectedEmp?.full_name}
          onClose={() => setEditModal(null)}
          onSave={handleEdit}
        />
      )}
    </div>
  )
}

function EditModal({ date, currentStatus, currentCheckIn, currentCheckOut, employeeName, onClose, onSave }) {
  const [status, setStatus]     = useState(currentStatus || 'present')
  const [checkIn, setCheckIn]   = useState(currentCheckIn || '')
  const [checkOut, setCheckOut] = useState(currentCheckOut || '')
  const [reason, setReason]     = useState('')
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState('')

  async function save() {
    if (!reason.trim()) return setError('Reason is required for audit purposes')
    setLoading(true)
    await onSave(date, status, reason, checkIn, checkOut)
    setLoading(false)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <div>
            <h2 className="text-base font-semibold">Edit Attendance</h2>
            <p className="text-xs text-gray-500 mt-0.5">
              {employeeName} · {format(new Date(date + 'T00:00:00'), 'dd MMM yyyy, EEEE')}
            </p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">✕</button>
        </div>
        <div className="px-6 py-4 space-y-4">
          {error && <div className="bg-red-50 border border-red-200 text-red-800 rounded-lg p-3 text-sm">{error}</div>}
          <div className="bg-yellow-50 border border-yellow-100 rounded-lg p-3 text-xs text-yellow-800">
            ⚠ This edit is permanent and will be logged in the audit trail with your name and reason.
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Status *</label>
            <div className="grid grid-cols-3 gap-2">
              {['present','wfh','on_leave','absent','half_day'].map(s => (
                <button key={s}
                  className={`py-2 px-3 rounded-lg text-xs font-medium border transition-colors
                    ${status===s
                      ? 'bg-brand-600 text-white border-brand-600'
                      : 'bg-white text-gray-600 border-gray-200 hover:border-brand-300'}`}
                  onClick={() => setStatus(s)}>
                  {s.replace(/_/g,' ')}
                </button>
              ))}
            </div>
          </div>
          {(status==='present'||status==='wfh'||status==='half_day') && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Check-in</label>
                <input type="time" className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  value={checkIn} onChange={e => setCheckIn(e.target.value)} />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Check-out</label>
                <input type="time" className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  value={checkOut} onChange={e => setCheckOut(e.target.value)} />
              </div>
            </div>
          )}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Reason for edit *</label>
            <textarea rows={3} className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              value={reason} onChange={e => setReason(e.target.value)}
              placeholder="e.g. Employee was marked absent but badge log confirms presence…" />
          </div>
        </div>
        <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-100 bg-gray-50 rounded-b-2xl">
          <button className="px-4 py-2 rounded-lg border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50"
            onClick={onClose}>Cancel</button>
          <button className="px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
            onClick={save} disabled={loading}>{loading?'Saving…':'Save Edit'}</button>
        </div>
      </div>
    </div>
  )
}
