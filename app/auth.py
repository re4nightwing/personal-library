"""
Authentication utilities:
- bcrypt password hashing
- TOTP (Google Authenticator) verification
- Signed JWT stored in HttpOnly cookie
"""
import os
import time
import bcrypt
import pyotp
from jose import jwt, JWTError
from fastapi import Request
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.environ["SECRET_KEY"]
ALGORITHM = "HS256"
SESSION_MINUTES = int(os.getenv("SESSION_MINUTES", "60"))
SECURE_COOKIES = os.getenv("SECURE_COOKIES", "true").lower() == "true"
TOTP_ISSUER = os.getenv("TOTP_ISSUER", "HomeLibrary")


# ── Password ──────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── TOTP ──────────────────────────────────────────────────────────────────────

def generate_totp_secret() -> str:
    return pyotp.random_base32()


def get_totp_uri(secret: str, username: str) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=username, issuer_name=TOTP_ISSUER
    )


def verify_totp(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    # valid_window=1 allows ±30s clock skew
    return totp.verify(code, valid_window=1)


# ── JWT Cookie ────────────────────────────────────────────────────────────────

COOKIE_NAME = "session"


def create_session_token(user_id: int, username: str) -> str:
    expire = int(time.time()) + SESSION_MINUTES * 60
    return jwt.encode(
        {"sub": str(user_id), "username": username, "exp": expire},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def set_session_cookie(response, token: str):
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=SECURE_COOKIES,
        samesite="lax",
        max_age=SESSION_MINUTES * 60,
        path="/",
    )


def clear_session_cookie(response):
    response.delete_cookie(key=COOKIE_NAME, path="/")


def _decode_token(request: Request) -> dict | None:
    """Returns user dict from cookie, or None if missing/invalid."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {"id": int(payload["sub"]), "username": payload["username"]}
    except JWTError:
        return None


def get_current_user(request: Request):
    """
    Dependency for page routes: redirects to /login if not authenticated.
    Returns {"id": int, "username": str}
    """
    user = _decode_token(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    return user


def require_user(request: Request) -> dict:
    """
    Dependency for API routes: returns user dict or raises 401 JSON.
    Use this on /api/* endpoints so they return proper JSON errors.
    """
    from fastapi import HTTPException, status
    user = _decode_token(request)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def optional_user(request: Request) -> dict | None:
    """Returns user dict or None — never raises."""
    return _decode_token(request)
