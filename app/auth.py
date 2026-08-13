import base64
import hashlib
import hmac
import os
import secrets
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User

# PBKDF2-HMAC-SHA256 from the standard library: no extra dependency, and the
# per-user salt means two people with the same password get different hashes.
_PBKDF2_ROUNDS = 260_000


def hash_password(password: str) -> str:
    """Returns 'pbkdf2_sha256$rounds$salt$hash' - everything needed to verify later."""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return "pbkdf2_sha256${}${}${}".format(
        _PBKDF2_ROUNDS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, stored: str) -> bool:
    """Constant-time check so a wrong password cannot be found by timing the reply."""
    try:
        algorithm, rounds, salt_b64, hash_b64 = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        expected = base64.b64decode(hash_b64)
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            base64.b64decode(salt_b64),
            int(rounds),
        )
    except (ValueError, TypeError):
        return False

    return hmac.compare_digest(candidate, expected)


# ---------- Session helpers ----------

SESSION_USER_KEY = "user_id"


def login_session(request: Request, user: User) -> None:
    request.session[SESSION_USER_KEY] = user.id


def logout_session(request: Request) -> None:
    request.session.clear()


def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> Optional[User]:
    """The signed-in user, or None. Never raises - use the guards below to require a role."""
    user_id = request.session.get(SESSION_USER_KEY)
    if not user_id:
        return None

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        # Deactivated or deleted mid-session: drop the stale cookie.
        request.session.clear()
        return None

    return user


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def require_login(user: Optional[User] = Depends(get_current_user)) -> User:
    """Any signed-in account - used for the student pages."""
    if user is None:
        raise _unauthorized("សូមចូលគណនីជាមុនសិន (Please log in first)")
    return user


def require_admin(
    request: Request, user: Optional[User] = Depends(get_current_user)
) -> User:
    """
    Admin-only gate for the dashboard page and every /api/v1/admin route.

    The Admin's own machine (any IP in ADMIN_TRUSTED_IPS) is let straight
    through, so it can browse both the student view and the dashboard without
    signing in. Every other device must log in with an ADMIN account.
    """
    client_ip = request.client.host if request.client else ""
    if client_ip and client_ip in settings.trusted_ip_list:
        return user or _trusted_ip_admin(client_ip)

    if user is None:
        raise _unauthorized("សូមចូលគណនី Admin ជាមុនសិន (Admin login required)")

    if user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="គណនីនេះមិនមានសិទ្ធិ Admin ទេ (This account is not an admin)",
        )

    return user


def _trusted_ip_admin(client_ip: str) -> User:
    """A stand-in Admin for trusted-IP access, so callers always get a User object."""
    placeholder = User(username=f"trusted-ip:{client_ip}", role="ADMIN", is_active=True)
    placeholder.id = 0
    return placeholder


def seed_admin_account(db: Session) -> None:
    """
    Ensures pre-configured default accounts exist in the system:
    1. ADMIN (username: ADMIN, password: syd@168, role: ADMIN)
    2. USER (username: USER, password: user@168, role: STUDENT)
    """
    admin_username = settings.ADMIN_USERNAME or "ADMIN"
    admin_password = settings.ADMIN_PASSWORD or "syd@168"

    # 1. ADMIN Account
    admin_user = db.query(User).filter(func.lower(User.username) == admin_username.lower()).first()
    if not admin_user:
        admin_user = db.query(User).filter(User.role == "ADMIN").first()

    if admin_user:
        admin_user.username = "ADMIN"
        admin_user.password_hash = hash_password(admin_password)
        admin_user.password_plain = admin_password
        admin_user.role = "ADMIN"
        admin_user.is_active = True
    else:
        admin_user = User(
            username="ADMIN",
            password_hash=hash_password(admin_password),
            password_plain=admin_password,
            full_name="System Administrator",
            role="ADMIN",
            is_active=True,
        )
        db.add(admin_user)

    # 2. USER Account (Student)
    student_user = db.query(User).filter(func.lower(User.username) == "user").first()
    student_password = "user@168"
    if student_user:
        student_user.username = "USER"
        student_user.password_hash = hash_password(student_password)
        student_user.password_plain = student_password
        student_user.role = "STUDENT"
        student_user.is_active = True
    else:
        student_user = User(
            username="USER",
            password_hash=hash_password(student_password),
            password_plain=student_password,
            full_name="Standard User",
            role="STUDENT",
            is_active=True,
        )
        db.add(student_user)

    db.commit()
