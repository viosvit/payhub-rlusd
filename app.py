# app.py — PayHub (RLUSD invoicing + demo send + VaultSeal receipt)
import sys
from pathlib import Path

# Add core path (do not modify core files)
for p in ("./v1_production_release", "../v1_production_release"):
    cp = (Path(__file__).resolve().parent / p).resolve()
    if cp.exists() and str(cp) not in sys.path:
        sys.path.insert(0, str(cp))

import streamlit as st
from datetime import datetime, timedelta, timezone
from decimal import Decimal

# TOML loader (Py 3.11+)
try:
    import tomllib as tomli
except ModuleNotFoundError:
    import tomli  # type: ignore

from invoices import Invoice, usd_to_rlusd, make_qr, save_invoice_pdf
from xrpl_client import XRPLClient, XRPLConfig
from vaultseal_receipt import make_receipt_vault, write_encrypted_vault, export_pdf
from qb_export import write_qb_csv


# ---------- Config ----------
CONFIG = tomli.loads(Path("settings.toml").read_text())

def _resolve_network_url(val: str) -> str:
    v = (val or "").strip().lower()
    if v.startswith("http"):
        return val
    if v in ("testnet", "xrpl-testnet"):
        return "https://s.altnet.rippletest.net:51234/"
    if v in ("mainnet", "xrpl-mainnet", "main"):
        return "https://s1.ripple.com:51234/"
    # fallback to testnet
    return "https://s.altnet.rippletest.net:51234/"

network_url = _resolve_network_url(CONFIG.get("xrpl", {}).get("network", "testnet"))
seed        = CONFIG["xrpl"]["seed"]
account     = CONFIG["xrpl"]["account"]
rlusd_cfg   = CONFIG.get("rlusd", {})
demo_mode   = (CONFIG.get("app", {}).get("env", "dev").lower() == "dev")

# ---------- App chrome ----------
st.set_page_config(page_title="PayHub • RLUSD Invoicing", layout="centered")
st.title("PayHub — USD Invoicing with Instant RLUSD Settlement")

# ---------- XRPL client ----------
xrpl = XRPLClient(XRPLConfig(
    network_url=network_url,
    seed=seed,
    account=account,
    demo_mode=demo_mode,
))

with st.sidebar:
    st.subheader("XRPL Status")
    st.write("Node:", network_url)
    st.write("Account:", xrpl.wallet.classic_address)
    if xrpl.ping():
    st.success("Node OK")
else:
    st.error("Node unreachable")

# ---------- Invoice form ----------
st.subheader("Create Invoice")
col1, col2 = st.columns(2)
with col1:
    buyer_name  = st.text_input("Buyer Name", "Acme LLC")
    buyer_email = st.text_input("Buyer Email", "billing@acme.com")
    amount_usd  = st.number_input("Amount (USD)", min_value=0.01, value=100.00, step=1.00, format="%.2f")
    memo        = st.text_input("Memo (optional)", "Web design services")
with col2:
    seller_name    = st.text_input("Your Business Name", CONFIG.get("branding", {}).get("company_name", "YourCo LLC"))
    seller_account = st.text_input("Your XRPL Account (r...)", xrpl.wallet.classic_address)
    days_due       = st.number_input("Net Days", min_value=1, value=7, step=1)

invoice_id = f"INV-{int(datetime.now(timezone.utc).timestamp())}"

if st.button("Generate Invoice"):
    inv = Invoice(
        invoice_id=invoice_id,
        issued_at=datetime.now(timezone.utc),
        due_at=datetime.now(timezone.utc) + timedelta(days=int(days_due)),
        seller_name=seller_name,
        seller_account=seller_account,
        buyer_name=buyer_name,
        buyer_email=buyer_email,
        amount_usd=Decimal(str(amount_usd)),
        rl_usd_amount=usd_to_rlusd(Decimal(str(amount_usd))),
        memo=memo,
    )
    st.session_state["invoice"] = inv

