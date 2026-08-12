import secrets
import string
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import Course, Registration, Payment, TelegramInvite, SystemSetting
from app.config import settings

# Ambiguous characters (0/O, 1/I) are left out so a code read over Telegram
# cannot be mistyped into a different valid code.
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_access_code(db: Session, length: int = 8) -> str:
    """A short unique code the student types to unlock their group link."""
    while True:
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))
        if not db.query(TelegramInvite).filter(TelegramInvite.access_code == code).first():
            return code


def get_group_link(db: Session, course_id: Optional[int] = None) -> str:
    """
    Retrieves the Telegram group link.
    PRIORITY 1: Course-specific telegram_group_link (if set on the registered Course).
    PRIORITY 2: SystemSetting TELEGRAM_GROUP_LINK stored in DB.
    PRIORITY 3: Fallback default settings.TELEGRAM_GROUP_LINK.
    """
    if course_id:
        course = db.query(Course).filter(Course.id == course_id).first()
        if course and course.telegram_group_link and course.telegram_group_link.strip():
            return course.telegram_group_link.strip()

    row = db.query(SystemSetting).filter(SystemSetting.key == "TELEGRAM_GROUP_LINK").first()
    if row and row.value and row.value.strip():
        return row.value.strip()

    return settings.TELEGRAM_GROUP_LINK


def process_successful_payment(
    db: Session,
    registration: Registration,
    transaction_ref: str = "MANUAL_ADMIN_ACCEPT"
) -> bool:
    """
    Marks a registration as PAID once Admin reviews the uploaded receipt and
    accepts it, then hands out the private Telegram group link assigned to that specific course.
    """
    if registration.status == "PAID":
        return True  # Already processed

    registration.status = "PAID"

    db_payment = Payment(
        registration_id=registration.id,
        invoice_id=registration.invoice_id,
        transaction_ref=transaction_ref,
        paid_amount=registration.amount,
        currency=registration.currency,
        status="SUCCESS",
        paid_at=datetime.utcnow()
    )
    db.add(db_payment)

    invite = db.query(TelegramInvite).filter(TelegramInvite.registration_id == registration.id).first()
    group_link = get_group_link(db, course_id=registration.course_id)

    if invite:
        invite.invite_link = group_link
        if not invite.access_code:
            invite.access_code = generate_access_code(db)
    else:
        db.add(TelegramInvite(
            registration_id=registration.id,
            invite_link=group_link,
            access_code=generate_access_code(db),
            is_used=False,
            created_at=datetime.utcnow()
        ))

    db.commit()
    return True
