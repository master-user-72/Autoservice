from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=True)

DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

WEB_DIR = ROOT / "web"
DB_PATH = DATA_DIR / "agent.db"

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8080"))

LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
LLM_FOLDER_ID = os.getenv("LLM_FOLDER_ID", "").strip()
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini").strip()
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "").strip()
QWEN_BASE_URL = os.getenv(
    "QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
).rstrip("/")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-plus").strip()
QWEN_FALLBACK = os.getenv("QWEN_FALLBACK", "1").strip() != "0"
_raw_provider = os.getenv("LLM_PROVIDER", "").strip().lower()
if _raw_provider:
    LLM_PROVIDER = _raw_provider
elif not LLM_API_KEY and not QWEN_API_KEY:
    LLM_PROVIDER = "off"
elif "yandex" in LLM_BASE_URL.lower() or LLM_FOLDER_ID:
    LLM_PROVIDER = "yandex"
elif "dashscope" in QWEN_BASE_URL.lower() or "qwen" in QWEN_BASE_URL.lower():
    LLM_PROVIDER = "qwen"
else:
    LLM_PROVIDER = "openai"
LLM_NONSTANDARD_ONLY = os.getenv("LLM_NONSTANDARD_ONLY", "1").strip() != "0"

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")

CITY = os.getenv("CITY", "Тюмень").strip() or "Тюмень"
VIN_DECODE_LIVE = os.getenv("VIN_DECODE_LIVE", "1").strip() != "0"

SUPPLIER_ADAPTER = os.getenv("SUPPLIER_ADAPTER", "live").strip().lower()
SUPPLIER_NAME = os.getenv("SUPPLIER_NAME", "Поставщики Тюмень")
SUPPLIER_LOGIN_URL = os.getenv("SUPPLIER_LOGIN_URL", "").strip()
SUPPLIER_USER = os.getenv("SUPPLIER_USER", "").strip()
SUPPLIER_PASSWORD = os.getenv("SUPPLIER_PASSWORD", "")
SUPPLIER_STATE_PATH = Path(os.getenv("SUPPLIER_STATE_PATH", str(DATA_DIR / "supplier_state.json")))
if not SUPPLIER_STATE_PATH.is_absolute():
    SUPPLIER_STATE_PATH = ROOT / SUPPLIER_STATE_PATH

ROSSKO_BASE = os.getenv("ROSSKO_BASE", "https://tmn.rossko.ru").rstrip("/")
ROSSKO_KEY1 = os.getenv("ROSSKO_KEY1", "").strip()
ROSSKO_KEY2 = os.getenv("ROSSKO_KEY2", "").strip()
ROSSKO_USER = os.getenv("ROSSKO_USER", "").strip() or SUPPLIER_USER
ROSSKO_PASSWORD = os.getenv("ROSSKO_PASSWORD", "") or SUPPLIER_PASSWORD
ROSSKO_DELIVERY_ID = os.getenv("ROSSKO_DELIVERY_ID", "000000001").strip()

PARTKOM_BASE = os.getenv("PARTKOM_BASE", "https://part-kom.ru").rstrip("/")
PARTKOM_API = os.getenv("PARTKOM_API", "https://b2b.part-kom.ru/engine/api/v3").rstrip("/")
PARTKOM_USER = os.getenv("PARTKOM_USER", "").strip()
PARTKOM_PASSWORD = os.getenv("PARTKOM_PASSWORD", "")
PARTKOM_PICKUP = os.getenv("PARTKOM_PICKUP", "Тюмень, ул. Малышева, д. 2А стр. 4")

EMEX_BASE = os.getenv("EMEX_BASE", "https://emex.ru").rstrip("/")
EMEX_USER = os.getenv("EMEX_USER", "").strip()
EMEX_PASSWORD = os.getenv("EMEX_PASSWORD", "")
EMEX_PICKUP = os.getenv("EMEX_PICKUP", "Тюмень")

EXIST_BASE = os.getenv("EXIST_BASE", "https://www.exist.ru").rstrip("/")
EXIST_USER = os.getenv("EXIST_USER", "").strip()
EXIST_PASSWORD = os.getenv("EXIST_PASSWORD", "")
EXIST_OFFICE = os.getenv("EXIST_OFFICE", "Тюмень")
