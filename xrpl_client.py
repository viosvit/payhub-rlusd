# xrpl_client.py — RLUSD-ready, version-agnostic, dev-safe
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple, Any

from xrpl.clients.json_rpc_client import JsonRpcClient
from xrpl.wallet import Wallet
from xrpl.models.transactions import Payment, Memo, TrustSet
from xrpl.models.amounts import IssuedCurrencyAmount
from xrpl.models.requests import AccountInfo, Tx, AccountTx
from xrpl.utils import xrp_to_drops, str_to_hex

# ---- version-agnostic wrappers (xrpl-py 2.3.0 vs 2.4.0) ---------------------
try:
    from xrpl.transaction import autofill_and_sign as __afn  # 2.4.0 style name, signature (tx, wallet, client)
    from xrpl.transaction import submit_and_wait as __saw
except Exception:
    # 2.3.0 import path
    from xrpl.transaction import (
        autofill_and_sign as __afn,      # signature (tx, client, wallet)
        submit_and_wait as __saw,
    )

def _call_autofill_and_sign(tx, client: JsonRpcClient, wallet: Wallet):
    """
    - xrpl-py 2.3.0: autofill_and_sign(tx, client, wallet)
    - xrpl-py 2.4.0: autofill_and_sign(tx, wallet, client)
    """
    try:
        return __afn(tx, client, wallet)   # 2.3.0
    except TypeError:
        return __afn(tx, wallet, client)   # 2.4.0

def _call_submit_and_wait(stx, client: JsonRpcClient):
    resp = __saw(stx, client)
    return getattr(resp, "result", resp)

# -----------------------------------------------------------------------------

@dataclass
class XRPLConfig:
    network_url: str
    seed: str
    account: str
    demo_mode: bool = True                # demo: allow DROP:1 blackhole fallback
    blackhole_addr: str = "rrrrrrrrrrrrrrrrrrrrBZbvji"  # well-known sink

class XRPLClient:
    def __init__(self, cfg: XRPLConfig):
        self.cfg = cfg
        self.client = JsonRpcClient(cfg.network_url)
        self.wallet = Wallet.from_seed(cfg.seed)

    # --- utilities ------------------------------------------------------------
    def ping(self) -> bool:
        try:
            info = self.client.request(AccountInfo(account=self.wallet.classic_address)).result
            return "account_data" in info
        except Exception:
            return False

    def _tx_hash_from_result(self, res: dict) -> Optional[str]:
        for path in (
            lambda r: r.get("tx_json", {}).get("hash"),
            lambda r: r.get("transaction", {}).get("hash"),
            lambda r: r.get("engine_result_object", {}).get("tx_json", {}).get("hash"),
        ):
            try:
                h = path(res)
                if h:
                    return h
            except Exception:
                pass
        return None

    def wait_tx_validated(self, tx_hash: str, timeout_s: int = 30) -> bool:
        import time
        t0 = time.time()
        while time.time() - t0 < timeout_s:
            try:
                resp = self.client.request(Tx(transaction=tx_hash, binary=False)).result
                if resp.get("validated"):
                    return resp.get("meta", {}).get("TransactionResult") == "tesSUCCESS"
            except Exception:
                pass
            time.sleep(2)
        return False

    # --- DEV XRP path (fallback) ---------------------------------------------
    def send_demo_xrp(self, destination: str, amount_units: str, memo: str = "", anchor_hash: str = "") -> str:
        """
        Dev-only: send 1 drop to blackhole when dest == sender OR amount is too small.
        Supports "DROP:<n>" to force raw drop amounts in demo.
        """
        dest = destination
        memos = []
        if memo:
            memos.append(Memo(memo_data=memo.encode().hex()))
        if anchor_hash:
            memos.append(Memo(memo_type=str_to_hex("vaultseal.hash"), memo_data=anchor_hash.encode().hex()))

        # Self-send guard + drop handling (DEV only)
        force_drops: Optional[str] = None
        if amount_units.startswith("DROP:"):
            force_drops = amount_units.split(":", 1)[1].strip()

        if dest == self.wallet.classic_address:
            # route to sink in demo
            dest = self.cfg.blackhole_addr
            force_drops = force_drops or "1"  # minimum 1 drop

        if force_drops is not None:
            amt_drops = force_drops
        else:
            # normal conversion with guard
            try:
                amt_drops = xrp_to_drops(float(amount_units))
            except Exception:
                amt_drops = "1"

        tx = Payment(
            account=self.wallet.classic_address,
            destination=dest,
            amount=str(amt_drops),
            memos=memos or None,
        )
        stx = _call_autofill_and_sign(tx, self.client, self.wallet)
        res = _call_submit_and_wait(stx, self.client)
        h = self._tx_hash_from_result(res)
        if not h:
            # last-chance search by account tx (recent)
            atx = self.client.request(AccountTx(account=self.wallet.classic_address, limit=10, forward=False)).result
            for it in atx.get("transactions", []):
                txo = it.get("tx", {})
                if (
                    txo.get("TransactionType") == "Payment"
                    and txo.get("Destination") == dest
                    and str(txo.get("Amount")) == str(amt_drops)
                ):
                    h = txo.get("hash") or it.get("hash")
                    break
        return h or ""

    # --- RLUSD trustline + IOU payment --------------------------------------
    def ensure_trustline(self, issuer: str, currency: str, limit: str = "1000000") -> None:
        tx = TrustSet(
            account=self.wallet.classic_address,
            limit_amount=IssuedCurrencyAmount(currency=currency, issuer=issuer, value=limit),
        )
        stx = _call_autofill_and_sign(tx, self.client, self.wallet)
        _call_submit_and_wait(stx, self.client)  # fire-and-forget; node will reject if already set

    def send_iou(
        self,
        destination: str,
        amount_units: str,
        currency: str,
        issuer: str,
        memo: str = "",
        anchor_hash: str = "",
    ) -> str:
        memos = []
        if memo:
            memos.append(Memo(memo_data=memo.encode().hex()))
        if anchor_hash:
            memos.append(Memo(memo_type=str_to_hex("vaultseal.hash"), memo_data=anchor_hash.encode().hex()))

        amt = IssuedCurrencyAmount(currency=currency, issuer=issuer, value=str(amount_units))
        tx = Payment(
            account=self.wallet.classic_address,
            destination=destination,
            amount=amt,
            memos=memos or None,
        )
        stx = _call_autofill_and_sign(tx, self.client, self.wallet)
        res = _call_submit_and_wait(stx, self.client)
        return self._tx_hash_from_result(res) or ""

    # --- Unified entry -------------------------------------------------------
    def send_rlusd(
        self,
        destination: str,
        amount_units: str,
        memo: str = "",
        anchor_hash: str = "",
        rlusd_issuer: Optional[str] = None,
        rlusd_currency: Optional[str] = None,
    ) -> str:
        if rlusd_issuer and rlusd_currency:
            # production IOU path
            self.ensure_trustline(rlusd_issuer, rlusd_currency)
            return self.send_iou(destination, amount_units, rlusd_currency, rlusd_issuer, memo, anchor_hash)

        # DEV fallback path
        if not self.cfg.demo_mode:
            raise RuntimeError("RLUSD config missing and demo_mode is disabled.")
        return self.send_demo_xrp(destination, amount_units, memo, anchor_hash)

