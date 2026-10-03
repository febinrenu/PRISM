import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
DEMO_DIR = BASE_DIR / "data" / "demo"
STORE_DIR = BASE_DIR / "data" / "store"
DEMO_PDF_NAME = "income_tax_2025.pdf"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
STORE_DIR.mkdir(parents=True, exist_ok=True)

_DEFAULT_CORS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:3002",
    "http://127.0.0.1:3002",
]
# Comma-separated extra origins for deployments (e.g. the Vercel frontend URL).
CORS_ORIGINS = _DEFAULT_CORS + [
    o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()
]

MAX_FILE_SIZE_MB = 50
# Uploads with more pages than this are rejected before analysis starts.
MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", "2000"))

# --- Phase 2: LLM extraction (Ollama) ---
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi3.5:3.8b")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
LLM_TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_S", "60"))
LLM_BATCH_SIZE = int(os.getenv("LLM_BATCH_SIZE", "5"))
LLM_MAX_CANDIDATES = int(os.getenv("LLM_MAX_CANDIDATES", "40"))
# Token budget for a full extraction JSON. 300 truncated real legal clauses
# mid-string (condition+action+consequence+reasoning+lists), which broke
# json.loads and surfaced as "extraction failed to parse".
LLM_NUM_PREDICT = int(os.getenv("LLM_NUM_PREDICT", "800"))
# Structured extraction is decoded greedily with a fixed seed so a rerun of the
# same (model, prompt, clause) reproduces the same rule.
EXTRACTION_TEMPERATURE = float(os.getenv("EXTRACTION_TEMPERATURE", "0.0"))
LLM_SEED = int(os.getenv("LLM_SEED", "42"))
# Ollama's default context (2048) silently drops the start of long prompts.
LLM_NUM_CTX = int(os.getenv("LLM_NUM_CTX", "4096"))
# Clause characters sent to the extractor; longer clauses are flagged
# `input_truncated` on the extraction record.
LLM_MAX_CLAUSE_CHARS = int(os.getenv("LLM_MAX_CLAUSE_CHARS", "3000"))

# --- Phase 2: LIME explainability ---
# 50 samples gave seed-to-seed top-8 token overlap of only 0.10-0.18 (Jaccard);
# 500 is the floor for a stable explanation on 70-110 word clauses.
LIME_NUM_SAMPLES = int(os.getenv("LIME_NUM_SAMPLES", "500"))
LIME_NUM_FEATURES = int(os.getenv("LIME_NUM_FEATURES", "12"))

# --- Phase 3: simulation calibration ---
# "nsso"   → per-type log-normal income calibrated to published Indian data
# "legacy" → the original illustrative log-uniform ranges (kept for ablation)
SIM_CALIBRATION = os.getenv("SIM_CALIBRATION", "nsso")

# Segmentation:
#   "statute"    → the statute structure parser (sections, sub-sections, clauses,
#                  provisos, schedules); falls back to "structural" for PDFs that
#                  are not statutes
#   "structural" → regex/layout segmenter
#   "semantic"   → structural + a MiniLM embedding-cohesion boundary check
SEGMENTATION_MODE = os.getenv("SEGMENTATION_MODE", "statute")

# --- Phase 3: LLM backend abstraction (Module D/E/F) ---
# Which generator serves free-form/RAG/chat calls:
#   "ollama"           → local Phi-3.5-mini (OLLAMA_MODEL)          [dev default]
#   "ollama_finetuned" → local QLoRA-merged model (OLLAMA_FT_MODEL) [Phase 3 Module E]
#   "groq"             → Groq cloud (GROQ_MODEL, needs GROQ_API_KEY)[production]
LLM_BACKEND = os.getenv("LLM_BACKEND", "ollama")
# Free-form/RAG generation is a bigger prompt (retrieved context) + longer output
# than a single extraction, and the first call cold-loads the model. Give it a
# generous ceiling; streaming resets the read clock per token so this is mostly
# a guard on first-token latency.
LLM_GEN_TIMEOUT_S = float(os.getenv("LLM_GEN_TIMEOUT_S", "300"))
OLLAMA_FT_MODEL = os.getenv("OLLAMA_FT_MODEL", "prism-legal")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_URL = os.getenv("GROQ_URL", "https://api.groq.com/openai/v1/chat/completions")
# Google Gemini (frontier-model baseline and silver labeller). Model names are
# pinned so results stay attributable; on the free tier only Flash models
# have quota.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
GEMINI_URL = os.getenv("GEMINI_URL", "https://generativelanguage.googleapis.com/v1beta")

# --- Phase 3: RAG corpus (Module D) ---
CHROMA_DIR = BASE_DIR / "data" / "chromadb"
CORPUS_COLLECTION = os.getenv("CORPUS_COLLECTION", "prism_legal_corpus")
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "8"))

# --- Phase 3: public API + auth (Module F) ---
DATABASE_URL = os.getenv("DATABASE_URL", "")  # Neon Postgres; empty → SQLite fallback
JWT_SECRET = os.getenv("JWT_SECRET", "prism-dev-secret-change-in-production")
# First user (or any existing user) whose email matches is promoted to admin on
# register/login — the bootstrap for reaching the /admin dashboard.
PRISM_ADMIN_EMAIL = os.getenv("PRISM_ADMIN_EMAIL", "")
API_RATE_LIMIT = os.getenv("API_RATE_LIMIT", "100/hour")
R2_ENDPOINT = os.getenv("R2_ENDPOINT", "")
R2_ACCESS_KEY = os.getenv("CLOUDFLARE_R2_KEY", "")
R2_SECRET_KEY = os.getenv("CLOUDFLARE_R2_SECRET", "")
R2_BUCKET = os.getenv("R2_BUCKET", "prism-uploads")
