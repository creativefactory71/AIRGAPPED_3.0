# stores/network_store.py
import json, re
from pathlib import Path

NETWORKS_PATH = Path("networks.json")
_ALLOWED_TYPES = {"evm","utxo","xrp"}

_DEFAULTS = {
    "version": 1,
    "networks": [
        {"key":"ETH","name":"Ethereum","type":"evm","symbol":"ETH","chain_id":1,"derivation_path":"m/44'/60'/0'/0/{index}"},
        {"key":"BTC","name":"Bitcoin","type":"utxo","symbol":"BTC","address_type":"P2WPKH","coin_type":0,"derivation_path":"m/84'/0'/0'/0/{index}"},
        {"key":"XDC","name":"XDC Network","type":"evm","symbol":"XDC","chain_id":50,"derivation_path":"m/44'/60'/0'/0/{index}"},
        {"key":"XRP","name":"Ripple","type":"xrp","symbol":"XRP"}
    ]
}

def load_networks():
    if not NETWORKS_PATH.exists():
        save_networks(_DEFAULTS); return _DEFAULTS
    try:
        data = json.loads(NETWORKS_PATH.read_text())
        if "networks" not in data or not isinstance(data["networks"], list):
            data["networks"] = _DEFAULTS["networks"]
        return data
    except Exception:
        save_networks(_DEFAULTS); return _DEFAULTS

def save_networks(data):
    NETWORKS_PATH.write_text(json.dumps(data, indent=2))

def list_networks():
    return load_networks()["networks"]

_KEY_RE = re.compile(r"^[A-Z0-9_]{2,12}$")

def _validate(net: dict) -> dict:
    # required
    k = (net.get("key") or "").upper()
    t = (net.get("type") or "").lower()
    name = (net.get("name") or "").strip()
    sym = (net.get("symbol") or "").strip()
    if not _KEY_RE.match(k): raise ValueError("key must be 2–12 chars [A-Z0-9_]")
    if t not in _ALLOWED_TYPES: raise ValueError("type must be one of: evm, utxo, xrp")
    if not name: raise ValueError("name required")
    if not sym:  raise ValueError("symbol required")

    out = {"key": k, "name": name, "type": t, "symbol": sym}
    if t == "evm":
        out["chain_id"] = int(net.get("chain_id", 1))
        out["derivation_path"] = net.get("derivation_path") or "m/44'/60'/0'/0/{index}"
    elif t == "utxo":
        out["address_type"] = (net.get("address_type") or "P2WPKH").upper()
        out["coin_type"] = int(net.get("coin_type", 0))
        out["derivation_path"] = net.get("derivation_path") or ("m/84'/%d'/0'/0/{index}" % out["coin_type"])
    else:  # xrp
        pass
    return out

def add_or_replace_network(net: dict):
    data = load_networks()
    newn = _validate(net)
    data["networks"] = [n for n in data["networks"] if n.get("key","").upper() != newn["key"]]
    data["networks"].append(newn)
    save_networks(data)

def edit_network(key: str, patch: dict):
    key = key.upper()
    data = load_networks()
    found = None
    for n in data["networks"]:
        if (n.get("key") or "").upper() == key:
            found = n; break
    if not found: raise KeyError(key)
    merged = {**found, **patch}
    data["networks"] = [n for n in data["networks"] if (n.get("key") or "").upper() != key]
    data["networks"].append(_validate(merged))
    save_networks(data)

def delete_network(key: str):
    key = key.upper()
    data = load_networks()
    before = len(data["networks"])
    data["networks"] = [n for n in data["networks"] if (n.get("key") or "").upper() != key]
    if len(data["networks"]) == before:
        raise KeyError(key)
    save_networks(data)
