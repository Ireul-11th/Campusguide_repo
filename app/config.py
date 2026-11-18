import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "campusguide.db"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _f(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


LLM_PROVIDER = os.getenv("LLM_PROVIDER", "none").strip().lower()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "").strip()
TOP_K = int(_f("TOP_K", 5))
MIN_COVERAGE = _f("MIN_COVERAGE", 0.4)
EMBEDDING_MIN_SIM = _f("EMBEDDING_MIN_SIM", 0.45)
REL_SCORE = _f("REL_SCORE", 0.45)
EXTRACT_MIN_SCORE = _f("EXTRACT_MIN_SCORE", 0.35)
EXTRACT_MAX_MISSING = _f("EXTRACT_MAX_MISSING", 0.3)
EXTRACT_DEBUG = _f("EXTRACT_DEBUG", "") not in ("", "0")
EXTRACT_MAX_UNITS = int(_f("EXTRACT_MAX_UNITS", 5))

HOST = os.getenv("APP_HOST", "127.0.0.1").strip()   # 0.0.0.0 để máy khác trong LAN vào được
PORT = int(_f("APP_PORT", 8000))

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin").strip().lower() or "admin"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")          # chỉ dùng để tạo quản trị viên đầu tiên
ADMIN_FORCE_RESET = os.getenv("ADMIN_FORCE_RESET", "0").strip().lower() in ("1", "true", "yes")
SESSION_DAYS = int(_f("SESSION_DAYS", 7))
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "0").strip().lower() in ("1", "true", "yes")   # bật khi chạy qua HTTPS
MAX_UPLOAD_MB = int(_f("MAX_UPLOAD_MB", 25))

ALLOWED_EXT = {".pdf", ".docx", ".txt", ".md"}

VECTOR_STORE = os.getenv("VECTOR_STORE", "sqlite").strip().lower()   # sqlite | chroma
RERANK_MODEL = os.getenv("RERANK_MODEL", "").strip()
RERANK_MIN_SCORE = _f("RERANK_MIN_SCORE", 0.0)
OCR_ENABLED = os.getenv("OCR", "0").strip().lower() in ("1", "true", "yes")
OCR_LANG = os.getenv("OCR_LANG", "vie+eng").strip()
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "").strip()
