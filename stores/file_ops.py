# file_ops.py
from pathlib import Path

FILES = ["wallet.json", "pin.json"]  # keep networks.json unless you want a full wipe

def wipe_files():
    for f in FILES:
        p=Path(f)
        if p.exists():
            try: p.unlink()
            except Exception: pass
