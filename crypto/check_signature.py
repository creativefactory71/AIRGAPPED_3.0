import json
from web3 import Web3
from eth_account import Account 
from hexbytes import HexBytes

# --- CONFIGURATION ---

WALLET_FILE = "wallet.json"
# 🎯 Updated to use the public RPC endpoint
RPC_URL = "https://0xrpc.io/sep" 

RECIPIENT_ADDRESS = "0xb5Cd926b42E30bD043C71673C326969570ba9b54" 
AMOUNT_TO_SEND_WEI = Web3.to_wei(0.001, 'ether')

# CRITICAL: These MUST be set correctly for the target network.
CHAIN_ID = 11155111  # Sepolia Chain ID 
NONCE = 0           # <<< 🛑 UPDATE THIS MANUALLY! Use the correct transaction count for the sender.
GAS_LIMIT = 21000   
MAX_PRIORITY_FEE_PER_GAS = Web3.to_wei(2, 'gwei') 
MAX_FEE_PER_GAS = Web3.to_wei(30, 'gwei') 
# --- END CONFIGURATION ---


def load_eth_credentials(file_path):
    """Loads ETH address and private key from the wallet JSON."""
    try:
        with open(file_path, 'r') as f:
            wallet_data = json.load(f)
        eth_account = next(
            (acc for acc in wallet_data['accounts'] if acc['network_key'] == 'ETH'),
            None
        )
        if eth_account:
            private_key = eth_account['private_key']
            if not private_key.startswith('0x'):
                private_key = '0x' + private_key
            return eth_account['address'], private_key
        else:
            raise ValueError("ETH account not found in wallet file.")
    except Exception as e:
        print(f"Error reading wallet file: {e}")
        return None, None


def sign_offline_transaction():
    """Generates the raw, signed transaction hex."""
    sender_address, private_key = load_eth_credentials(WALLET_FILE)
    if not sender_address or not private_key: return None

    try:
        local_account = Account.from_key(private_key)

        transaction = {
            'from': sender_address,
            'to': RECIPIENT_ADDRESS,
            'value': AMOUNT_TO_SEND_WEI,
            'gas': GAS_LIMIT,
            'nonce': NONCE,
            'chainId': CHAIN_ID,
            'maxFeePerGas': MAX_FEE_PER_GAS,
            'maxPriorityFeePerGas': MAX_PRIORITY_FEE_PER_GAS
        }
        
        print("\n--- OFFLINE SIGNING ---")
        print(f"Sender: {sender_address} | Nonce: {NONCE} | ChainID: {CHAIN_ID}")
        
        # Perform the OFF-CHAIN signing
        signed_txn = local_account.sign_transaction(transaction)
        
        # Extract the raw, signed transaction bytes
        raw_tx_hex = Web3.to_hex(signed_txn.raw_transaction)
        
        print(f"\n✅ Signed successfully. Raw transaction hex generated.")
        return raw_tx_hex

    except Exception as e:
        print(f"\n❌ OFFLINE SIGNING FAILED: {e}")
        return None


def broadcast_online_transaction(raw_tx_hex):
    """Connects to the node and sends the signed transaction for validation and mining."""
    if not raw_tx_hex:
        print("🛑 Cannot broadcast: No raw transaction hex provided.")
        return

    print("\n--- ONLINE BROADCASTING ---")
    try:
        # 1. Connect to the Ethereum node using the public RPC
        w3 = Web3(Web3.HTTPProvider(RPC_URL))

        if not w3.is_connected():
            print(f"❌ Failed to connect to Ethereum node at {RPC_URL}")
            return
        
        print(f"✅ Connected to network: {w3.eth.chain_id} (Expected {CHAIN_ID})")

        # 2. Send the raw, signed transaction to the network
        print("⏳ Broadcasting raw transaction...")
        tx_hash = w3.eth.send_raw_transaction(raw_tx_hex)
        
        print(f"📢 Transaction sent. Hash: {Web3.to_hex(tx_hash)}")
        
        # 3. Wait for the transaction to be mined
        print("⏳ Waiting for confirmation...")
        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

        print("\n--- TEST SUCCESSFUL! ---")
        print(f"✅ Signature verification successful and transaction mined!")
        print(f"Transaction Hash: {Web3.to_hex(tx_hash)}")
        print(f"Block Number: {tx_receipt.blockNumber}")
        print("------------------------")

    except ValueError as e:
        # This catches errors like 'nonce too low' or 'insufficient funds'
        print(f"\n❌ BROADCAST FAILED (ValueError): {e}")
        print("HINT: If the error is NOT 'invalid signature', the signing was probably OK, but the parameters (nonce/gas/funds) were wrong.")
    except Exception as e:
        print(f"\n❌ BROADCAST FAILED (Unexpected Error): {e}")


if __name__ == "__main__":
    # 1. Perform the offline signing step
    raw_tx_hex_data = sign_offline_transaction()
    
    # 2. Test online by broadcasting the result
    if raw_tx_hex_data:
        broadcast_online_transaction(raw_tx_hex_data)