# ---------- Generated invoice ----------
if "invoice" in st.session_state:
    inv: Invoice = st.session_state["invoice"]

    # Demo pay URI (for QR)
    pay_uri = f"xrpl:{inv.seller_account}?amount={inv.rl_usd_amount}&memo={inv.memo}"
    qr_png = make_qr(pay_uri)

    st.markdown(f"**Invoice #{inv.invoice_id} — ${inv.amount_usd} USD → {inv.rl_usd_amount} RLUSD**")
    st.image(qr_png, caption="Scan to pay (demo URI)")

    # Invoice PDF
    pdf_path = Path(".payhub/out") / f"{inv.invoice_id}.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    save_invoice_pdf(inv, qr_png, pdf_path)
    st.download_button("Download Invoice PDF", data=pdf_path.read_bytes(), file_name=pdf_path.name)

    st.divider()
    st.subheader("Simulate / Confirm Payment")

    # Demo route: if seller == sender, send DROP:1 to XRPL sink
    dest = inv.seller_account
    send_amount = str(inv.rl_usd_amount)  # RLUSD logical amount; demo path will override to DROP:1
    if dest == xrpl.wallet.classic_address:
        st.info("Demo mode: seller == sender → routing to XRPL blackhole for a 1-drop test TX.")
        dest = "rrrrrrrrrrrrrrrrrrrrBZbvji"
        send_amount = "DROP:1"

    if st.button("Send Demo Payment (uses your seed)"):
        import hashlib
        inv_hash = hashlib.sha256(inv.model_dump_json().encode()).hexdigest()
        tx_hash = xrpl.send_rlusd(
            destination=dest,
            amount_units=send_amount,
            memo=inv.memo,
            anchor_hash=inv_hash,
            rlusd_issuer=rlusd_cfg.get("issuer"),
            rlusd_currency=rlusd_cfg.get("currency"),
        )
        st.session_state["tx_hash"] = tx_hash
        st.write(f"Destination used: **{dest}**  •  Amount: **{send_amount}**")
        if not tx_hash:
            st.error("No transaction hash returned.")
        else:
            st.info(f"Submitted TX: {tx_hash}. Waiting for validation...")
            ok = xrpl.wait_tx_validated(tx_hash)
            if ok:
                st.success("Payment validated on XRPL.")
                # Explorer link (testnet explorer works even if node is custom)
                st.markdown(f"[View on XRPL Testnet Explorer](https://testnet.xrpl.org/transactions/{tx_hash})")
            else:
                st.error("Validation timeout (check manually).")

    # Manual hash entry/override
    tx_hash = st.text_input("Or paste XRPL TX hash", value=st.session_state.get("tx_hash", ""))

    if st.button("VaultSeal Receipt"):
        if not tx_hash:
            st.error("Provide a validated TX hash.")
        else:
            receipt = make_receipt_vault(inv.model_dump(), tx_hash)
            vault_dir = Path(".payhub/out") / inv.invoice_id
            vault_dir.mkdir(parents=True, exist_ok=True)
            vault_path = write_encrypted_vault(receipt, vault_dir, password="ownYourImprint")
            receipt_pdf = vault_dir / "receipt.pdf"
            export_pdf(vault_path, receipt_pdf)
            st.success("Vault & PDF created.")
            st.download_button("Download Receipt PDF", data=receipt_pdf.read_bytes(), file_name=receipt_pdf.name)

    st.divider()
    st.subheader("Export for QuickBooks / Xero")
    if st.button("Export CSV"):
        rows = [{
            "Date": inv.issued_at.date().isoformat(),
            "InvoiceID": inv.invoice_id,
            "Customer": inv.buyer_name,
            "Email": inv.buyer_email,
            "AmountUSD": f"{inv.amount_usd:.2f}",
            "AmountRLUSD": f"{inv.rl_usd_amount:.2f}",
            "XRPLTx": st.session_state.get("tx_hash", ""),
            "Memo": inv.memo,
        }]
        csv_path = Path(".payhub/out") / f"{inv.invoice_id}.csv"
        write_qb_csv(rows, csv_path)
        st.download_button("Download CSV", data=csv_path.read_bytes(), file_name=csv_path.name)

