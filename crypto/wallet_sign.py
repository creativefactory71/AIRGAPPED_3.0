# wallet_sign.py
from eth_account import Account
from eth_account.messages import encode_defunct
import json
from eth_account._utils.legacy_transactions import serializable_unsigned_transaction_from_dict, encode_transaction

Account.enable_unaudited_hdwallet_features()

def sign_transaction_with_privkey_hex(privkey_hex, tx_dict):
    """
    tx_dict expects: to (str), value (as string or int wei), nonce (int), gas (int), gasPrice (int)
    Returns serialized signed tx hex (0x...)
    """
    acct = Account.from_key(bytes.fromhex(privkey_hex))
    # Build legacy txn dict
    txn = {
        "nonce": int(tx_dict["nonce"]),
        "gasPrice": int(tx_dict["gasPrice"]),
        "gas": int(tx_dict["gas"]),
        "to": tx_dict["to"],
        "value": int(tx_dict["value"]),
        "data": b'',
        "chainId": 1  # default to mainnet for demo; change as needed
    }
    signed = acct.sign_transaction(txn)
    return signed.raw_transaction.hex()
