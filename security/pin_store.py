# security/pin_store.py
from __future__ import annotations
import os, json, time, hmac, hashlib, base64
from pathlib import Path

PIN_PATH = Path("pin.json")
_DEFAULT_ITERS = 120_000  # balance for Pi Zero; increase on faster hardware

def _pbkdf2(pin: str, salt: bytes, iters: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, iters, dklen=32)

def _read_pin_file() -> dict | None:
    if not PIN_PATH.exists():
        return None
    try:
        return json.loads(PIN_PATH.read_text() or "{}")
    except Exception:
        return None

def pin_present() -> bool:
    obj = _read_pin_file()
    if not obj: return False
    return bool(obj.get("hash_hex") or obj.get("hash_b64"))

def verify_pin(pin: str) -> bool:
    obj = _read_pin_file()
    if not obj: return False
    # try hex first
    try:
        salt = bytes.fromhex(obj.get("salt_hex",""))
    except Exception:
        salt = None
    if not salt and obj.get("salt_b64"):
        try:
            salt = base64.b64decode(obj["salt_b64"])
        except Exception:
            pass
    if not salt:
        return False
    iters = int(obj.get("iter", _DEFAULT_ITERS))
    want = None
    if obj.get("hash_hex"):
        try: want = bytes.fromhex(obj["hash_hex"])
        except Exception: return False
    elif obj.get("hash_b64"):
        try: want = base64.b64decode(obj["hash_b64"])
        except Exception: return False
    else:
        return False
    got = _pbkdf2(pin, salt, iters)
    return hmac.compare_digest(got, want)

def set_pin(new_pin: str, iterations: int = _DEFAULT_ITERS) -> None:
    salt = os.urandom(16)
    digest = _pbkdf2(new_pin, salt, iterations)
    obj = {
        "iter": iterations,
        "salt_hex": salt.hex(),
        "hash_hex": digest.hex(),
        "updated_at": int(time.time()),
        "scheme": "pbkdf2-hmac-sha256"
    }
    PIN_PATH.write_text(json.dumps(obj, indent=2))

def change_pin(current_pin: str, new_pin: str) -> None:
    if not verify_pin(current_pin):
        raise ValueError("Current PIN incorrect")
    set_pin(new_pin)

def clear_pin() -> None:
    if PIN_PATH.exists():
        PIN_PATH.unlink()
