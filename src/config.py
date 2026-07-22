import os

from dotenv import load_dotenv

load_dotenv()

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "gemini")  # "gemini" or "groq"

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
MAX_PRIORITY_FILES = int(os.environ.get("MAX_PRIORITY_FILES", "15"))
