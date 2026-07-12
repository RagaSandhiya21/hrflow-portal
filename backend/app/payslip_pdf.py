"""
Payslip PDF generation - PyMuPDF (fitz), per Module 3 of the proposal:
"PDF payslip dynamically generated on-demand per employee per month using a
stored template and PyMuPDF."

Risk mitigation #4 in the proposal calls for "a template with fixed
coordinate regions" - that's exactly what this is: a single-page A4 layout
with the header, earnings table, deductions table, and net-salary line all
drawn at fixed (x, y) coordinates via fitz's low-level text/shape drawing
API, so the same template renders consistently for every employee/month.
"""
from __future__ import annotations

import io

import fitz  # PyMuPDF

PAGE_WIDTH, PAGE_HEIGHT = fitz.paper_size("a4")
MARGIN_X = 40
BRAND = (0x1F / 255, 0x5C / 255, 0x5C / 255)
GRID = (0.85, 0.87, 0.87)
LIGHT_BG = (0.93, 0.97, 0.97)
BLACK = (0, 0, 0)


def _fmt(n) -> str:
    return f"{float(n):,.2f}"


def _draw_table(page: "fitz.Page", top: float, title: str, rows: list[tuple[str, str]],
                 total_label: str) -> float:
    col1_w, col2_w = 340, 120
    row_h = 20
    x0 = MARGIN_X
    x1 = x0 + col1_w + col2_w

    # Header row
    header_rect = fitz.Rect(x0, top, x1, top + row_h)
    page.draw_rect(header_rect, color=BRAND, fill=BRAND)
    page.insert_text((x0 + 6, top + 14), title, fontsize=10, fontname="helv", color=(1, 1, 1))
    page.insert_text((x0 + col1_w + 6, top + 14), "Amount (INR)", fontsize=10, fontname="helv", color=(1, 1, 1))

    y = top + row_h
    for label, value in rows[:-1]:
        row_rect = fitz.Rect(x0, y, x1, y + row_h)
        page.draw_rect(row_rect, color=GRID)
        page.insert_text((x0 + 6, y + 14), label, fontsize=9.5, fontname="helv", color=BLACK)
        page.insert_text((x0 + col1_w + 6, y + 14), value, fontsize=9.5, fontname="helv", color=BLACK)
        y += row_h

    # Total row (bold-ish, shaded)
    total_label_text, total_value = rows[-1]
    total_rect = fitz.Rect(x0, y, x1, y + row_h)
    page.draw_rect(total_rect, color=GRID, fill=LIGHT_BG)
    page.insert_text((x0 + 6, y + 14), total_label_text, fontsize=9.5, fontname="hebo", color=BLACK)
    page.insert_text((x0 + col1_w + 6, y + 14), total_value, fontsize=9.5, fontname="hebo", color=BLACK)
    y += row_h

    return y


def build_payslip_pdf(detail) -> bytes:
    """
    `detail` is a PayslipDetail (see schemas.py) - a plain object/Pydantic
    model with employee_name, employee_code, designation, department,
    payslip_month, and every earnings/deduction/net_salary field.
    """
    doc = fitz.open()
    page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)

    month_str = detail.payslip_month.strftime("%B %Y") if detail.payslip_month else ""

    # -- Header --------------------------------------------------------
    page.draw_rect(fitz.Rect(0, 0, PAGE_WIDTH, 70), color=BRAND, fill=BRAND)
    page.insert_text((MARGIN_X, 30), "HRFlow — Payslip", fontsize=18, fontname="hebo", color=(1, 1, 1))
    page.insert_text((MARGIN_X, 50), f"Pay Period: {month_str}", fontsize=10, fontname="helv", color=(1, 1, 1))

    y = 90
    page.insert_text((MARGIN_X, y), f"{detail.employee_name}  ({detail.employee_code})",
                      fontsize=11, fontname="hebo", color=BLACK)
    y += 16
    page.insert_text((MARGIN_X, y), f"{detail.designation or '—'}   |   {detail.department or '—'}",
                      fontsize=9.5, fontname="helv", color=(0.3, 0.3, 0.3))
    y += 26

    # -- Earnings table --------------------------------------------------
    earnings_rows = [
        ("Basic Salary",        _fmt(detail.basic_salary)),
        ("HRA",                 _fmt(detail.hra)),
        ("Transport Allowance", _fmt(detail.transport_allowance)),
        ("Medical Allowance",   _fmt(detail.medical_allowance)),
        ("Special Allowance",   _fmt(detail.special_allowance)),
        ("Performance Bonus",   _fmt(detail.performance_bonus)),
        ("Other Earnings",      _fmt(detail.other_earnings)),
        ("Gross Earnings",      _fmt(detail.gross_earnings)),
    ]
    y = _draw_table(page, y, "Earnings", earnings_rows, "Gross Earnings") + 14

    # -- Deductions table --------------------------------------------------
    deduction_rows = [
        ("Provident Fund (Employee)", _fmt(detail.pf_employee)),
        ("ESI (Employee)",            _fmt(detail.esi_employee)),
        ("Professional Tax",          _fmt(detail.professional_tax)),
        ("TDS",                       _fmt(detail.tds)),
        ("Loan Deduction",            _fmt(detail.loan_deduction)),
        ("Loss of Pay",               _fmt(detail.loss_of_pay)),
        ("Other Deductions",          _fmt(detail.other_deductions)),
        ("Total Deductions",          _fmt(detail.total_deductions)),
    ]
    y = _draw_table(page, y, "Deductions", deduction_rows, "Total Deductions") + 20

    # -- Net salary --------------------------------------------------
    page.insert_text((MARGIN_X, y), f"Net Salary: INR {_fmt(detail.net_salary)}",
                      fontsize=13, fontname="hebo", color=BRAND)
    y += 20
    if detail.days_worked:
        page.insert_text((MARGIN_X, y), f"Days worked: {detail.days_worked}", fontsize=9.5, color=BLACK)
        y += 18

    y += 20
    page.insert_text((MARGIN_X, y), "This is a system-generated payslip and does not require a signature.",
                      fontsize=8, fontname="heit", color=(0.45, 0.45, 0.45))

    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    buf.seek(0)
    return buf.read()
