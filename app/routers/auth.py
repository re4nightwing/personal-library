"""
Auth routes: login form + logout.
Two-step: password first, then TOTP pin.
Rate-limited to prevent brute force.
"""
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_pool
from app.auth import (
    verify_password, verify_totp,
    create_session_token, set_session_cookie, clear_session_cookie,
    optional_user,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
limiter = Limiter(key_func=get_remote_address)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, user=Depends(optional_user)):
    if user:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": None,
        "step": "password",
    })


@router.post("/login", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(default=None),
    totp_code: str = Form(default=None),
    step: str = Form(default="password"),
):
    pool = await get_pool()
    error_resp = lambda msg, st: templates.TemplateResponse("login.html", {
        "request": request, "error": msg, "step": st,
        "username": username,
    })

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, username, password_hash, totp_secret FROM users WHERE username = $1",
            username,
        )

    if not row:
        return error_resp("Invalid credentials.", "password")

    if step == "password":
        if not verify_password(password, row["password_hash"]):
            return error_resp("Invalid credentials.", "password")
        # Password OK → ask for TOTP
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": None,
            "step": "totp",
            "username": username,
        })

    elif step == "totp":
        if not verify_totp(row["totp_secret"], totp_code or ""):
            return error_resp("Invalid authenticator code.", "totp")
        # All good — issue session
        token = create_session_token(row["id"], row["username"])
        response = RedirectResponse("/", status_code=302)
        set_session_cookie(response, token)
        return response

    return error_resp("Bad request.", "password")


@router.post("/logout")
async def logout(request: Request):
    response = RedirectResponse("/login", status_code=302)
    clear_session_cookie(response)
    return response
