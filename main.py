from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

app = FastAPI()

# --- Pydantic Models ---
class Expense(BaseModel):
    date: str
    category: str
    amount: str
    description: str
    invoice: str

class ReimbursementRequest(BaseModel):
    employee_name: str
    employee_id: str
    department: str
    contact: str
    expenses: List[Expense]
    total_claimed: str
    advance_taken: str
    net_payable: str
    employee_signature: str
    employee_date: str
    manager_signature: str = ""  # left empty by default
    manager_date: str = ""       # left empty by default

# --- PDF Generation Function ---
def generate_reimbursement_pdf(data: ReimbursementRequest, filename="reimbursement_form.pdf"):
    styles = getSampleStyleSheet()
    story = []

    doc = SimpleDocTemplate(filename, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)

    # Title
    story.append(Paragraph("<b>Reimbursement Request Form</b>", styles['Title']))
    story.append(Spacer(1, 12))

    # Employee Info Table
    employee_info = [
        ["Employee Name:", data.employee_name, "Employee ID:", data.employee_id],
        ["Department:", data.department, "Contact:", data.contact]
    ]
    emp_table = Table(employee_info, colWidths=[100, 150, 100, 150])
    emp_table.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE")
    ]))
    story.append(emp_table)
    story.append(Spacer(1, 20))

    # Expense Table
    expense_data = [["Date", "Category", "Amount", "Description", "Invoice"]] + \
        [[e.date, e.category, e.amount, e.description, e.invoice] for e in data.expenses]
    expense_table = Table(expense_data, colWidths=[70, 100, 70, 150, 120])
    expense_table.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.5, colors.black),
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("ALIGN", (2,1), (2,-1), "RIGHT"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("FONTSIZE", (0,0), (-1,-1), 9)
    ]))
    story.append(Paragraph("<b>Expense Details</b>", styles['Heading3']))
    story.append(expense_table)
    story.append(Spacer(1, 20))

    # Summary Table
    summary = [
        ["Total Claimed:", data.total_claimed],
        ["Advance Taken:", data.advance_taken],
        ["Net Payable:", data.net_payable]
    ]
    summary_table = Table(summary, colWidths=[150, 200])
    summary_table.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.5, colors.black),
        ("BACKGROUND", (0,0), (-1,-1), colors.whitesmoke)
    ]))
    story.append(Paragraph("<b>Summary</b>", styles['Heading3']))
    story.append(summary_table)
    story.append(Spacer(1, 20))

    # Approvals Table (without finance)
    approvals = [
        ["Employee Signature:", data.employee_signature, "Date:", data.employee_date],
        ["Manager Signature:", data.manager_signature, "Date:", data.manager_date]
    ]
    approvals_table = Table(approvals, colWidths=[130, 150, 50, 90])
    approvals_table.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.5, colors.black),
        ("BACKGROUND", (0,0), (-1,-1), colors.whitesmoke)
    ]))
    story.append(Paragraph("<b>Approvals</b>", styles['Heading3']))
    story.append(approvals_table)
    story.append(Spacer(1, 20))

    # Footer Note
    story.append(Paragraph("<i>Note: Please attach original invoices/receipts for all expenses claimed.</i>", styles['Normal']))

    # Build PDF
    doc.build(story)
    return filename

# --- API Endpoint ---
@app.post("/generate-pdf/")
async def create_pdf(request: ReimbursementRequest):
    filename = "reimbursement_form.pdf"
    generate_reimbursement_pdf(request, filename)
    return FileResponse(filename, media_type='application/pdf', filename=filename)
