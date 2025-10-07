# network_store.py
import json
from pathlib import Path

NETWORKS_PATH = Path("networks.json")

_DEFAULTS = {
    "version": 1,
    "networks": [
        # EVM (built-ins)
        {
            "key": "ETH",
            "name": "Ethereum",
            "type": "evm",
            "symbol": "ETH",
            "chain_id": 1,  # change to 11155111 if you want Sepolia by default
            "derivation_path": "m/44'/60'/0'/0/{index}"
        },
        {
            "key": "XDC",
            "name": "XDC Network",
            "type": "evm",
            "symbol": "XDC",
            "chain_id": 50,
            "derivation_path": "m/44'/60'/0'/0/{index}"
        },
        # BTC (UTXO)
        {
            "key": "BTC",
            "name": "Bitcoin",
            "type": "utxo",
            "symbol": "BTC",
            "address_type": "P2WPKH",
            "coin_type": 0,
            "derivation_path": "m/84'/0'/0'/0/{index}"
        },
        # XRP
        {
            "key": "XRP",
            "name": "XRP Ledger",
            "type": "xrp",
            "symbol": "XRP",
            "derivation_path": "m/44'/144'/0'/0/{index}"
        }
    ]
}

_BUILTIN_KEYS = {n["key"] for n in _DEFAULTS["networks"]}
_NON_EVM_BUILTINS = {"BTC", "XRP"}  # must NOT be overridden by custom

def _save(data: dict):
    NETWORKS_PATH.write_text(json.dumps(data, indent=2))

def _merge_defaults(data: dict) -> dict:
    """Ensure defaults exist at least once by key; preserve existing custom entries."""
    if not isinstance(data, dict):
        data = {"version": _DEFAULTS["version"], "networks": []}
    nets = data.get("networks")
    if not isinstance(nets, list):
        nets = []
    have = {n.get("key") for n in nets if isinstance(n, dict)}
    for b in _DEFAULTS["networks"]:
        if b["key"] not in have:
            nets.append(b)
    data["version"] = data.get("version", _DEFAULTS["version"])
    data["networks"] = nets
    return data

def load_networks() -> dict:
    if not NETWORKS_PATH.exists():
        data = _merge_defaults({"version": _DEFAULTS["version"], "networks": []})
        _save(data)
        return data
    try:
        data = json.loads(NETWORKS_PATH.read_text() or "{}")
    except Exception:
        data = {}
    data = _merge_defaults(data)
    _save(data)  # keep file normalized
    return data

def save_networks(data: dict):
    """Overwrite the full object (use sparingly)."""
    _save(_merge_defaults(data))

def list_networks() -> list:
    """Return the list of networks (built-ins + custom), normalized."""
    return load_networks()["networks"]

def add_network(net: dict):
    """
    Add or replace a CUSTOM network.
    Rules:
      - Custom networks MUST be EVM: type == "evm"
      - Cannot override built-in non-EVM networks: BTC, XRP
      - Key is uppercased and required
      - chain_id is required for EVM; derivation_path defaults to m/44'/60'/0'/0/{index}
    """
    if not isinstance(net, dict):
        raise ValueError("Network must be an object")

    key = (net.get("key") or "").upper().strip()
    if not key:
        raise ValueError("Network 'key' is required")

    ntype = (net.get("type") or "").lower().strip()
    if ntype != "evm":
        # Only EVM custom networks allowed
        raise ValueError("Custom networks must have type 'evm'")

    if key in _NON_EVM_BUILTINS:
        # Prevent overriding BTC or XRP
        raise ValueError(f"Cannot override built-in non-EVM network: {key}")

    # Build normalized object
    name = net.get("name") or key
    symbol = net.get("symbol") or key
    try:
        chain_id = int(net.get("chain_id"))
    except Exception:
        raise ValueError("EVM 'chain_id' must be provided as an integer")

    derivation_path = net.get("derivation_path") or "m/44'/60'/0'/0/{index}"

    new_obj = {
        "key": key,
        "name": name,
        "type": "evm",
        "symbol": symbol,
        "chain_id": chain_id,
        "derivation_path": derivation_path,
    }

    data = load_networks()
    nets = data["networks"]

    # If an entry with this key exists and is non-EVM (BTC/XRP), block it.
    for existing in nets:
        if (existing.get("key") or "").upper() == key and (existing.get("type") or "").lower() != "evm":
            raise ValueError(f"Cannot replace non-EVM built-in '{key}'")

    # Upsert by key
    replaced = False
    for i, existing in enumerate(nets):
        if (existing.get("key") or "").upper() == key:
            nets[i] = new_obj
            replaced = True
            break
    if not replaced:
        nets.append(new_obj)

    data["networks"] = nets
    _save(data)
