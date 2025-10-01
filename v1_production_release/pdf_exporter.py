from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from pathlib import Path
from datetime import datetime

def main(vault_path: str, out_pdf_path: str):
    vp = Path(vault_path)
    op = Path(out_pdf_path)
    op.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(op), pagesize=LETTER)
    w,h = LETTER
    c.setFont("Helvetica-Bold", 16)
    c.drawString(1*inch, h-1*inch, "VaultSeal Receipt")
    c.setFont("Helvetica", 11)
    c.drawString(1*inch, h-1.35*inch, f"Encrypted vault file: {vp.name}")
    c.drawString(1*inch, h-1.6*inch,  f"Location: {vp.resolve()}")
    c.drawString(1*inch, h-1.85*inch, f"Generated: {datetime.utcnow().isoformat(timespec='seconds')}Z")
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(1*inch, 0.9*inch, "Shim exporter — replace with your production renderer anytime.")
    c.showPage(); c.save()
