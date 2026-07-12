import { X, AlertCircle, Info, CheckCircle, AlertTriangle, Inbox } from 'lucide-react'

// ── Spinner ──────────────────────────────────────────────────────────────────
export function Spinner({ size = 'md', className = '' }) {
  const s = { sm: 'w-4 h-4', md: 'w-6 h-6', lg: 'w-10 h-10' }[size]
  return (
    <div className={`${s} border-2 border-brand-200 border-t-brand-600 rounded-full animate-spin ${className}`} />
  )
}

export function PageSpinner() {
  return (
    <div className="flex items-center justify-center h-64">
      <Spinner size="lg" />
    </div>
  )
}

// ── StatusBadge ───────────────────────────────────────────────────────────────
const STATUS_MAP = {
  pending:       'badge-yellow',
  approved:      'badge-green',
  rejected:      'badge-red',
  withdrawn:     'badge-gray',
  cancelled:     'badge-gray',
  open:          'badge-blue',
  in_progress:   'badge-yellow',
  pending_info:  'badge-yellow',
  resolved:      'badge-green',
  closed:        'badge-gray',
  on_hold:       'badge-yellow',
  present:       'badge-green',
  absent:        'badge-red',
  wfh:           'badge-blue',
  on_leave:      'badge-yellow',
  half_day:      'badge-blue',
  holiday:       'badge-gray',
  published:     'badge-green',
  draft:         'badge-gray',
  paid:          'badge-green',
  active:        'badge-green',
  resigned:      'badge-gray',
  terminated:    'badge-red',
}

export function StatusBadge({ status }) {
  const cls = STATUS_MAP[status] || 'badge-gray'
  return <span className={cls}>{status?.replace(/_/g, ' ')}</span>
}

// ── Alert / Error ─────────────────────────────────────────────────────────────
const ALERT_STYLES = {
  error:   { wrap: 'bg-red-50 border-red-200',   icon: <AlertCircle className="w-4 h-4 text-red-500 shrink-0" />,   text: 'text-red-800' },
  warning: { wrap: 'bg-yellow-50 border-yellow-200', icon: <AlertTriangle className="w-4 h-4 text-yellow-500 shrink-0" />, text: 'text-yellow-800' },
  success: { wrap: 'bg-green-50 border-green-200',  icon: <CheckCircle className="w-4 h-4 text-green-500 shrink-0" />,   text: 'text-green-800' },
  info:    { wrap: 'bg-blue-50 border-blue-200',    icon: <Info className="w-4 h-4 text-blue-500 shrink-0" />,           text: 'text-blue-800' },
}

export function Alert({ type = 'info', message, onDismiss }) {
  if (!message) return null
  const s = ALERT_STYLES[type]
  return (
    <div className={`flex items-start gap-2 rounded-lg border p-3 text-sm ${s.wrap}`}>
      {s.icon}
      <span className={`flex-1 ${s.text}`}>{message}</span>
      {onDismiss && (
        <button onClick={onDismiss} className="text-gray-400 hover:text-gray-600">
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  )
}

// ── Modal ─────────────────────────────────────────────────────────────────────
export function Modal({ open, onClose, title, children, footer, wide }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
      <div className={`bg-white rounded-2xl shadow-2xl w-full ${wide ? 'max-w-2xl' : 'max-w-lg'} max-h-[90vh] flex flex-col`}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-900">{title}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">{children}</div>
        {footer && (
          <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100 bg-gray-50 rounded-b-2xl">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}

// ── EmptyState ────────────────────────────────────────────────────────────────
export function EmptyState({ icon, title, description, action }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="text-gray-300 mb-3">{icon || <Inbox className="w-12 h-12" />}</div>
      <p className="text-gray-600 font-medium">{title}</p>
      {description && <p className="text-sm text-gray-400 mt-1 max-w-xs">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

// ── FormField ─────────────────────────────────────────────────────────────────
export function FormField({ label, required, error, children }) {
  return (
    <div>
      {label && (
        <label className="label">
          {label}{required && <span className="text-red-500 ml-0.5">*</span>}
        </label>
      )}
      {children}
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  )
}

// ── Table wrapper ─────────────────────────────────────────────────────────────
export function Table({ headers, children, empty }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-gray-100">
      <table className="w-full divide-y divide-gray-100">
        <thead className="bg-gray-50">
          <tr>{headers.map((h) => <th key={h} className="table-th">{h}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-gray-50 bg-white">
          {children}
        </tbody>
      </table>
      {empty}
    </div>
  )
}

// ── Confirm dialog ────────────────────────────────────────────────────────────
export function Confirm({ open, onClose, onConfirm, title, message, confirmLabel = 'Confirm', danger = false }) {
  return (
    <Modal open={open} onClose={onClose} title={title}
      footer={<>
        <button className="btn-secondary" onClick={onClose}>Cancel</button>
        <button className={danger ? 'btn-danger' : 'btn-primary'} onClick={onConfirm}>{confirmLabel}</button>
      </>}>
      <p className="text-sm text-gray-600">{message}</p>
    </Modal>
  )
}
