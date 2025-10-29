#!/usr/bin/env bash
set -euo pipefail
cd /home/admin/Desktop/AIRGAPPED_3.0

# wait for framebuffer and touch to exist
for i in {1..60}; do
  [[ -e /dev/fb0 ]] && break
  sleep 0.5
done

export PYTHONUNBUFFERED=1
# If you use a venv, activate it here:
# source /home/admin/venv/bin/activate

exec /usr/bin/python3 /home/admin/Desktop/AIRGAPPED_3.0/main_wallet.py
