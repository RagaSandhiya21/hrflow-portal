import { useState, useEffect } from 'react'
import { format, parseISO } from 'date-fns'
import { Download, Eye } from 'lucide-react'
import { payslipApi } from '../../api/services'
import { PageSpinner, EmptyState, Alert } from '../../components/ui'

export default function PayslipsPage() {
  const [payslips, setPayslips] = useState([])
  const [loading, setLoading]   = useState(true)
  const [selected, setSelected] = useState(null)
  const [detail, setDetail]     = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError]       = useState('')
  const [downloading, setDownloading] = useState(null)

  useEffect(() => {
    payslipApi.list().then(r => setPayslips(r.data)).finally(() => setLoading(false))
  }, [])

  async function viewPayslip(p) {
    if (selected?.payslip_id === p.payslip_id) {
      setSelected(null); setDetail(null); return
    }
    setSelected(p); setDetailLoading(true); setDetail(null)
    try {
      const r = await payslipApi.detail(p.payslip_id)
      setDetail(r.data)
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to load payslip')
    } finally { setDetailLoading(false) }
  }

  async function downloadPDF(payslip_id, payslip_month) {
    setDownloading(payslip_id)
    setError('')
    try {
      const token = localStorage.getItem('hrflow_token')
      if (!token) throw new Error('Not authenticated')

      const response = await fetch(`/api/payslips/${payslip_id}/pdf`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      })

      if (!response.ok) {
        const text = await response.text()
        throw new Error(`Download failed: ${response.status} ${text}`)
      }

      const contentType = response.headers.get('content-type')
      if (!contentType || !contentType.includes('pdf')) {
        throw new Error('Server did not return a PDF')
      }

      const blob = await response.blob()
      if (blob.size < 100) throw new Error('PDF file is empty')

      const url = URL.createObjectURL(blob)
      const a   = document.createElement('a')
      const monthStr = payslip_month
        ? format(parseISO(payslip_month), 'MMM_yyyy')
        : payslip_id
      a.href     = url
      a.download = `payslip_${monthStr}.pdf`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (e) {
      setError(e.message || 'PDF download failed')
    } finally {
      setDownloading(null)
    }
  }

  if (loading) return <PageSpinner />

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Payslips</h1>

      <Alert type="error" message={error} onDismiss={() => setError('')} />

      {payslips.length === 0
        ? <EmptyState
            title="No payslips yet"
            description="Payslips are published by HR after monthly payroll is processed."
          />
        : (
          <div className="space-y-3">
            {payslips.map((p) => (
              <div key={p.payslip_id} className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
                <div className="flex items-center justify-between px-5 py-4">
                  <div className="flex items-center gap-4">
                    <div>
                      <p className="font-semibold text-gray-900">
                        {format(parseISO(p.payslip_month), 'MMMM yyyy')}
                      </p>
                      <p className="text-xs text-gray-400 mt-0.5">Payslip #{p.payslip_id}</p>
                    </div>
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium
                      ${p.is_published ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'}`}>
                      {p.is_published ? 'Published' : 'Draft'}
                    </span>
                  </div>

                  {p.is_published && (
                    <div className="flex gap-2">
                      <button
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-300 bg-white text-gray-700 text-xs font-medium hover:bg-gray-50 transition-colors"
                        onClick={() => viewPayslip(p)}>
                        <Eye className="w-3.5 h-3.5" />
                        {selected?.payslip_id === p.payslip_id ? 'Close' : 'View'}
                      </button>
                      <button
                        className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors
                          ${downloading === p.payslip_id
                            ? 'bg-gray-200 text-gray-500 cursor-wait'
                            : 'bg-brand-600 text-white hover:bg-brand-700'}`}
                        onClick={() => downloadPDF(p.payslip_id, p.payslip_month)}
                        disabled={downloading === p.payslip_id}>
                        <Download className="w-3.5 h-3.5" />
                        {downloading === p.payslip_id ? 'Downloading…' : 'Download PDF'}
                      </button>
                    </div>
                  )}
                </div>

                {/* Inline detail */}
                {selected?.payslip_id === p.payslip_id && (
                  <div className="border-t border-gray-100 px-5 py-4 bg-gray-50">
                    {detailLoading
                      ? <p className="text-sm text-gray-400">Loading…</p>
                      : detail && <PayslipDetail data={detail} />
                    }
                  </div>
                )}
              </div>
            ))}
          </div>
        )
      }
    </div>
  )
}

function PayslipDetail({ data }) {
  const fmt = (n) =>
    `₹ ${Number(n).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`

  const Row = ({ label, value, bold }) => (
    <tr className={bold ? 'bg-brand-50' : 'hover:bg-gray-50'}>
      <td className={`py-2 px-3 text-sm ${bold ? 'font-semibold text-gray-900' : 'text-gray-600'}`}>
        {label}
      </td>
      <td className={`py-2 px-3 text-sm text-right ${bold ? 'font-semibold text-gray-900' : 'text-gray-800'}`}>
        {fmt(value)}
      </td>
    </tr>
  )

  return (
    <div>
      <div className="flex gap-6 text-sm text-gray-600 mb-4 flex-wrap">
        <span><strong>Employee:</strong> {data.employee_name} ({data.employee_code})</span>
        {data.designation && <span><strong>Designation:</strong> {data.designation}</span>}
        {data.department  && <span><strong>Department:</strong>  {data.department}</span>}
        {data.days_worked && <span><strong>Days worked:</strong> {data.days_worked}</span>}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Earnings */}
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase mb-1">Earnings</p>
          <table className="w-full text-sm border border-gray-100 rounded-lg overflow-hidden">
            <tbody>
              <Row label="Basic Salary"        value={data.basic_salary} />
              <Row label="HRA"                  value={data.hra} />
              <Row label="Transport Allowance"  value={data.transport_allowance} />
              <Row label="Medical Allowance"    value={data.medical_allowance} />
              <Row label="Special Allowance"    value={data.special_allowance} />
              <Row label="Performance Bonus"    value={data.performance_bonus} />
              <Row label="Other Earnings"       value={data.other_earnings} />
              <Row label="Gross Earnings"       value={data.gross_earnings} bold />
            </tbody>
          </table>
        </div>

        {/* Deductions */}
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase mb-1">Deductions</p>
          <table className="w-full text-sm border border-gray-100 rounded-lg overflow-hidden">
            <tbody>
              <Row label="Provident Fund (Employee)" value={data.pf_employee} />
              <Row label="ESI (Employee)"             value={data.esi_employee} />
              <Row label="Professional Tax"           value={data.professional_tax} />
              <Row label="TDS"                        value={data.tds} />
              <Row label="Loan Deduction"             value={data.loan_deduction} />
              <Row label="Loss of Pay"                value={data.loss_of_pay} />
              <Row label="Other Deductions"           value={data.other_deductions} />
              <Row label="Total Deductions"           value={data.total_deductions} bold />
            </tbody>
          </table>
        </div>
      </div>

      {/* Net salary */}
      <div className="mt-4 flex justify-end">
        <div className="bg-brand-600 text-white rounded-xl px-6 py-3">
          <span className="text-sm opacity-80">Net Salary</span>
          <p className="text-2xl font-bold">
            ₹ {Number(data.net_salary).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </p>
        </div>
      </div>
    </div>
  )
}
