import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
WEBAPP_ROOT = ROOT.parent
load_dotenv(WEBAPP_ROOT / ".env")
load_dotenv(ROOT / ".env")

RUNS_DIR = ROOT / "runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
OPENAI_VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "").strip() or OPENAI_MODEL
PYTHON_BIN = os.getenv("PYTHON_BIN", "python").strip()

MAX_ITERATIONS = 3
EXEC_TIMEOUT_SEC = 60
MAX_CSV_BYTES = 5 * 1024 * 1024
PROMPT_DIR = ROOT / "prompts"
