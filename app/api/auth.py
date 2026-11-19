from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from app.auth import (
    SESSION_COOKIE,
    SESSION_MAX_AGE,
    GoogleVerifier,
    InvalidGoogleToken,
    get_google_verifier,
    is_allowed,
    make_session_token,
    require_session,
)

router = APIRouter()


class GoogleSignIn(BaseModel):
    credential: str


@router.post("/auth/google")
async def sign_in(
    body: GoogleSignIn,
    response: Response,
    verifier: GoogleVerifier = Depends(get_google_verifier),
) -> dict:
    try:
        identity = await verifier.verify(body.credential)
    except InvalidGoogleToken:
        raise HTTPException(status_code=401, detail="Invalid Google token")
    if not identity.email_verified or not is_allowed(identity.email):
        raise HTTPException(status_code=403, detail="This account is not allowed")
    email = identity.email.strip().lower()
    response.set_cookie(
        SESSION_COOKIE,
        make_session_token(email),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=False,  # the app may be served over plain http in development
        path="/",
    )
    return {"email": email}


@router.get("/auth/me")
async def who_am_i(email: str = Depends(require_session)) -> dict:
    return {"email": email}


@router.post("/auth/logout")
async def sign_out(response: Response) -> dict:
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"signedIn": False}
