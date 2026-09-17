import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"
SEED_DB_PATH = BASE_DIR / "data" / "seed" / "kiosco_merlo_sepa.sqlite"
DEV_DB_PATH = INSTANCE_DIR / "kiosco_dev.sqlite"

# Timeout de espera cuando SQLite está ocupado (ms).
SQLITE_BUSY_TIMEOUT_MS = 5000


class Config:
    SECRET_KEY = os.environ.get("KIOSCO_SECRET_KEY", "dev-kiosco-control-cambiar")
    WTF_CSRF_ENABLED = True
    DATABASE_PATH = DEV_DB_PATH
    SEED_DATABASE_PATH = SEED_DB_PATH
    PAGE_SIZE = 50
    SQLITE_BUSY_TIMEOUT_MS = SQLITE_BUSY_TIMEOUT_MS
