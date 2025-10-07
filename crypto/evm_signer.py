# evm_signer.py
from web3 import Web3

def _to_0x_hex(v) -> str:
    """Normalize any bytes/HexBytes/str into a 0x-prefixed hex string."""
    if v is None:
        return "0x"
    # HexBytes and bytes both have .hex(); for HexBytes it already includes 0x
    try:
        hx = v.hex()
        return hx if isinstance(hx, str) and hx.startswith("0x") else ("0x" + hx)
    except Exception:
        s = str(v)
        return s if s.startswith("0x") else ("0x" + s)

def sign_legacy_tx(
    privkey_hex: str,
    to_addr: str,
    value_wei: int,
    nonce: int,
    gas_limit: int,
    gas_price_wei: int,
    chain_id: int,
    data_bytes: bytes = b"",
) -> str:
    """
    Sign a legacy EVM tx and return raw tx hex (0x...).
    """
    tx = {
        "nonce": int(nonce),
        "to": to_addr,
        "value": int(value_wei),
        "gas": int(gas_limit),
        "gasPrice": int(gas_price_wei),
        "chainId": int(chain_id),
        # Ensure bytes here; your unsigned JSON should use "0x"
        "data": data_bytes or b"",
    }
    w3 = Web3()  # offline signing is fine
    signed = w3.eth.account.sign_transaction(tx, bytes.fromhex(privkey_hex))
    return _to_0x_hex(signed.raw_transaction)

def sign_eip1559_tx(
    privkey_hex: str,
    to_addr: str,
    value_wei: int,
    nonce: int,
    gas_limit: int,
    max_fee_per_gas_wei: int,
    max_priority_fee_per_gas_wei: int,
    chain_id: int,
    data_bytes: bytes = b"",
) -> str:
    """
    Sign an EIP-1559 tx and return raw tx hex (0x...).
    """
    tx = {
        "type": 2,
        "nonce": int(nonce),
        "to": to_addr,
        "value": int(value_wei),
        "gas": int(gas_limit),
        "maxFeePerGas": int(max_fee_per_gas_wei),
        "maxPriorityFeePerGas": int(max_priority_fee_per_gas_wei),
        "chainId": int(chain_id),
        "data": data_bytes or b"",
    }
    w3 = Web3()
    signed = w3.eth.account.sign_transaction(tx, bytes.fromhex(privkey_hex))
    return _to_0x_hex(signed.rawTransaction)
