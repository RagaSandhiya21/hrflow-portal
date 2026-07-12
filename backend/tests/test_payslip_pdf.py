"""Unit tests for app/payslip_pdf.py — PyMuPDF payslip template (Module 3)."""
from datetime import date
from types import SimpleNamespace

import fitz  # PyMuPDF

from app.payslip_pdf import build_payslip_pdf


def _sample_detail(**overrides):
    base = dict(
        employee_name="Rohan Iyer", employee_code="P104",
        designation="Software Engineer", department="Engineering",
        payslip_month=date(2026, 6, 1),
        basic_salary=38000, hra=15200, transport_allowance=1600, medical_allowance=1250,
        special_allowance=0, performance_bonus=0, other_earnings=0, gross_earnings=56050,
        pf_employee=4560, esi_employee=0, professional_tax=200, tds=0,
        loan_deduction=0, loss_of_pay=0, other_deductions=0, total_deductions=4760,
        net_salary=51290, days_worked=22, payroll_status="paid",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_build_payslip_pdf_produces_valid_pdf_bytes():
    detail = _sample_detail()
    pdf_bytes = build_payslip_pdf(detail)
    assert pdf_bytes[:4] == b"%PDF"

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    assert doc.page_count == 1
    text = doc[0].get_text()
    doc.close()

    assert "Rohan Iyer" in text
    assert "P104" in text
    assert "51,290.00" in text  # net salary must appear correctly formatted


def test_build_payslip_pdf_handles_zero_days_worked():
    detail = _sample_detail(days_worked=0)
    pdf_bytes = build_payslip_pdf(detail)
    assert pdf_bytes[:4] == b"%PDF"
