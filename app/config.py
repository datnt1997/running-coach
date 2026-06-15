from dotenv import load_dotenv
import os

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
AI_PROVIDER = os.getenv("AI_PROVIDER", "anthropic")


def validate_config():
    missing = []
    if not ANTHROPIC_API_KEY and AI_PROVIDER == "anthropic":
        missing.append("ANTHROPIC_API_KEY")
    if not DATABASE_URL:
        missing.append("DATABASE_URL")
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")
