import api from './client'

// ── Auth ─────────────────────────────────────────────────────────────────────
export const authApi = {
  login:    (email)   => api.post('/auth/login', { email }),           // dev-only mock SSO
  ssoLogin: (idToken) => api.post('/auth/sso/entra', { id_token: idToken }), // real Entra ID SSO
  me:       ()        => api.get('/auth/me'),
  adminAccountLog: (employeeId) => api.get(`/auth/admin-account-log/${employeeId}`),
}

// ── Dashboard ─────────────────────────────────────────────────────────────────
export const dashboardApi = {
  summary: () => api.get('/dashboard/summary'),
}

// ── Leave ─────────────────────────────────────────────────────────────────────
export const leaveApi = {
  types:        ()           => api.get('/leave/types'),
  balances:     (year)       => api.get('/leave/balances', { params: { year } }),
  myRequests:   ()           => api.get('/leave/requests'),
  teamRequests: ()           => api.get('/leave/requests/team'),
  apply:        (data)       => api.post('/leave/requests', data),
  decide:       (id, data)   => api.post(`/leave/requests/${id}/decision`, data),
  withdraw:     (id)         => api.delete(`/leave/requests/${id}`),
}

// ── Payslips ──────────────────────────────────────────────────────────────────
export const payslipApi = {
  list:    (employeeId) => api.get('/payslips', { params: employeeId ? { employee_id: employeeId } : {} }),
  detail:  (id)         => api.get(`/payslips/${id}`),
  pdfUrl:  (id)         => `${api.defaults.baseURL}/payslips/${id}/pdf`,
  publish: (id)         => api.post(`/payslips/${id}/publish`),
}

// ── Profile ───────────────────────────────────────────────────────────────────
export const profileApi = {
  me:                    ()       => api.get('/profile/me'),
  updateContact:         (data)   => api.put('/profile/me/contact', data),
  upsertAddress:         (data)   => api.put('/profile/me/address', data),
  addEmergencyContact:   (data)   => api.post('/profile/me/emergency-contacts', data),
  updateEmergencyContact:(id, d)  => api.put(`/profile/me/emergency-contacts/${id}`, d),
  deleteEmergencyContact:(id)     => api.delete(`/profile/me/emergency-contacts/${id}`),
  submitChangeRequest:   (data)   => api.post('/profile/change-requests', data),
  myChangeRequests:      ()       => api.get('/profile/change-requests'),
  pendingChangeRequests: ()       => api.get('/profile/change-requests/pending'),
  decideChangeRequest:   (id, d)  => api.post(`/profile/change-requests/${id}/decision`, d),
}

// ── HR Requests ───────────────────────────────────────────────────────────────
export const hrRequestApi = {
  categories:   ()          => api.get('/hr-requests/categories'),
  myRequests:   ()          => api.get('/hr-requests'),
  queue:        ()          => api.get('/hr-requests/queue'),
  raise:        (data)      => api.post('/hr-requests', data),
  updateStatus: (id, data)  => api.patch(`/hr-requests/${id}/status`, data),
  comments:     (id)        => api.get(`/hr-requests/${id}/comments`),
  addComment:   (id, data)  => api.post(`/hr-requests/${id}/comments`, data),
}

// ── Attendance ────────────────────────────────────────────────────────────────
export const attendanceApi = {
  myRecords:         (year, month) => api.get('/attendance/me', { params: { year, month } }),
  summary:           (year, month) => api.get('/attendance/summary', { params: { year, month } }),
  regularise:        (data)        => api.post('/attendance/regularisation', data),
  myRegularisations: ()            => api.get('/attendance/regularisation'),
  regQueue:          ()            => api.get('/attendance/regularisation/queue'),
  decideReg:         (id, data)    => api.post(`/attendance/regularisation/${id}/decision`, data),
}

// ── Holidays ──────────────────────────────────────────────────────────────────
export const holidayApi = {
  list:   (year) => api.get('/attendance/holidays', { params: { year } }),
  add:    (data) => api.post('/attendance/holidays', data),
  delete: (id)   => api.delete(`/attendance/holidays/${id}`),
}

// ── IT Requests ───────────────────────────────────────────────────────────────
export const itRequestApi = {
  myRequests:   ()          => api.get('/it-requests'),
  queue:        ()          => api.get('/it-requests/queue'),
  raise:        (data)      => api.post('/it-requests', data),
  updateStatus: (id, data)  => api.patch(`/it-requests/${id}/status`, data),
}

// ── Chatbot ───────────────────────────────────────────────────────────────────
export const chatbotApi = {
  policyDocs:          ()            => api.get('/chatbot/policy-docs'),
  deletePolicyDoc:     (id)          => api.delete(`/chatbot/policy-docs/${id}`),
  query:               (data)        => api.post('/chatbot/query', data),
  escalate:            (data)        => api.post('/chatbot/escalate', data),
  myEscalations:       ()            => api.get('/chatbot/escalations/mine'),
  escalationQueue:     ()            => api.get('/chatbot/escalations/queue'),
  respondToEscalation: (id, formData)=> api.post(`/chatbot/escalations/${id}/respond`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  resolveEscalation:   (id, notes)   => api.post(`/chatbot/escalations/${id}/resolve`, null, { params: { notes } }),
}

// ── Notifications ─────────────────────────────────────────────────────────────
export const notificationsApi = {
  list:     (unreadOnly) => api.get('/notifications', { params: { unread_only: unreadOnly } }),
  markRead: (id)         => api.post(`/notifications/${id}/read`),
}

// ── Org hierarchy / employee directory (HR Admin) ───────────────────────────────
export const orgApi = {
  searchEmployees:    (q) => api.get('/org/employees', { params: { q } }),
  managers:           ()  => api.get('/org/managers'),
  deactivateEmployee: (employeeId) => api.delete(`/org/employees/${employeeId}`),

  departments:        ()  => api.get('/org/departments'),
  createDepartment:   (body) => api.post('/org/departments', body),
  updateDepartment:   (id, body) => api.put(`/org/departments/${id}`, body),
  deleteDepartment:   (id) => api.delete(`/org/departments/${id}`),

  teams:              (departmentId) => api.get('/org/teams', { params: { department_id: departmentId } }),
  createTeam:         (body) => api.post('/org/teams', body),
  updateTeam:         (id, body) => api.put(`/org/teams/${id}`, body),
  deleteTeam:         (id) => api.delete(`/org/teams/${id}`),

  designations:       ()  => api.get('/org/designations'),
  createDesignation:  (body) => api.post('/org/designations', body),
  updateDesignation:  (id, body) => api.put(`/org/designations/${id}`, body),
  deleteDesignation:  (id) => api.delete(`/org/designations/${id}`),

  assignEmployee:     (employeeId, params) => api.put(`/org/employees/${employeeId}/assignment`, null, { params }),
}

// ── HR Admin: employee profile management ───────────────────────────────────────
export const hrProfileApi = {
  getProfile:  (employeeId)        => api.get(`/profile/${employeeId}`),
  editProfile: (employeeId, body)  => api.put(`/profile/${employeeId}/hr-edit`, body),
}
