# stores/wallet_store.py
from __future__ import annotations
from pathlib import Path
import json, time, re, shutil

# New location for all wallet files
WALLETS_DIR = Path("wallets").resolve()
WALLETS_DIR.mkdir(parents=True, exist_ok=True)

# Meta now stored inside wallets/
META = WALLETS_DIR / "wallet_meta.json"

# Legacy (root) locations we may need to migrate from
LEGACY_ROOT = Path(".").resolve()
LEGACY_META = LEGACY_ROOT / "wallet_meta.json"

_VALID_NAME = re.compile(r"^[A-Za-z0-9_\-]{1,32}$")

def _is_wallet_file(p: Path) -> bool:
    if p.suffix.lower() != ".json":
        return False
    try:
        obj = json.loads(p.read_text() or "{}")
        return isinstance(obj, dict) and "accounts" in obj and "seed_phrase" in obj
    except Exception:
        return False

def _legacy_wallet_candidates() -> list[Path]:
    # any *.json in root that look like wallets (avoid obvious config files)
    reserved = {
        "wallet_meta.json","networks.json","settings.json","platform.json",
        "config.json","pin.json","unsigned_tx.json","signed_tx.txt"
    }
    out = []
    for p in LEGACY_ROOT.glob("*.json"):
        if p.name in reserved: 
            continue
        if _is_wallet_file(p):
            out.append(p)
    return out

def _migrate_legacy_if_needed():
    # Move legacy meta
    if not META.exists() and LEGACY_META.exists():
        try:
            META.write_text(LEGACY_META.read_text())
            # keep a backup instead of deleting
            LEGACY_META.rename(LEGACY_META.with_suffix(".json.bak"))
        except Exception:
            pass
    # Move legacy wallet jsons into wallets/
    moved = 0
    for p in _legacy_wallet_candidates():
        dst = WALLETS_DIR / p.name
        if not dst.exists():
            try:
                shutil.move(str(p), str(dst))
                moved += 1
            except Exception:
                pass
    if moved:
        # best-effort: update META if it referenced a name that still exists
        try:
            obj = json.loads(META.read_text() or "{}") if META.exists() else {}
            if "active" in obj and obj["active"]:
                # nothing to change; file names stayed the same
                META.write_text(json.dumps(obj, indent=2))
        except Exception:
            pass

_migrate_legacy_if_needed()

def list_wallet_names() -> list[str]:
    return sorted([p.stem for p in WALLETS_DIR.glob("*.json") if _is_wallet_file(p)])

def _read_meta() -> dict:
    if not META.exists():
        # pick first wallet as active if present
        names = list_wallet_names()
        active = names[0] if names else None
        obj = {"active": active, "ts": int(time.time())}
        META.write_text(json.dumps(obj, indent=2))
        return obj
    try:
        return json.loads(META.read_text() or "{}")
    except Exception:
        return {"active": None}

def active_name() -> str | None:
    return _read_meta().get("active")

def set_active(name: str) -> None:
    names = list_wallet_names()
    if name not in names:
        raise ValueError(f"Wallet '{name}' not found")
    obj = _read_meta()
    obj["active"] = name
    obj["ts"] = int(time.time())
    META.write_text(json.dumps(obj, indent=2))

def load_wallet(name: str) -> dict:
    p = WALLETS_DIR / f"{name}.json"
    if not p.exists():
        raise FileNotFoundError(p)
    return json.loads(p.read_text())

def load_active_wallet() -> dict | None:
    n = active_name()
    return load_wallet(n) if n else None

def create_wallet_file(name: str, wallet_obj: dict) -> None:
    if not _VALID_NAME.match(name):
        raise ValueError("Wallet name must be 1–32 chars: A–Z a–z 0–9 _ -")
    p = WALLETS_DIR / f"{name}.json"
    if p.exists():
        raise FileExistsError("A wallet with that name already exists")
    # Minimal sanitize
    wallet_obj = dict(wallet_obj or {})
    wallet_obj.setdefault("created_at", int(time.time()))
    wallet_obj.setdefault("name", name)
    wallet_obj.setdefault("accounts", [])
    wallet_obj.setdefault("seed_phrase", "")
    p.write_text(json.dumps(wallet_obj, indent=2))
    # If no active wallet yet, set this one
    meta = _read_meta()
    if not meta.get("active"):
        set_active(name)

def rename_wallet(old: str, new: str) -> None:
    if not _VALID_NAME.match(new):
        raise ValueError("Wallet name must be 1–32 chars: A–Z a–z 0–9 _ -")
    src = WALLETS_DIR / f"{old}.json"
    dst = WALLETS_DIR / f"{new}.json"
    if not src.exists(): 
        raise FileNotFoundError(old)
    if dst.exists(): 
        raise FileExistsError(new)
    src.rename(dst)
    meta = _read_meta()
    if meta.get("active") == old:
        set_active(new)

def delete_wallet(name: str) -> None:
    names = list_wallet_names()
    if name not in names:
        raise FileNotFoundError(name)
    if len(names) <= 1:
        raise RuntimeError("Cannot delete the last remaining wallet")
    (WALLETS_DIR / f"{name}.json").unlink(missing_ok=False)
    if active_name() == name:
        remaining = list_wallet_names()
        if remaining:
            set_active(remaining[0])
