import os
import secrets
from typing import Optional

from fastapi import FastAPI, Request, Depends, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine, Base, get_db, run_light_migrations
from app.models import Course, SystemSetting, User
from app.routes import courses, registrations, admin, users, chat
from app.auth import (
    require_admin,
    get_current_user,
    require_login,
    verify_password,
    hash_password,
    login_session,
    logout_session,
    seed_admin_account,
)

# Create database tables & apply lightweight schema migrations
Base.metadata.create_all(bind=engine)
run_light_migrations()

app = FastAPI(
    title=settings.APP_NAME,
    description="Course Sales System with KHQR Payment Upload & Telegram Group Access",
    version="1.0.0"
)

# Signed session cookie backing the login form. A generated fallback keeps the
# app runnable if SECRET_KEY is missing, at the cost of logging everyone out on restart.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY or secrets.token_urlsafe(32),
    session_cookie="mti_session",
    same_site="lax",
    https_only=False,  # served over plain HTTP on the LAN
    # max_age=None makes this a browser-session cookie: closing the browser
    # signs the student out, so re-opening the link always asks for the login.
    max_age=None,
)

# Ensure directories exist
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/js", exist_ok=True)
os.makedirs("static/uploads/receipts", exist_ok=True)
os.makedirs("templates", exist_ok=True)

# Mount static directory & templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Include Routers
app.include_router(courses.router)
app.include_router(registrations.router)
app.include_router(admin.router)
app.include_router(users.router)
app.include_router(chat.router)

def seed_initial_courses(db: Session):
    """Seed initial sample courses if database is brand new."""
    if db.query(Course).count() == 0:
        sample_courses = [
            Course(
                title="Python Programming & Automation Masterclass",
                description="រៀនសរសេរកូដ Python ពីកម្រិតដំបូងរហូតដល់អាចបង្កើត Bot និងប្រព័ន្ធស្វ័យប្រវត្តិកម្មបានដោយខ្លួនឯង។ Master Python from scratch to build automated bots and web systems.",
                price_usd=15.0,
                price_khr=61500.0,
                duration="4 សប្តាហ៍ (4 Weeks)",
                features="Python Fundamentals\nTelegram Bot Automation\nFastAPI & Database\nKHQR Payment Integration",
                image_url="https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=600&auto=format&fit=crop&q=60",
                is_active=True
            ),
            Course(
                title="Web Development with FastAPI & React",
                description="បង្កើត Web Application ទំនើប និងលឿនបំផុតជាមួយ FastAPI Backend & Modern Web Interfaces។ Build modern high-speed web apps.",
                price_usd=25.0,
                price_khr=102500.0,
                duration="6 សប្តាហ៍ (6 Weeks)",
                features="FastAPI RESTful APIs\nPostgreSQL & SQLite\nJWT Authentication\nDeployment on Cloud",
                image_url="https://images.unsplash.com/photo-1555066931-4365d14bab8c?w=600&auto=format&fit=crop&q=60",
                is_active=True
            ),
            Course(
                title="Telegram Bot & API Integration Mastery",
                description="រៀបចំ Telegram Bot សម្រាប់អាជីវកម្ម ការលក់វគ្គ និងការផ្ញើសារប្រព័ន្ធស្វ័យប្រវត្តិ។ Build interactive business bots for Telegram.",
                price_usd=19.0,
                price_khr=77900.0,
                duration="3 សប្តាហ៍ (3 Weeks)",
                features="Telegram Bot API & Webhooks\nDynamic Invite Link Manager\nAutomated Customer Support\nIntegration with KHQR Payment",
                image_url="https://images.unsplash.com/photo-1618401471353-b98aedd04e11?w=600&auto=format&fit=crop&q=60",
                is_active=True
            )
        ]
        db.add_all(sample_courses)
        db.commit()

@app.on_event("startup")
def on_startup():
    db = next(get_db())
    try:
        seed_initial_courses(db)
        seed_admin_account(db)
    finally:
        db.close()

from fastapi import Response

@app.get("/api/v1/settings/public")
def get_public_settings(response: Response, db: Session = Depends(get_db)):
    """
    Non-sensitive settings needed to render the checkout page:
    the KHQR image to scan, the Telegram link to send the payment code,
    and a support phone number. The private group link is deliberately
    excluded here — it's only revealed via /registrations/{id}/status
    once Admin accepts the payment.
    """
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    setting_map = {s.key: s.value for s in db.query(SystemSetting).all()}
    return {
        "khqr_image_url": setting_map.get("KHQR_IMAGE_URL", settings.KHQR_IMAGE_URL),
        "telegram_contact_link": setting_map.get("TELEGRAM_CONTACT_LINK", settings.TELEGRAM_CONTACT_LINK),
        "contact_phone": setting_map.get("CONTACT_PHONE", settings.CONTACT_PHONE),
    }

