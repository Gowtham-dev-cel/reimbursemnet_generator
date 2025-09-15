from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List,Optional
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import uuid
import os
import asyncio
from datetime import datetime, timedelta
import httpx
import base64

app = FastAPI()

# --- Storage paths ---
PDF_STORAGE = "./pdfs"
os.makedirs(PDF_STORAGE, exist_ok=True)

IMAGE_STORAGE = "./images"
os.makedirs(IMAGE_STORAGE, exist_ok=True)

# --- In-memory token store with expiry ---
token_store = {}  # token: {"file": filename, "expires_at": datetime}

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
    manager_signature: str = ""
    manager_date: str = ""

# --- Invoice Models ---
class CompanyInfo(BaseModel):
    name: str
    address: str
    email: Optional[str] = ""
    phone: Optional[str] = ""

class ClientInfo(BaseModel):
    name: str
    address: str
    email: Optional[str] = ""
    phone: Optional[str] = ""

class InvoiceInfo(BaseModel):
    invoice_number: str
    date: str
    due_date: str

class InvoiceItem(BaseModel):
    description: str
    date: str
    quantity: float
    rate: float
    amount: float

class InvoiceRequest(BaseModel):
    company_info: CompanyInfo
    client_info: ClientInfo
    invoice_info: InvoiceInfo
    items: List[InvoiceItem]
    tax_percent: float = 0
    discount: float = 0
    terms: str = ""
    invoice_type: str = "general"  # time_log, order, project, usage

# --- PDF Generation ---
def generate_reimbursement_pdf(data: ReimbursementRequest, filename: str):
    styles = getSampleStyleSheet()
    link_style = ParagraphStyle(
        name="LinkStyle",
        fontSize=9,
        textColor="blue",
        underline=True
    )
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
    expense_data = [["Date", "Category", "Amount", "Description", "Invoice"]]
    for e in data.expenses:
        invoice_cell = Paragraph(f'<link href="{e.invoice}">View Invoice</link>', link_style)
        expense_data.append([e.date, e.category, e.amount, e.description, invoice_cell])
    expense_table = Table(expense_data, colWidths=[70, 100, 70, 150, 120])
    expense_table.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.5, colors.black),
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("ALIGN", (2,1), (2,-1), "RIGHT"),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("FONTSIZE", (0,0), (-1,-1), 9)
    ]))
    story.append(Paragraph("<b>Expense Details</b>", styles['Heading3']))
    story.append(expense_table)
    story.append(Spacer(1, 20))

    # Summary
    summary = [["Total Reimbursement Amount:", data.total_reimbursement_amount]]
    summary_table = Table(summary, colWidths=[200, 200])
    summary_table.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.5, colors.black),
        ("BACKGROUND", (0,0), (-1,-1), colors.whitesmoke)
    ]))
    story.append(Paragraph("<b>Summary</b>", styles['Heading3']))
    story.append(summary_table)
    story.append(Spacer(1, 20))

    # Approvals
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

    story.append(Paragraph("<i>Note: Please attach original invoices/receipts for all expenses claimed.</i>", styles['Normal']))
    doc.build(story)
    return filename

# --- Updated generate_invoice_pdf ---
def generate_invoice_pdf(data: InvoiceRequest, filename: str):
    styles = getSampleStyleSheet()
    if "InvoiceTitle" not in styles:
        styles.add(ParagraphStyle(name='InvoiceTitle', fontSize=18, leading=22, spaceAfter=10, alignment=1))
    if "InvoiceHeading" not in styles:
        styles.add(ParagraphStyle(name='InvoiceHeading', fontSize=12, leading=14, spaceAfter=6))

    story = []
    doc = SimpleDocTemplate(filename, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)

    # --- Title ---
    story.append(Paragraph(f"<b>{data.invoice_type.capitalize()} Invoice</b>", styles['InvoiceTitle']))
    story.append(Spacer(1, 12))

    # --- Company Info ---
    story.append(Paragraph("<b>From:</b>", styles['Heading3']))
    story.append(Paragraph(data.company_info.name, styles['Normal']))
    story.append(Paragraph(data.company_info.address, styles['Normal']))
    if data.company_info.email:
        story.append(Paragraph(f"Email: {data.company_info.email}", styles['Normal']))
    if data.company_info.phone:
        story.append(Paragraph(f"Phone: {data.company_info.phone}", styles['Normal']))
    story.append(Spacer(1, 6))

    # --- Client Info ---
    story.append(Paragraph("<b>To:</b>", styles['Heading3']))
    story.append(Paragraph(data.client_info.name, styles['Normal']))
    story.append(Paragraph(data.client_info.address, styles['Normal']))
    if data.client_info.email:
        story.append(Paragraph(f"Email: {data.client_info.email}", styles['Normal']))
    if data.client_info.phone:
        story.append(Paragraph(f"Phone: {data.client_info.phone}", styles['Normal']))
    story.append(Spacer(1, 12))

    # --- Invoice Info ---
    story.append(Paragraph(f"Invoice #: {data.invoice_info.invoice_number}", styles['Normal']))
    story.append(Paragraph(f"Date: {data.invoice_info.date}", styles['Normal']))
    story.append(Paragraph(f"Due Date: {data.invoice_info.due_date}", styles['Normal']))
    story.append(Spacer(1, 12))

    # --- Items Table ---
    column_map = {
        "time_log": ["#", "Task/Description", "Date", "Hours", "Rate / Hour", "Amount"],
        "order": ["#", "Item", "Date", "Quantity", "Rate / Unit", "Amount"],
        "project": ["#", "Deliverable", "Date", "Units", "Rate", "Amount"],
        "usage": ["#", "Service/Metric", "Date", "Units Used", "Rate / Unit", "Amount"]
    }
    headers = column_map.get(data.invoice_type, ["#", "Description", "Date", "Quantity", "Rate", "Amount"])
    table_data = [headers]

    for i, item in enumerate(data.items, start=1):
        table_data.append([
            str(i),
            item.description,
            item.date,
            str(item.quantity),
            f"${item.rate:.2f}",
            f"${item.amount:.2f}"
        ])

    # --- Summary Calculations ---
    subtotal = sum(item.amount for item in data.items)
    tax = subtotal * data.tax_percent / 100
    discount = data.discount
    total = subtotal + tax - discount

    # --- Add summary rows ---
    table_data.extend([
        ["", "", "", "", "Subtotal", f"${subtotal:.2f}"],
        ["", "", "", "", f"Tax ({data.tax_percent}%)", f"${tax:.2f}"],
        ["", "", "", "", "Discount", f"${discount:.2f}"],
        ["", "", "", "", "Total Due", f"${total:.2f}"]
    ])

    invoice_table = Table(table_data, colWidths=[30, 180, 70, 70, 70, 70])
    invoice_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f2f2f2')),
        ('ALIGN',(3,1),(-1,-1),'CENTER'),
        ('ALIGN',(-2,-4),(-1,-1),'RIGHT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold')
    ]))
    story.append(invoice_table)
    story.append(Spacer(1, 20))

    # --- Terms & Notes ---
    story.append(Paragraph("<b>Terms & Notes</b>", styles['InvoiceHeading']))
    story.append(Paragraph(data.terms, styles['Normal']))

    # --- Build PDF ---
    doc.build(story)
    return filename

