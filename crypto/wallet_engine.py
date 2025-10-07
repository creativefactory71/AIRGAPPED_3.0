# wallet_engine.py
from mnemonic import Mnemonic
from bip_utils import (
    Bip39SeedGenerator,
    Bip44, Bip44Coins,
    Bip49, Bip49Coins,
    Bip84, Bip84Coins,
    Bip44Changes,
)

class WalletEngine:
    def __init__(self, lang="english"):
        self.mnemo = Mnemonic(lang)

    # --- Seed & validation ---
    def generate_mnemonic(self, words=12) -> str:
        strength = 128 if words == 12 else 256
        return self.mnemo.generate(strength=strength)

    def validate_mnemonic(self, mnemonic: str) -> bool:
        return self.mnemo.check(mnemonic.strip())

    def mnemonic_to_seed(self, mnemonic: str, passphrase: str = "") -> bytes:
        return Bip39SeedGenerator(mnemonic.strip()).Generate(passphrase)

    # --- EVM derivation (ETH & EVM-like) ---
    def derive_evm_account(self, seed: bytes, derivation_path: str = "m/44'/60'/0'/0/0"):
        """
        Returns dict:
          {private_key, public_key, address, derivation_path, index}
        public_key: uncompressed hex (starts with '04').
        """
        # Best-effort leaf index parsing from path
        index = 0
        try:
            index = int(derivation_path.split("/")[-1])
        except Exception:
            index = 0

        acct = (
            Bip44.FromSeed(seed, Bip44Coins.ETHEREUM)
            .Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(index)
        )

        priv_hex = acct.PrivateKey().Raw().ToHex()
        pub_uncompressed_hex = acct.PublicKey().RawUncompressed().ToHex()  # '04' + X + Y
        address = acct.PublicKey().ToAddress()

        return {
            "private_key": priv_hex,
            "public_key": pub_uncompressed_hex,
            "address": address,
            "derivation_path": derivation_path,
            "index": index,
        }

    # --- BTC/UTXO derivation ---
    def derive_utxo_account(
        self,
        seed: bytes,
        address_type: str = "P2WPKH",
        coin_type: int = 0,  # reserved for future use
        derivation_path: str = "m/84'/0'/0'/0/0",
    ):
        """
        address_type: P2WPKH (bech32), P2SH-P2WPKH, P2PKH
        Returns dict:
          {private_key (WIF), public_key (compressed hex), address, derivation_path, index}
        """
        addr_type = (address_type or "P2WPKH").upper()

        if addr_type == "P2WPKH":
            # Native SegWit (BIP84)
            acct = (
                Bip84.FromSeed(seed, Bip84Coins.BITCOIN)
                .Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
            )
        elif addr_type == "P2SH-P2WPKH":
            # Nested SegWit (BIP49)
            acct = (
                Bip49.FromSeed(seed, Bip49Coins.BITCOIN)
                .Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
            )
        else:
            # Legacy (BIP44)
            acct = (
                Bip44.FromSeed(seed, Bip44Coins.BITCOIN)
                .Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)
            )

        address = acct.PublicKey().ToAddress()
        pub_comp_hex = acct.PublicKey().RawCompressed().ToHex()

        # Get WIF directly from the private key (handles net + version internally)
        try:
            wif = acct.PrivateKey().ToWif(compressed=True)
        except TypeError:
            # some versions use no argument
            wif = acct.PrivateKey().ToWif()

        return {
            "private_key": wif,
            "public_key": pub_comp_hex,
            "address": address,
            "derivation_path": derivation_path,
            "index": 0,
        }
