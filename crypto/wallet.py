# wallet.py
import os
from mnemonic import Mnemonic
from bip_utils import Bip39SeedGenerator, Bip44, Bip44Coins, Bip44Changes

MNEMONIC_LANG = "english"

def generate_mnemonic(words=12):
    mnemo = Mnemonic(MNEMONIC_LANG)
    strength = 128 if words == 12 else 256
    return mnemo.generate(strength=strength)

def mnemonic_to_seed(mnemonic, passphrase=""):
    seed_bytes = Bip39SeedGenerator(mnemonic).Generate(passphrase)
    return seed_bytes

def derive_eth_account_from_seed(seed_bytes, account_index=0):
    """
    Derive BIP44 Ethereum account (m/44'/60'/0'/0/index).
    Returns (priv_key_hex, address_hex)
    """
    bip44_mst = Bip44.FromSeed(seed_bytes, Bip44Coins.ETHEREUM)
    acct = bip44_mst.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(account_index)
    priv_key = acct.PrivateKey().Raw().ToHex()
    addr = acct.PublicKey().ToAddress()
    return priv_key, addr

def restore_from_mnemonic(mnemonic, passphrase="", index=0):
    seed = mnemonic_to_seed(mnemonic, passphrase)
    return derive_eth_account_from_seed(seed, account_index=index)
