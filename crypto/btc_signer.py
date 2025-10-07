# btc_signer.py
# pyright: reportMissingImports=false, reportAttributeAccessIssue=false
# Single-input P2WPKH signer (btclib), resilient to module layout changes.
import importlib
from btclib.tx import Tx, TxIn, TxOut, OutPoint

# --- small local helper: hex string -> bytes (handles 0x prefix, odd length)
def _bytes_from_hex(s: str) -> bytes:
    if not isinstance(s, str):
        raise TypeError("hex input must be str")
    h = s.strip().lower()
    if h.startswith("0x"):
        h = h[2:]
    if len(h) % 2:
        h = "0" + h
    return bytes.fromhex(h)

def _import_attr(mod_paths, attr_names):
    last = None
    for mp in mod_paths:
        try:
            m = importlib.import_module(mp)
            for an in attr_names:
                if hasattr(m, an):
                    return getattr(m, an)
        except Exception as e:
            last = e
    raise ImportError(f"Could not import {attr_names} from {mod_paths}") from last

# dynamic imports (work across btclib builds)
addr_to_scriptpubkey = _import_attr(
    ["btclib.address", "btclib.script.address"],
    ["addr_to_scriptpubkey", "address_to_scriptpubkey"],
)
PSBT = _import_attr(
    ["btclib.psbt.psbt", "btclib.psbt"],
    ["PSBT", "Psbt"],
)
sign_psbtin = _import_attr(
    ["btclib.psbt.psbt_in", "btclib.psbt.input"],
    ["sign_psbtin"],
)
prvkey_from_prvkeyhex = _import_attr(
    ["btclib.keys"],
    ["prvkey_from_prvkeyhex"],
)
pubkey_from_prvkey = _import_attr(
    ["btclib.keys"],
    ["pubkey_from_prvkey"],
)

def _make_psbt_from_tx(tx: Tx, network: str):
    if hasattr(PSBT, "from_tx"):
        try:
            return PSBT.from_tx(tx, network=network)
        except TypeError:
            return PSBT.from_tx(tx)
    try:
        return PSBT(tx, network=network)
    except TypeError:
        return PSBT(tx)

def sign_p2wpkh_single_input(
    *,
    privkey_hex: str,
    utxo_txid_be_hex: str,
    utxo_vout: int,
    utxo_amount_sats: int,
    utxo_address: str,           # address that controls the UTXO (input owner)
    recipient_address: str,
    send_amount_sats: int,
    fee_sats: int,
    change_address: str | None = None,
    network: str = "mainnet",
) -> str:
    if send_amount_sats <= 0: raise ValueError("send_amount_sats must be > 0")
    if utxo_amount_sats <= 0: raise ValueError("utxo_amount_sats must be > 0")
    if fee_sats < 0: raise ValueError("fee_sats must be >= 0")

    change_sats = utxo_amount_sats - send_amount_sats - fee_sats
    if change_sats < 0: raise ValueError("Insufficient funds")

    # Build tx (little-endian txid inside the transaction)
    prev_txid_le = _bytes_from_hex(utxo_txid_be_hex)[::-1]
    txin = TxIn(OutPoint(prev_txid_le, int(utxo_vout)), b"", 0xFFFFFFFF)

    outs = [TxOut(int(send_amount_sats), addr_to_scriptpubkey(recipient_address, network))]
    if change_sats > 0:
        outs.append(TxOut(int(change_sats), addr_to_scriptpubkey(change_address or utxo_address, network)))

    tx = Tx(2, [txin], outs, 0)

    # PSBT + witness UTXO
    psbt = _make_psbt_from_tx(tx, network)
    psbt.inputs[0].witness_utxo = TxOut(int(utxo_amount_sats), addr_to_scriptpubkey(utxo_address, network))

    # Keys
    prv = prvkey_from_prvkeyhex(privkey_hex)
    pub = pubkey_from_prvkey(prv, compressed=True)

    # Sign input 0 (SIGHASH_ALL)
    try:
        sign_psbtin(psbt, 0, prv, pub, sighash_flag=1)
    except TypeError:
        sign_psbtin(psbt, 0, prv, pub, 1)

    # Finalize & extract raw hex
    if hasattr(psbt, "finalize"): psbt.finalize()
    elif hasattr(psbt, "finalize_psbt"): psbt.finalize_psbt()
    elif hasattr(psbt, "finalize_input"): psbt.finalize_input(0)

    tx_out = getattr(psbt, "tx", None) or (psbt.to_tx() if hasattr(psbt, "to_tx") else None)
    if tx_out is None:
        raise RuntimeError("btclib PSBT: cannot extract final transaction")
    return tx_out.serialize().hex()
