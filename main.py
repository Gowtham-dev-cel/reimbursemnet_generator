from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import uuid
import os
import asyncio
from datetime import datetime, timedelta

app = FastAPI()

# In-memory token store with expiry
token_store = {}

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
    submission_date: str
    expenses: List[Expense]
    total_reimbursement_amount: str
    employee_signature: str
    employee_date: str
    manager_signature: str=""
    manager_date: str=""

# --- PDF Generation ---
def generate_reimbursement_pdf(data: ReimbursementRequest, filename="reimbursement_form.pdf"):
    styles = getSampleStyleSheet()
    story = []

    doc = SimpleDocTemplate(filename, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)

    # Title
    story.append(Paragraph("<b>Reimbursement Request Form</b>", styles['Title']))
    story.append(Spacer(1, 12))

    # Employee Info
    employee_info = [
        ["Employee Name:", data.employee_name, "Employee ID:", data.employee_id],
        ["Department:", data.department, "Contact:", data.contact],
        ["Submission Date:", data.submission_date, "", ""]
    ]
    emp_table = Table(employee_info, colWidths=[100, 150, 100, 150])
    emp_table.setStyle(TableStyle([("GRID", (0,0), (-1,-1), 0.5, colors.grey),
                                   ("VALIGN", (0,0), (-1,-1), "MIDDLE")]))
    story.append(emp_table)
    story.append(Spacer(1, 20))

    # Expense Table
    expense_data = [["Date", "Category", "Amount", "Description", "Invoice"]] + \
                   [[e.date, e.category, e.amount, e.description, e.invoice] for e in data.expenses]
    expense_table = Table(expense_data, colWidths=[70, 100, 70, 150, 120])
    expense_table.setStyle(TableStyle([("GRID", (0,0), (-1,-1), 0.5, colors.black),
                                       ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
                                       ("ALIGN", (2,1), (2,-1), "RIGHT"),
                                       ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                                       ("FONTSIZE", (0,0), (-1,-1), 9)]))
    story.append(Paragraph("<b>Expense Details</b>", styles['Heading3']))
    story.append(expense_table)
    story.append(Spacer(1, 20))

    # Summary
    summary = [["Total Reimbursement Amount:", data.total_reimbursement_amount]]
    summary_table = Table(summary, colWidths=[200, 200])
    summary_table.setStyle(TableStyle([("GRID", (0,0), (-1,-1), 0.5, colors.black),
                                       ("BACKGROUND", (0,0), (-1,-1), colors.whitesmoke)]))
    story.append(Paragraph("<b>Summary</b>", styles['Heading3']))
    story.append(summary_table)
    story.append(Spacer(1, 20))

    # Approvals
    approvals = [
        ["Employee Signature:", data.employee_signature, "Date:", data.employee_date],
        ["Manager Signature:", data.manager_signature, "Date:", data.manager_date]
    ]
    approvals_table = Table(approvals, colWidths=[130, 150, 50, 90])
    approvals_table.setStyle(TableStyle([("GRID", (0,0), (-1,-1), 0.5, colors.black),
                                         ("BACKGROUND", (0,0), (-1,-1), colors.whitesmoke)]))
    story.append(Paragraph("<b>Approvals</b>", styles['Heading3']))
    story.append(approvals_table)
    story.append(Spacer(1, 20))

    # Footer
    story.append(Paragraph("<i>Note: Please attach original invoices/receipts for all expenses claimed.</i>", styles['Normal']))

    doc.build(story)
    return filename

# --- Prepare PDF and return token ---
@app.post("/generate-pdf/prepare/")
async def prepare_pdf(request: ReimbursementRequest):
    token = str(uuid.uuid4())
    filename = f"{token}.pdf"
    generate_reimbursement_pdf(request, filename)

    expires_at = datetime.utcnow() + timedelta(minutes=5)
    token_store[token] = {"file": filename, "expires_at": expires_at}
    
    return {"download_url": f"https://reimbursemnet-generator.onrender.com/generate-pdf/download/{token}"}

# --- Download PDF ---
@app.get("/generate-pdf/download/{token}")
async def download_pdf(token: str):
    if token not in token_store:
        raise HTTPException(status_code=404, detail="Invalid or expired token")
    
    entry = token_store[token]
    if datetime.utcnow() > entry["expires_at"]:
        if os.path.exists(entry["file"]):
            os.remove(entry["file"])
        token_store.pop(token)
        raise HTTPException(status_code=410, detail="Token expired")
    
    return FileResponse(entry["file"], media_type="application/pdf", filename="reimbursement_form.pdf")

# --- Background cleanup ---
async def cleanup_expired_files():
    while True:
        now = datetime.utcnow()
        expired_tokens = [t for t, e in token_store.items() if now > e["expires_at"]]
        for t in expired_tokens:
            file_path = token_store[t]["file"]
            if os.path.exists(file_path):
                os.remove(file_path)
            token_store.pop(t)
        await asyncio.sleep(300)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(cleanup_expired_files())
