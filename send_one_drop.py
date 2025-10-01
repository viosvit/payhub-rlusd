from pathlib import Path
try:
    import tomllib as tomli
except ModuleNotFoundError:
    import tomli

from xrpl.clients.json_rpc_client import JsonRpcClient
from xrpl.wallet import Wallet
from xrpl.models.transactions import Payment, Memo
from xrpl.transaction import autofill_and_sign, submit_and_wait
from xrpl.utils import str_to_hex
from xrpl.models.requests import AccountTx

cfg = tomli.loads(Path("settings.toml").read_text())
seed = cfg["xrpl"]["seed"].strip()
acct = cfg["xrpl"]["account"].strip()
node = "https://s.altnet.rippletest.net:51234/"

client = JsonRpcClient(node)
wallet = Wallet.from_seed(seed)

memos = [
    Memo(memo_type=str_to_hex("vaultseal.hash"),
         memo_data="7661756c747365616c2d64656d6f2d68617368"),  # 'vaultseal-demo-hash'
    Memo(memo_data="5061794875622044454d4f"),  # 'PayHub DEMO'
]
tx = Payment(
    account=wallet.classic_address,
    destination="rrrrrrrrrrrrrrrrrrrrBZbvji",
    amount="1",  # one drop
    memos=memos,
)

def call_autofill_and_sign(tx, client, wallet):
    try:    return autofill_and_sign(tx, client, wallet)   # 2.3.0
    except TypeError: return autofill_and_sign(tx, wallet, client)   # 2.4.0

stx = call_autofill_and_sign(tx, client, wallet)
resp = submit_and_wait(stx, client)
res = getattr(resp, "result", resp)

tx_hash = None
for path in [lambda r: r.get("tx_json",{}).get("hash"),
             lambda r: r.get("transaction",{}).get("hash"),
             lambda r: r.get("engine_result_object",{}).get("tx_json",{}).get("hash")]:
    try:
        tx_hash = tx_hash or path(res)
    except Exception:
        pass

if not tx_hash:
    atx = client.request(AccountTx(account=acct, limit=10, forward=False)).result
    for it in atx.get("transactions", []):
        txo = it.get("tx", {})
        if (txo.get("TransactionType")=="Payment"
            and txo.get("Destination")=="rrrrrrrrrrrrrrrrrrrrBZbvji"
            and str(txo.get("Amount"))=="1"):
            mems = txo.get("Memos") or []
            ok=False
            for m in mems:
                md = (m.get("Memo",{}) or {}).get("MemoData")
                if not md: continue
                try: dec = bytes.fromhex(md).decode("utf-8")
                except Exception: dec = ""
                if "PayHub DEMO" in dec:
                    ok=True; break
            if ok:
                tx_hash = txo.get("hash") or it.get("hash")
                break

print("TX_HASH=", tx_hash)
