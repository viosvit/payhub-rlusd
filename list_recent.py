from xrpl.clients.json_rpc_client import JsonRpcClient
from xrpl.models.requests import AccountTx
from pathlib import Path
try:
    import tomllib as tomli
except ModuleNotFoundError:
    import tomli

cfg = tomli.loads(Path("settings.toml").read_text())
addr = cfg["xrpl"]["account"].strip()
c = JsonRpcClient("https://s.altnet.rippletest.net:51234/")
resp = c.request(AccountTx(account=addr, limit=10, forward=False)).result

def dec(x):
    if not x: return ""
    try: return bytes.fromhex(x).decode("utf-8")
    except Exception: return x

for it in resp.get("transactions", []):
    tx = it.get("tx", {})
    if tx.get("TransactionType") != "Payment":
        continue
    h = tx.get("hash") or it.get("hash")
    dest = tx.get("Destination"); amt = tx.get("Amount")
    memos = []
    for m in tx.get("Memos") or []:
        mm = m.get("Memo", {})
        memos.append((dec(mm.get("MemoType")), dec(mm.get("MemoData"))))
    print(f"{h}  to={dest}  amt={amt}  memos={memos}")
