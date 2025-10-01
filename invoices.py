from pydantic import BaseModel, field_validator
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import qrcode
from io import BytesIO
from pathlib import Path

class Invoice(BaseModel):
    invoice_id: str
    issued_at: datetime
    due_at: datetime
    seller_name: str
    seller_account: str
    buyer_name: str
    buyer_email: str
    amount_usd: Decimal
    rl_usd_amount: Decimal
    memo: str = ""

    @field_validator("amount_usd", "rl_usd_amount", mode="before")
    @classmethod
    def as_decimal(cls, v):
        return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def usd_to_rlusd(usd: Decimal) -> Decimal:
    return usd.quantize(Decimal("0.01"))

def make_qr(data: str) -> BytesIO:
    img = qrcode.make(data)
    bio = BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio

def save_invoice_pdf(invoice: Invoice, qr_png: BytesIO, out_path: Path):
    from reportlab.lib.pagesizes import LETTER
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import inch
    from reportlab.lib.utils import ImageReader
    out_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(out_path), pagesize=LETTER)
    w, h = LETTER
    c.setFont("Helvetica-Bold", 16); c.drawString(1*inch, h-1*inch, f"Invoice #{invoice.invoice_id}")
    c.setFont("Helvetica", 10)
    c.drawString(1*inch, h-1.25*inch, f"Issued: {invoice.issued_at.isoformat(timespec='seconds')}")
    c.drawString(1*inch, h-1.45*inch, f"Due:    {invoice.due_at.isoformat(timespec='seconds')}")
    c.setFont("Helvetica-Bold", 12); c.drawString(1*inch, h-1.9*inch, "Bill To")
    c.setFont("Helvetica", 10); c.drawString(1*inch, h-2.1*inch, f"{invoice.buyer_name}  <{invoice.buyer_email}>")
    c.setFont("Helvetica-Bold", 12); c.drawString(1*inch, h-2.6*inch, "From")
    c.setFont("Helvetica", 10); c.drawString(1*inch, h-2.8*inch, f"{invoice.seller_name}  ({invoice.seller_account})")
    c.setFont("Helvetica-Bold", 12); c.drawString(1*inch, h-3.3*inch, "Amount")
    c.setFont("Helvetica", 11); c.drawString(1*inch, h-3.55*inch, f"${invoice.amount_usd} USD  →  {invoice.rl_usd_amount} RLUSD")
    c.setFont("Helvetica", 10); c.drawString(1*inch, h-4.0*inch, f"Memo: {invoice.memo}")
    qr_img = ImageReader(qr_png)
    c.drawImage(qr_img, w-2.25*inch, h-2.25*inch, 1.5*inch, 1.5*inch, preserveAspectRatio=True, mask="auto")
    c.setFont("Helvetica", 8); c.drawString(w-2.25*inch, h-2.35*inch, "Scan to pay")
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(1*inch, 0.75*inch, "VaultSeal™ audit receipt on payment. Hash will be anchored to XRPL.")
    c.showPage(); c.save()
