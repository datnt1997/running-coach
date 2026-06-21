from dotenv import load_dotenv
import os

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
AI_PROVIDER = os.getenv("AI_PROVIDER", "anthropic")

STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
STRAVA_WEBHOOK_VERIFY_TOKEN = os.getenv("STRAVA_WEBHOOK_VERIFY_TOKEN")
STRAVA_REDIRECT_URI = os.getenv("STRAVA_REDIRECT_URI")


def validate_config():
    missing = []
    if not ANTHROPIC_API_KEY and AI_PROVIDER == "anthropic":
        missing.append("ANTHROPIC_API_KEY")
    if not DATABASE_URL:
        missing.append("DATABASE_URL")
    if not STRAVA_CLIENT_ID:
        missing.append("STRAVA_CLIENT_ID")
    if not STRAVA_CLIENT_SECRET:
        missing.append("STRAVA_CLIENT_SECRET")
    if not STRAVA_WEBHOOK_VERIFY_TOKEN:
        missing.append("STRAVA_WEBHOOK_VERIFY_TOKEN")
    if not STRAVA_REDIRECT_URI:
        missing.append("STRAVA_REDIRECT_URI")
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")
