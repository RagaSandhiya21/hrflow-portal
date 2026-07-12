import { useState, useEffect } from 'react'
import { Search, Edit2, Users, Plus, Building2, Trash2, UserX } from 'lucide-react'
import { orgApi, hrProfileApi } from '../../api/services'
import { PageSpinner, Alert, Modal, FormField, EmptyState, Confirm } from '../../components/ui'

/**
 * HR Admin only: browse employees, assign/reassign their manager (and
 * department/team/designation), directly edit their profile, deactivate
 * (offboard) employees, and manage the org structure itself (create,
 * rename, and retire departments/teams/designations) as the org grows
 * across multiple projects.
 */
export default function EmployeeManagementPage() {
  const [search, setSearch] = useState('')
  const [employees, setEmployees] = useState([])
  const [managers, setManagers] = useState([])
  const [departments, setDepartments] = useState([])
  const [designations, setDesignations] = useState([])
  const [loading, setLoading] = useState(true)
  const [editTarget, setEditTarget] = useState(null)
  const [deactivateTarget, setDeactivateTarget] = useState(null)
  const [orgManagerOpen, setOrgManagerOpen] = useState(false)
  const [error, setError] = useState(''); const [success, setSuccess] = useState('')

  async function loadDirectory(q = '') {
    setLoading(true)
    try {
      const r = await orgApi.searchEmployees(q)
      setEmployees(r.data)
    } catch (e) { setError('Failed to load employees') }
    finally { setLoading(false) }
  }

  function loadOrgLookups() {
    orgApi.managers().then(r => setManagers(r.data)).catch(() => {})
    orgApi.departments().then(r => setDepartments(r.data)).catch(() => {})
    orgApi.designations().then(r => setDesignations(r.data)).catch(() => {})
  }

  useEffect(() => {
    loadDirectory('')
    loadOrgLookups()
  }, [])

  function onSearchChange(v) {
    setSearch(v)
    loadDirectory(v)
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="page-title mb-1">Employee Management</h1>
        <p className="text-sm text-gray-500">
          Assign managers, departments, and teams — and edit or deactivate any employee's profile.
        </p>
      </div>

      <Alert type="error" message={error} onDismiss={() => setError('')} />
      <Alert type="success" message={success} onDismiss={() => setSuccess('')} />

      {/* Org structure — create, rename, or retire departments/teams/
          designations as the company grows across multiple projects. */}
      <div className="card mb-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-semibold text-gray-900 text-sm">Org Structure</h2>
            <p className="text-xs text-gray-400 mt-1">
              {departments.length} department{departments.length !== 1 ? 's' : ''} · {designations.length} designation{designations.length !== 1 ? 's' : ''} on file.
              System roles (employee / manager / HR Admin / IT Admin) are fixed and tied to permissions — use the manager picker below instead.
            </p>
          </div>
          <button className="btn-secondary text-xs py-1.5 shrink-0" onClick={() => setOrgManagerOpen(true)}>
            <Building2 className="w-3.5 h-3.5" /> Manage Departments, Teams & Designations
          </button>
        </div>
      </div>

      <div className="card mb-4">
        <div className="relative">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
          <input
            className="w-full pl-9 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            placeholder="Search by name, employee code, or email…"
            value={search}
            onChange={e => onSearchChange(e.target.value)}
          />
        </div>
      </div>

      {loading ? <PageSpinner /> : employees.length === 0 ? (
        <EmptyState title="No employees found" description="Try a different search term." icon={<Users className="w-12 h-12" />} />
      ) : (
        <div className="card p-0 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs font-semibold text-gray-500 uppercase">
              <tr>
                <th className="px-4 py-3">Employee</th>
                <th className="px-4 py-3">Role</th>
                <th className="px-4 py-3">Department</th>
                <th className="px-4 py-3">Team</th>
                <th className="px-4 py-3">Manager</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {employees.map(e => (
                <tr key={e.employee_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <p className="font-medium text-gray-900">{e.full_name}</p>
                    <p className="text-xs text-gray-400">{e.employee_code} · {e.email}</p>
                  </td>
                  <td className="px-4 py-3 capitalize text-gray-600">{e.role}</td>
                  <td className="px-4 py-3 text-gray-600">{e.department_name || '—'}</td>
                  <td className="px-4 py-3 text-gray-600">{e.team_name || '—'}</td>
                  <td className="px-4 py-3 text-gray-600">{e.manager_name || '—'}</td>
                  <td className="px-4 py-3 text-right whitespace-nowrap">
                    <button className="btn-secondary py-1 text-xs mr-2" onClick={() => setEditTarget(e)}>
                      <Edit2 className="w-3.5 h-3.5" /> Edit
                    </button>
                    <button className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border border-red-200 bg-white text-red-600 text-xs font-medium hover:bg-red-50"
                      onClick={() => setDeactivateTarget(e)}>
                      <UserX className="w-3.5 h-3.5" /> Deactivate
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editTarget && (
        <EditEmployeeModal
          employee={editTarget}
          managers={managers}
          departments={departments}
          designations={designations}
          onClose={() => setEditTarget(null)}
          onSaved={() => {
            setEditTarget(null)
            setSuccess(`${editTarget.full_name}'s profile updated.`)
            loadDirectory(search)
            loadOrgLookups()
          }}
        />
      )}

      <Confirm
        open={!!deactivateTarget}
        onClose={() => setDeactivateTarget(null)}
        title="Deactivate employee?"
        message={`${deactivateTarget?.full_name} will no longer be able to sign in, and will be removed from the employee directory and manager picker. Their historical records (leave, payslips, attendance) are preserved.`}
        confirmLabel="Deactivate"
        danger
        onConfirm={async () => {
          try {
            await orgApi.deactivateEmployee(deactivateTarget.employee_id)
            setSuccess(`${deactivateTarget.full_name} has been deactivated.`)
            setDeactivateTarget(null)
            loadDirectory(search)
            loadOrgLookups()
          } catch (e) {
            setError(e.response?.data?.detail || 'Failed to deactivate employee')
            setDeactivateTarget(null)
          }
        }}
      />

      {orgManagerOpen && (
        <OrgStructureModal
          departments={departments}
          designations={designations}
          onClose={() => setOrgManagerOpen(false)}
          onChanged={() => { loadOrgLookups(); loadDirectory(search) }}
        />
      )}
    </div>
  )
}

// ── Org Structure management (Departments / Teams / Designations) ──────────────

function OrgStructureModal({ departments, designations, onClose, onChanged }) {
  const [tab, setTab] = useState('departments') // departments | teams | designations
  const [teams, setTeams] = useState([])
  const [teamsDeptFilter, setTeamsDeptFilter] = useState('')
  const [formOpen, setFormOpen] = useState(null) // { kind, item? } — item present = edit, absent = create
  const [deleteItem, setDeleteItem] = useState(null) // { kind, id, label }
  const [error, setError] = useState('')

  function loadTeams(deptId) {
    orgApi.teams(deptId || undefined).then(r => setTeams(r.data)).catch(() => setTeams([]))
  }
  useEffect(() => { if (tab === 'teams') loadTeams(teamsDeptFilter) }, [tab, teamsDeptFilter])

  async function handleDelete() {
    const { kind, id, label } = deleteItem
    try {
      if (kind === 'department') await orgApi.deleteDepartment(id)
      else if (kind === 'team') await orgApi.deleteTeam(id)
      else await orgApi.deleteDesignation(id)
      setDeleteItem(null)
      onChanged()
      if (kind === 'team') loadTeams(teamsDeptFilter)
    } catch (e) {
      setError(e.response?.data?.detail || `Failed to remove ${label}`)
      setDeleteItem(null)
    }
  }

  const tabs = [
    { key: 'departments', label: 'Departments' },
    { key: 'teams', label: 'Teams' },
    { key: 'designations', label: 'Designations' },
  ]

  return (
    <Modal open onClose={onClose} title="Manage Org Structure" wide>
      <Alert type="error" message={error} onDismiss={() => setError('')} />
      <div className="flex gap-1 bg-gray-100 p-1 rounded-xl w-fit mb-4">
        {tabs.map(t => (
          <button key={t.key}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors
              ${tab === t.key ? 'bg-white shadow text-gray-900' : 'text-gray-500 hover:text-gray-700'}`}
            onClick={() => setTab(t.key)}>{t.label}</button>
        ))}
      </div>

      {tab === 'departments' && (
        <ListManager
          items={departments}
          getId={d => d.department_id}
          getLabel={d => `${d.department_name} (${d.department_code})`}
          addLabel="Add Department"
          onAdd={() => setFormOpen({ kind: 'department' })}
          onEdit={d => setFormOpen({ kind: 'department', item: d })}
          onDelete={d => setDeleteItem({ kind: 'department', id: d.department_id, label: d.department_name })}
        />
      )}

      {tab === 'teams' && (
        <div>
          <FormField label="Filter by department">
            <select className="input" value={teamsDeptFilter} onChange={e => setTeamsDeptFilter(e.target.value)}>
              <option value="">All departments</option>
              {departments.map(d => <option key={d.department_id} value={d.department_id}>{d.department_name}</option>)}
            </select>
          </FormField>
          <ListManager
            items={teams}
            getId={t => t.team_id}
            getLabel={t => `${t.team_name} (${t.team_code})`}
            addLabel="Add Team"
            addDisabled={departments.length === 0}
            addDisabledReason="Add a department first"
            onAdd={() => setFormOpen({ kind: 'team' })}
            onEdit={t => setFormOpen({ kind: 'team', item: t })}
            onDelete={t => setDeleteItem({ kind: 'team', id: t.team_id, label: t.team_name })}
          />
        </div>
      )}

      {tab === 'designations' && (
        <ListManager
          items={designations}
          getId={d => d.designation_id}
          getLabel={d => d.level ? `${d.title} (${d.level})` : d.title}
          addLabel="Add Designation"
          onAdd={() => setFormOpen({ kind: 'designation' })}
          onEdit={d => setFormOpen({ kind: 'designation', item: d })}
          onDelete={d => setDeleteItem({ kind: 'designation', id: d.designation_id, label: d.title })}
        />
      )}

      {formOpen && (
        <OrgItemFormModal
          kind={formOpen.kind}
          item={formOpen.item}
          departments={departments}
          onClose={() => setFormOpen(null)}
          onSaved={() => {
            setFormOpen(null)
            onChanged()
            if (formOpen.kind === 'team') loadTeams(teamsDeptFilter)
          }}
        />
      )}

      <Confirm
        open={!!deleteItem}
        onClose={() => setDeleteItem(null)}
        title={`Remove ${deleteItem?.label}?`}
        message="This deactivates it — existing employees keep their historical assignment, but it will no longer be selectable for new ones."
        confirmLabel="Remove"
        danger
        onConfirm={handleDelete}
      />
    </Modal>
  )
}

function ListManager({ items, getId, getLabel, addLabel, addDisabled, addDisabledReason, onAdd, onEdit, onDelete }) {
  return (
    <div>
      <div className="flex justify-end mb-3">
        <button className="btn-secondary text-xs py-1.5" onClick={onAdd} disabled={addDisabled}
          title={addDisabled ? addDisabledReason : undefined}>
          <Plus className="w-3.5 h-3.5" /> {addLabel}
        </button>
      </div>
      {items.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-8">Nothing here yet.</p>
      ) : (
        <div className="divide-y divide-gray-100 border border-gray-100 rounded-xl overflow-hidden">
          {items.map(item => (
            <div key={getId(item)} className="flex items-center justify-between px-4 py-2.5 text-sm hover:bg-gray-50">
              <span className="text-gray-800">{getLabel(item)}</span>
              <div className="flex gap-2 shrink-0">
                <button className="p-1.5 rounded-lg border border-gray-300 bg-white text-gray-500 hover:bg-gray-100"
                  onClick={() => onEdit(item)}>
                  <Edit2 className="w-3.5 h-3.5" />
                </button>
                <button className="p-1.5 rounded-lg border border-gray-300 bg-white text-red-500 hover:bg-red-50"
                  onClick={() => onDelete(item)}>
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function OrgItemFormModal({ kind, item, departments, onClose, onSaved }) {
  const isEdit = !!item
  const [name, setName] = useState(item ? (kind === 'designation' ? item.title : kind === 'department' ? item.department_name : item.team_name) : '')
  const [code, setCode] = useState(item ? (kind === 'department' ? item.department_code : kind === 'team' ? item.team_code : '') : '')
  const [departmentId, setDepartmentId] = useState(item?.department_id || departments[0]?.department_id || '')
  const [level, setLevel] = useState(item?.level || '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const titles = {
    department: isEdit ? 'Edit Department' : 'Add Department',
    team: isEdit ? 'Edit Team' : 'Add Team',
    designation: isEdit ? 'Edit Designation' : 'Add Designation',
  }

  async function save() {
    if (!name.trim()) return setError('Name is required')
    if (kind !== 'designation' && !code.trim()) return setError('Code is required')
    if (kind === 'team' && !departmentId) return setError('Select a department for this team')
    setSaving(true); setError('')
    try {
      if (kind === 'department') {
        const body = { department_name: name, department_code: code }
        if (isEdit) await orgApi.updateDepartment(item.department_id, body)
        else await orgApi.createDepartment(body)
      } else if (kind === 'team') {
        const body = { department_id: Number(departmentId), team_name: name, team_code: code }
        if (isEdit) await orgApi.updateTeam(item.team_id, body)
        else await orgApi.createTeam(body)
      } else {
        const body = { title: name, level: level || undefined }
        if (isEdit) await orgApi.updateDesignation(item.designation_id, body)
        else await orgApi.createDesignation(body)
      }
      onSaved()
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to save')
    } finally { setSaving(false) }
  }

  return (
    <Modal open onClose={onClose} title={titles[kind]}
      footer={<>
        <button className="btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn-primary" onClick={save} disabled={saving}>{saving ? 'Saving…' : 'Save'}</button>
      </>}>
      <Alert type="error" message={error} onDismiss={() => setError('')} />
      {kind === 'team' && (
        <FormField label="Department" required>
          <select className="input" value={departmentId} onChange={e => setDepartmentId(e.target.value)}>
            {departments.length === 0 && <option value="">No departments yet — add one first</option>}
            {departments.map(d => <option key={d.department_id} value={d.department_id}>{d.department_name}</option>)}
          </select>
        </FormField>
      )}
      <FormField label={kind === 'designation' ? 'Title' : 'Name'} required>
        <input className="input" value={name} onChange={e => setName(e.target.value)}
          placeholder={kind === 'department' ? 'e.g. Engineering' : kind === 'team' ? 'e.g. Platform' : 'e.g. Software Engineer'} />
      </FormField>
      {kind !== 'designation' && (
        <FormField label="Code" required>
          <input className="input" value={code} onChange={e => setCode(e.target.value.toUpperCase())}
            placeholder={kind === 'department' ? 'e.g. ENG' : 'e.g. PLAT-1'} />
        </FormField>
      )}
      {kind === 'designation' && (
        <FormField label="Level (optional)">
          <input className="input" value={level} onChange={e => setLevel(e.target.value)}
            placeholder="e.g. junior, senior, lead" />
        </FormField>
      )}
    </Modal>
  )
}

// ── Employee edit (manager/department/team/designation + contact/address) ──────

function EditEmployeeModal({ employee, managers, departments, designations, onClose, onSaved }) {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const [departmentId, setDepartmentId] = useState(employee.department_id || '')
  const [teamId, setTeamId] = useState(employee.team_id || '')
  const [teams, setTeams] = useState([])
  const [designationId, setDesignationId] = useState(employee.designation_id || '')
  const [managerId, setManagerId] = useState(employee.manager_id || '')
  const [phone, setPhone] = useState('')
  const [addressLine1, setAddressLine1] = useState('')
  const [city, setCity] = useState('')
  const [state, setState] = useState('')

  useEffect(() => {
    hrProfileApi.getProfile(employee.employee_id).then(r => {
      setPhone(r.data.employee.phone || '')
      const addr = r.data.addresses?.find(a => a.address_type === 'current') || r.data.addresses?.[0]
      if (addr) { setAddressLine1(addr.address_line1 || ''); setCity(addr.city || ''); setState(addr.state || '') }
    }).finally(() => setLoading(false))
  }, [employee.employee_id])

  // Teams are scoped to a department — reload whenever the selected
  // department changes, and clear the team choice if it's no longer valid.
  useEffect(() => {
    if (!departmentId) { setTeams([]); return }
    orgApi.teams(departmentId).then(r => {
      setTeams(r.data)
      if (!r.data.some(t => String(t.team_id) === String(teamId))) setTeamId('')
    }).catch(() => setTeams([]))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [departmentId])

  async function save() {
    setSaving(true); setError('')
    try {
      // Org assignment (department/team/designation/manager) — HR Admin only.
      await orgApi.assignEmployee(employee.employee_id, {
        department_id: departmentId || undefined,
        team_id: teamId || undefined,
        designation_id: designationId || undefined,
        manager_id: managerId || undefined,
      })
      // Direct profile edit (contact/address) — audited automatically.
      await hrProfileApi.editProfile(employee.employee_id, {
        phone: phone || undefined,
        address_line1: addressLine1 || undefined,
        city: city || undefined,
        state: state || undefined,
      })
      onSaved()
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to save changes')
    } finally { setSaving(false) }
  }

  return (
    <Modal open onClose={onClose} title={`Edit ${employee.full_name}`}
      footer={<>
        <button className="btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn-primary" onClick={save} disabled={saving || loading}>
          {saving ? 'Saving…' : 'Save Changes'}
        </button>
      </>}>
      <Alert type="error" message={error} onDismiss={() => setError('')} />
      {loading ? <PageSpinner /> : (
        <div className="space-y-4">
          <FormField label="Manager">
            <select className="input" value={managerId} onChange={e => setManagerId(e.target.value)}>
              <option value="">No manager assigned</option>
              {managers.filter(m => m.employee_id !== employee.employee_id)
                .map(m => (
                  <option key={m.employee_id} value={m.employee_id}>
                    {m.full_name}{m.role !== 'manager' ? ' (will become a manager)' : ''}
                  </option>
                ))}
            </select>
          </FormField>
          <FormField label="Department">
            <select className="input" value={departmentId} onChange={e => setDepartmentId(e.target.value)}>
              <option value="">Unassigned</option>
              {departments.map(d => <option key={d.department_id} value={d.department_id}>{d.department_name}</option>)}
            </select>
          </FormField>
          <FormField label="Team">
            <select className="input" value={teamId} onChange={e => setTeamId(e.target.value)} disabled={!departmentId}>
              <option value="">{departmentId ? 'Unassigned' : 'Select a department first'}</option>
              {teams.map(t => <option key={t.team_id} value={t.team_id}>{t.team_name}</option>)}
            </select>
          </FormField>
          <FormField label="Designation">
            <select className="input" value={designationId} onChange={e => setDesignationId(e.target.value)}>
              <option value="">Unassigned</option>
              {designations.map(d => <option key={d.designation_id} value={d.designation_id}>{d.title}</option>)}
            </select>
          </FormField>
          <FormField label="Phone">
            <input className="input" value={phone} onChange={e => setPhone(e.target.value)} />
          </FormField>
          <FormField label="Address">
            <input className="input mb-2" placeholder="Address line 1" value={addressLine1} onChange={e => setAddressLine1(e.target.value)} />
            <div className="grid grid-cols-2 gap-2">
              <input className="input" placeholder="City" value={city} onChange={e => setCity(e.target.value)} />
              <input className="input" placeholder="State" value={state} onChange={e => setState(e.target.value)} />
            </div>
          </FormField>
          <p className="text-xs text-gray-400">
            Every change here is logged with your name, the old value, and the new value for audit purposes.
          </p>
        </div>
      )}
    </Modal>
  )
}
