# pip install xrpl-py
from xrpl.core.binarycodec import encode
from xrpl.core.keypairs import sign, derive_keypair

def sign_xrp_payment_tx(
    privkey_hex: str,
    account: str,
    destination: str,
    amount_drops: int,
    sequence: int,
    fee_drops: int,
    flags: int = 2147483648,  # tfFullyCanonicalSig
    network_id: int | None = None,
) -> str:
    pubkey_hex, _ = derive_keypair(privkey_hex)
    tx = {
        "TransactionType": "Payment",
        "Account": account,
        "Destination": destination,
        "Amount": str(int(amount_drops)),
        "Sequence": int(sequence),
        "Fee": str(int(fee_drops)),
        "Flags": int(flags),
        "SigningPubKey": pubkey_hex,
    }
    if network_id is not None: tx["NetworkID"] = int(network_id)
    unsigned_blob = encode(tx)
    tx["TxnSignature"] = sign(unsigned_blob, privkey_hex)
    return encode(tx)  # signed blob hex (no 0x)
