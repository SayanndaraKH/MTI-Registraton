from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Registration
from app.auth import require_admin, hash_password

# Only an Admin may create accounts - there is no public sign-up anywhere.
router = APIRouter(
    prefix="/api/v1/admin/users",
    tags=["User Accounts"],
    dependencies=[Depends(require_admin)],
)


class UserCreate(BaseModel):
    username: str
    password: str
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    telegram_username: Optional[str] = None
    role: str = "STUDENT"


class UserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None  # only rewritten when a new one is supplied
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    telegram_username: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


def _serialize(u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "full_name": u.full_name,
        "phone_number": u.phone_number,
        "telegram_username": u.telegram_username,
        "password_plain": u.password_plain,  # shown in the dashboard so Admin can re-send it
        "role": u.role,
        "is_active": u.is_active,
        "created_at": u.created_at.strftime("%Y-%m-%d %H:%M:%S") if u.created_at else None,
    }


@router.get("")
def list_users(search: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(User)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            (User.username.ilike(term))
            | (User.full_name.ilike(term))
            | (User.phone_number.ilike(term))
        )
    # Oldest account first, so the numbering reads 1, 2, 3... down the table.
    return [_serialize(u) for u in query.order_by(User.id.asc()).all()]


@router.get("/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _serialize(user)


@router.post("", status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    username = payload.username.strip()
    if not username or not payload.password:
        raise HTTPException(status_code=400, detail="ត្រូវការឈ្មោះគណនី និងលេខសម្ងាត់ (Username and password are required)")

    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=409, detail="ឈ្មោះគណនីនេះមានរួចហើយ (Username already exists)")

    role = payload.role.upper()
    if role not in ("ADMIN", "STUDENT"):
        raise HTTPException(status_code=400, detail="Role must be ADMIN or STUDENT")

    user = User(
        username=username,
        password_hash=hash_password(payload.password),
        password_plain=payload.password,
        full_name=(payload.full_name or "").strip() or None,
        phone_number=(payload.phone_number or "").strip() or None,
        telegram_username=(payload.telegram_username or "").strip().lstrip("@") or None,
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {"message": "បានបង្កើតគណនីជោគជ័យ (Account created)", **_serialize(user)}


@router.put("/{user_id}")
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.username is not None:
        new_name = payload.username.strip()
        clash = db.query(User).filter(User.username == new_name, User.id != user_id).first()
        if clash:
            raise HTTPException(status_code=409, detail="ឈ្មោះគណនីនេះមានរួចហើយ (Username already exists)")
        user.username = new_name

    if payload.password:  # blank means "leave the current password alone"
        user.password_hash = hash_password(payload.password)
        user.password_plain = payload.password

    if payload.full_name is not None:
        user.full_name = payload.full_name.strip() or None
    if payload.phone_number is not None:
        user.phone_number = payload.phone_number.strip() or None
    if payload.telegram_username is not None:
        user.telegram_username = payload.telegram_username.strip().lstrip("@") or None

    if payload.role is not None:
        role = payload.role.upper()
        if role not in ("ADMIN", "STUDENT"):
            raise HTTPException(status_code=400, detail="Role must be ADMIN or STUDENT")
        _guard_last_admin(db, user, new_role=role, new_active=user.is_active)
        user.role = role

    if payload.is_active is not None:
        _guard_last_admin(db, user, new_role=user.role, new_active=payload.is_active)
        user.is_active = payload.is_active

    db.commit()
    db.refresh(user)

    return {"message": "បានរក្សាទុកគណនីជោគជ័យ (Account updated)", **_serialize(user)}


@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    _guard_last_admin(db, user, new_role="STUDENT", new_active=False)

    # Keep the student's paid history; just unlink it from the deleted account.
    db.query(Registration).filter(Registration.user_id == user.id).update({"user_id": None})

    username = user.username
    db.delete(user)
    db.commit()

    return {"message": f"បានលុបគណនី {username} (Account deleted)"}


def _guard_last_admin(db: Session, user: User, new_role: str, new_active: bool) -> None:
    """Refuses any change that would leave the system with no way for an Admin to log in."""
    if user.role != "ADMIN":
        return
    if new_role == "ADMIN" and new_active:
        return

    remaining = (
        db.query(User)
        .filter(User.role == "ADMIN", User.is_active == True, User.id != user.id)
        .count()
    )
    if remaining == 0:
        raise HTTPException(
            status_code=400,
            detail="នេះជាគណនី Admin ចុងក្រោយ មិនអាចលុប ឬបិទបានទេ (Cannot remove the last active admin)",
        )