# --- API Endpoints ---
@app.post("/generate-pdf/prepare/")
async def prepare_pdf(request: ReimbursementRequest):
    token = str(uuid.uuid4())
    filename = os.path.join(PDF_STORAGE, f"{token}.pdf")
    generate_reimbursement_pdf(request, filename)
    token_store[token] = {"file": filename, "expires_at": datetime.utcnow() + timedelta(minutes=5)}
    return {"download_url": f"https://reimbursemnet-generator.onrender.com/generate-pdf/download/{token}"}

@app.get("/generate-pdf/download/{token}")
async def download_pdf(token: str):
    entry = token_store.get(token)
    if not entry or not os.path.exists(entry["file"]):
        raise HTTPException(status_code=404, detail="Invalid or expired token")
    if datetime.utcnow() > entry["expires_at"]:
        os.remove(entry["file"])
        token_store.pop(token)
        raise HTTPException(status_code=410, detail="Token expired")
    return FileResponse(entry["file"], media_type="application/pdf", filename="reimbursement_form.pdf")

@app.post("/invoice/create/")
async def create_invoice(request: InvoiceRequest):
    token = str(uuid.uuid4())
    filename = os.path.join(PDF_STORAGE, f"{token}.pdf")
    generate_invoice_pdf(request, filename)
    token_store[token] = {"file": filename, "expires_at": datetime.utcnow() + timedelta(minutes=10)}
    return {"download_url": f"https://reimbursemnet-generator.onrender.com/invoice/download/{token}"}

@app.get("/invoice/download/{token}")
async def download_invoice(token: str):
    entry = token_store.get(token)
    if not entry or not os.path.exists(entry["file"]):
        raise HTTPException(status_code=404, detail="Invalid or expired token")
    if datetime.utcnow() > entry["expires_at"]:
        os.remove(entry["file"])
        token_store.pop(token)
        raise HTTPException(status_code=410, detail="Token expired")
    return FileResponse(entry["file"], media_type="application/pdf", filename="invoice.pdf")


STABILITY_API_KEY = "sk-szp0aWoLoCC4NSnHD4teIcqQm694jKfDtb2MwmVNsYusziWX"
STABILITY_URL = "https://api.stability.ai/v2beta/stable-image/generate/core"

class ImageRequest(BaseModel):
    prompt: str
    output_format: str = "png"

@app.post("/image/generate/")
async def generate_image(
    prompt: str = Form(...),
    output_format: str = Form("png")
):
    headers = {
        "Authorization": f"Bearer {STABILITY_API_KEY}",
        "Accept": "application/json"
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            STABILITY_URL,
            headers=headers,
            files={
                "prompt": (None, prompt),
                "output_format": (None, output_format)
            }
        )
        resp.raise_for_status()
        data = resp.json()

    if "artifacts" not in data or len(data["artifacts"]) == 0:
        raise HTTPException(status_code=500, detail="Image not returned")

    image_b64 = data["artifacts"][0]["base64"]
    image_bytes = base64.b64decode(image_b64)

    token = str(uuid.uuid4())
    filename = os.path.join(IMAGE_STORAGE, f"{token}.png")
    with open(filename, "wb") as f:
        f.write(image_bytes)

    token_store[token] = {"file": filename, "expires_at": datetime.utcnow() + timedelta(minutes=5)}
    return {"download_url": f"https://reimbursemnet-generator.onrender.com/image/download/{token}"}

@app.get("/image/download/{token}")
async def download_image(token: str):
    entry = token_store.get(token)
    if not entry or not os.path.exists(entry["file"]):
        raise HTTPException(status_code=404, detail="Invalid or expired token")

    if datetime.utcnow() > entry["expires_at"]:
        os.remove(entry["file"])
        token_store.pop(token)
        raise HTTPException(status_code=410, detail="Token expired")

    return FileResponse(entry["file"], media_type="image/png", filename="generated.png")


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