# ---------- Login / logout ----------

@app.get("/login", response_class=HTMLResponse)
def page_login(request: Request, next: str = "/", error: Optional[str] = None):
    return templates.TemplateResponse(
        request,
        "login.html",
        {"settings": settings, "next": next, "error": error},
    )

@app.post("/login")
def do_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
    db: Session = Depends(get_db),
):
    username = username.strip()

    def reject(message: str):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"settings": settings, "next": next, "error": message},
            status_code=401,
        )

    # Case-insensitive: SQLite compares TEXT as case-sensitive by default, so
    # without this, "Admin" and "admin" would be treated as different accounts
    # and typing the wrong case would silently self-register a shadow account.
    user = db.query(User).filter(func.lower(User.username) == username.lower()).first()

    if user is None:
        # First visit: the name is free, so this attempt claims it and becomes
        # the account. Every later login must match what was saved here.
        if not settings.ALLOW_SELF_REGISTER:
            return reject("ឈ្មោះគណនី ឬលេខសម្ងាត់មិនត្រឹមត្រូវ (Invalid username or password)")

        if len(username) < settings.MIN_USERNAME_LENGTH:
            return reject(f"ឈ្មោះគណនីត្រូវមានយ៉ាងតិច {settings.MIN_USERNAME_LENGTH} តួ (Username too short)")
        if len(password) < settings.MIN_PASSWORD_LENGTH:
            return reject(f"លេខសម្ងាត់ត្រូវមានយ៉ាងតិច {settings.MIN_PASSWORD_LENGTH} តួ (Password too short)")

        # Self-registered accounts are always students; ADMIN is granted only
        # by an existing Admin from the dashboard.
        user = User(
            username=username,
            password_hash=hash_password(password),
            password_plain=password,
            full_name=username,
            role="STUDENT",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    else:
        # Known account: the saved password must match exactly.
        if not user.is_active or not verify_password(password, user.password_hash):
            return reject("ឈ្មោះគណនី ឬលេខសម្ងាត់មិនត្រឹមត្រូវ (Invalid username or password)")

    login_session(request, user)

    # Only allow same-site paths, so ?next= cannot bounce a user to another site.
    target = next if next.startswith("/") and not next.startswith("//") else "/"
    if user.role == "ADMIN" and target == "/":
        target = "/admin"

    return RedirectResponse(url=target, status_code=303)

@app.get("/logout")
def do_logout(request: Request):
    logout_session(request)
    return RedirectResponse(url="/login", status_code=303)

# HTML Pages Routes
@app.get("/", response_class=HTMLResponse)
def page_home(request: Request, db: Session = Depends(get_db), user: User = Depends(require_login)):
    """
    The address handed out to students. Login is required here too, so opening
    the link lands on the login form first and never on the course list.
    """
    all_courses = db.query(Course).order_by(Course.id.desc()).all()
    return templates.TemplateResponse(
        request,
        "index.html",
        {"courses": all_courses, "settings": settings, "user": user},
    )

@app.get("/checkout/{invoice_id}", response_class=HTMLResponse)
def page_checkout(
    invoice_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    return templates.TemplateResponse(
        request,
        "checkout.html",
        {"invoice_id": invoice_id, "settings": settings, "user": user},
    )

@app.get("/register", response_class=HTMLResponse)
@app.get("/student", response_class=HTMLResponse)
def page_student(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """
    Dedicated student link to hand out (/student or /register). Same page as "/",
    kept separate so the address shared with students never hints at /admin.
    Students must sign in with the account the Admin created for them.
    """
    active_courses = db.query(Course).filter(Course.is_active == True).order_by(Course.id.desc()).all()
    return templates.TemplateResponse(
        request,
        "index.html",
        {"courses": active_courses, "settings": settings, "user": user},
    )

@app.get("/admin", response_class=HTMLResponse)
def page_admin(request: Request, _admin: User = Depends(require_admin)):
    """Admin-only: anyone else is bounced to the login form, never shown the dashboard."""
    return templates.TemplateResponse(request, "admin.html", {"settings": settings})

@app.exception_handler(401)
@app.exception_handler(403)
async def auth_redirect_handler(request: Request, exc):
    """
    Send browsers to the login form instead of showing raw JSON, but let API
    callers (fetch/XHR) keep the status code so their error handling still works.
    """
    wants_html = "text/html" in request.headers.get("accept", "")
    if wants_html and request.method == "GET":
        return RedirectResponse(url=f"/login?next={request.url.path}", status_code=303)

    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
