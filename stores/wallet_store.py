# wallet_store.py
import json, shutil
from pathlib import Path
from datetime import datetime

LEGACY_PATH   = Path("wallet.json")
WALLETS_DIR   = Path("wallets")
META_PATH     = Path("wallet_meta.json")
DEFAULT_WALLET_NAME = "default"

def _now_iso(): return datetime.utcnow().isoformat()+"Z"

def _safe_read_json(path: Path, fallback):
    try:
        if path.exists():
            return json.loads(path.read_text() or "{}")
    except Exception:
        pass
    return fallback

def _safe_write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2))

def _wallet_path(name: str) -> Path:
    return WALLETS_DIR / f"{name}.json"

def _load_meta():
    WALLETS_DIR.mkdir(exist_ok=True)
    meta = _safe_read_json(META_PATH, {})
    existing = sorted([p.stem for p in WALLETS_DIR.glob("*.json")])
    if not existing:
        if LEGACY_PATH.exists():
            try:
                shutil.copy2(LEGACY_PATH, _wallet_path(DEFAULT_WALLET_NAME))
            except Exception:
                _safe_write_json(_wallet_path(DEFAULT_WALLET_NAME), {"seed_phrase":"", "accounts":[]})
            meta["active"] = DEFAULT_WALLET_NAME
            _safe_write_json(META_PATH, meta); return meta
        _safe_write_json(_wallet_path(DEFAULT_WALLET_NAME), {"seed_phrase":"", "accounts":[]})
        meta["active"] = DEFAULT_WALLET_NAME
        _safe_write_json(META_PATH, meta); return meta
    active = meta.get("active")
    if not active or not _wallet_path(active).exists():
        meta["active"] = existing[0]; _safe_write_json(META_PATH, meta)
    return meta

def _ensure_meta_ready(): return _load_meta()

# ---- Public API ----
def list_wallets():
    _ensure_meta_ready()
    return sorted([p.stem for p in WALLETS_DIR.glob("*.json")])

def get_active_wallet_name() -> str:
    meta=_ensure_meta_ready(); return meta.get("active", DEFAULT_WALLET_NAME)

def set_active_wallet(name: str):
    if not name: return
    _ensure_meta_ready()
    if not _wallet_path(name).exists():
        _safe_write_json(_wallet_path(name), {"seed_phrase":"", "accounts":[]})
    meta=_safe_read_json(META_PATH,{})
    meta["active"]=name; _safe_write_json(META_PATH, meta)

def ensure_wallet_exists(name: str):
    p=_wallet_path(name)
    if not p.exists():
        _safe_write_json(p, {"seed_phrase":"", "accounts":[]})

def delete_wallet(name: str) -> bool:
    name=(name or "").strip()
    if not name: return False
    _ensure_meta_ready()
    wallets = list_wallets()
    if name not in wallets: return False
    p=_wallet_path(name)
    try:
        p.unlink()
    except Exception:
        return False
    remaining = list_wallets()
    active=get_active_wallet_name()
    if not remaining:
        ensure_wallet_exists(DEFAULT_WALLET_NAME)
        set_active_wallet(DEFAULT_WALLET_NAME)
    else:
        if active==name:
            set_active_wallet(remaining[0])
    return True

def rename_wallet(old: str, new: str) -> bool:
    old = (old or "").strip()
    new = (new or "").strip()
    if not old or not new: return False
    _ensure_meta_ready()
    src=_wallet_path(old); dst=_wallet_path(new)
    if not src.exists(): return False
    if dst.exists(): return False
    try:
        src.rename(dst)
    except Exception:
        return False
    # update active reference if needed
    meta=_safe_read_json(META_PATH,{})
    if meta.get("active")==old:
        meta["active"]=new; _safe_write_json(META_PATH, meta)
    return True

def load_wallet():
    name=get_active_wallet_name()
    data=_safe_read_json(_wallet_path(name), {"seed_phrase":"", "accounts":[]})
    data.setdefault("seed_phrase",""); data.setdefault("accounts",[])
    return data

def save_wallet(data: dict):
    name=get_active_wallet_name()
    _safe_write_json(_wallet_path(name), data or {"seed_phrase":"", "accounts":[]})

def upsert_wallet(seed_phrase: str, accounts: list):
    name=get_active_wallet_name()
    current=_safe_read_json(_wallet_path(name), {})
    current["seed_phrase"]=seed_phrase or current.get("seed_phrase","")
    current["accounts"]=accounts or current.get("accounts", [])
    current.setdefault("created_at", _now_iso()); current["updated_at"]=_now_iso()
    _safe_write_json(_wallet_path(name), current)
