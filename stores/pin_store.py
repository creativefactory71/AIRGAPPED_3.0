# pin_store.py
import os, json, hmac, base64, hashlib
from pathlib import Path

PIN_PATH = Path("pin.json")
ITER_DEFAULT = 200_000

def has_pin() -> bool:
    return PIN_PATH.exists()

def _b64e(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")

def _b64d(s: str) -> bytes:
    return base64.b64decode(s.encode("ascii"))

def set_pin(pin: str, iterations: int = ITER_DEFAULT):
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, iterations)
    data = {
        "version": 1,
        "iter": iterations,
        "salt": _b64e(salt),
        "hash": _b64e(dk),
    }
    PIN_PATH.write_text(json.dumps(data, indent=2))

def verify_pin(pin: str) -> bool:
    if not has_pin():
        return False
    data = json.loads(PIN_PATH.read_text())
    salt = _b64d(data["salt"])
    it = int(data.get("iter", ITER_DEFAULT))
    expect = _b64d(data["hash"])
    got = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, it)
    return hmac.compare_digest(got, expect)

def reset_pin():
    if PIN_PATH.exists():
        PIN_PATH.unlink()
