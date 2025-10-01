import csv
from pathlib import Path
from typing import List, Dict

QB_FIELDS = ["Date","InvoiceID","Customer","Email","AmountUSD","AmountRLUSD","XRPLTx","Memo"]

def write_qb_csv(rows: List[Dict], out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=QB_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in QB_FIELDS})
