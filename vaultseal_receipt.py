import json, sys
from datetime import datetime
from pathlib import Path
from hashlib import sha256

# add core to path
for p in ("./v1_production_release","../v1_production_release"):
    cp = (Path(__file__).resolve().parent / p).resolve()
    if cp.exists() and str(cp) not in sys.path:
        sys.path.insert(0, str(cp))

from vault_crypto import encrypt_vault_bytes  # core
import pdf_exporter  # core

def make_receipt_vault(invoice_dict: dict, xrpl_tx_hash: str) -> dict:
    ts = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    body = {"type":"payhub.receipt.v1","timestamp":ts,"invoice":invoice_dict,"xrpl_tx_hash":xrpl_tx_hash}
    b = json.dumps(body, sort_keys=True).encode()
    return {"header":{"version":"2.0","app":"PayHub","schema":"payhub.receipt.v1","hash":sha256(b).hexdigest(),"created_at":ts},"body":body}

def write_encrypted_vault(receipt_obj: dict, out_dir: Path, password: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(receipt_obj, sort_keys=True).encode()
    enc = encrypt_vault_bytes(raw, password=password)
    vp = out_dir / "receipt.vault"
    with open(vp, "wb") as f: f.write(enc)
    return vp

def export_pdf(vault_path: Path, out_pdf: Path):
    pdf_exporter.main(str(vault_path), str(out_pdf))
