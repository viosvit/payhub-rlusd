from xrpl.clients.json_rpc_client import JsonRpcClient
from xrpl.models.requests import Tx
import sys, json

if len(sys.argv) != 2:
    print("Usage: python verify_memo.py <tx_hash>"); sys.exit(1)
h = sys.argv[1].strip()
c = JsonRpcClient("https://s.altnet.rippletest.net:51234/")
r = c.request(Tx(transaction=h, binary=False)).result

# Show errors if any
if "error" in r:
    print("❌ XRPL error:", json.dumps(r, indent=2)); sys.exit(1)

def dec(x):
    if not x: return ""
    try: return bytes.fromhex(x).decode("utf-8")
    except Exception: return x

src = r.get("Memos") or r.get("tx", {}).get("Memos") or []
memos=[]
for m in src:
    mm = m.get("Memo", {})
    memos.append((dec(mm.get("MemoType")), dec(mm.get("MemoData"))))
print("TX:", h)
print("Memos:", memos)
