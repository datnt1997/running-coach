from dotenv import load_dotenv
import os
import pathlib

load_dotenv()

FRONTEND_DIST = pathlib.Path(__file__).parent.parent / "frontend" / "dist"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
AI_PROVIDER = os.getenv("AI_PROVIDER", "anthropic")
CHAT_AI_PROVIDER = os.getenv("CHAT_AI_PROVIDER") or None
# The Plan chat's edit step only; falls back to CHAT_AI_PROVIDER, then AI_PROVIDER.
PLAN_EDIT_AI_PROVIDER = os.getenv("PLAN_EDIT_AI_PROVIDER") or None
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
APP_LANGUAGE = os.getenv("APP_LANGUAGE", "vi")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
ALLOWED_EMAILS = os.getenv("ALLOWED_EMAILS", "")
SESSION_SECRET = os.getenv("SESSION_SECRET")
# The session cookie is Secure (https only) unless this is explicitly false, e.g. http dev
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").strip().lower() not in ("false", "0", "no")

STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
STRAVA_WEBHOOK_VERIFY_TOKEN = os.getenv("STRAVA_WEBHOOK_VERIFY_TOKEN")
STRAVA_REDIRECT_URI = os.getenv("STRAVA_REDIRECT_URI")


def validate_config():
    from app.i18n import LANGUAGES

    if APP_LANGUAGE not in LANGUAGES:
        raise RuntimeError(
            f"Unsupported APP_LANGUAGE '{APP_LANGUAGE}'. Registered: {', '.join(sorted(LANGUAGES))}"
        )
    missing = []
    providers = {
        AI_PROVIDER, CHAT_AI_PROVIDER or AI_PROVIDER, PLAN_EDIT_AI_PROVIDER or CHAT_AI_PROVIDER or AI_PROVIDER,
    }
    if not ANTHROPIC_API_KEY and "anthropic" in providers:
        missing.append("ANTHROPIC_API_KEY")
    if not GEMINI_API_KEY and "gemini" in providers:
        missing.append("GEMINI_API_KEY")
    if not DATABASE_URL:
        missing.append("DATABASE_URL")
    if not GOOGLE_CLIENT_ID:
        missing.append("GOOGLE_CLIENT_ID")
    if not any(e.strip() for e in ALLOWED_EMAILS.split(",")):
        missing.append("ALLOWED_EMAILS")
    if not SESSION_SECRET:
        missing.append("SESSION_SECRET")
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
    if SESSION_SECRET == "change_me" or len(SESSION_SECRET) < 32:
        raise RuntimeError(
            "SESSION_SECRET is the placeholder or shorter than 32 characters. Generate one: "
            'python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )
