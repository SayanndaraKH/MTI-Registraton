import os
import uuid
import shutil
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Course, Registration, TelegramInvite, SystemSetting, User
from app.schemas import StudentRegistrationCreate
from app.auth import require_login
from app.config import settings

router = APIRouter(prefix="/api/v1/registrations", tags=["Registrations"])

RECEIPT_UPLOAD_DIR = os.path.join("static", "uploads", "receipts")
ALLOWED_RECEIPT_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}


from typing import Optional

def get_group_link(db: Session, course_id: Optional[int] = None) -> str:
    from app.routes.payments import get_group_link as get_payment_group_link
    return get_payment_group_link(db, course_id=course_id)


def generate_invoice_id() -> str:
    """Generates unique invoice ID like INV-20260811-A1B2."""
    date_str = datetime.utcnow().strftime("%Y%m%d")
    unique_suffix = uuid.uuid4().hex[:4].upper()
    return f"INV-{date_str}-{unique_suffix}"


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
def register_student(
    reg_in: StudentRegistrationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    # Verify course exists and is active
    course = db.query(Course).filter(Course.id == reg_in.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="វគ្គសិក្សានេះមិនត្រូវបានស្វែងរកឃើញឡើយ (Course not found)")
    if not course.is_active:
        raise HTTPException(status_code=400, detail="វគ្គសិក្សានេះមិនទាន់បើកទទួលការចុះឈ្មោះនៅឡើយទេ - Coming Soon (Course is inactive)")

    # Generate unique invoice ID
    invoice_id = generate_invoice_id()

    # Determine amount & currency
    currency = reg_in.currency.upper()
    if currency == "KHR":
        amount = course.price_khr
    else:
        currency = "USD"
        amount = course.price_usd

    # Create DB registration
    db_reg = Registration(
        invoice_id=invoice_id,
        user_id=user.id,  # ties the invoice to the signed-in student account
        student_name=reg_in.student_name.strip(),
        phone_number=reg_in.phone_number.strip(),
        telegram_username=reg_in.telegram_username.strip(),
        course_id=course.id,
        amount=amount,
        currency=currency,
        status="PENDING"
    )
    db.add(db_reg)
    db.commit()
    db.refresh(db_reg)

    return {
        "registration_id": db_reg.id,
        "invoice_id": invoice_id,
        "student_name": db_reg.student_name,
        "telegram_username": db_reg.telegram_username,
        "course_title": course.title,
        "amount": amount,
        "currency": currency,
        "status": db_reg.status,
        "created_at": db_reg.created_at.isoformat()
    }


@router.get("/my-registrations")
def get_my_registrations(db: Session = Depends(get_db), user: User = Depends(require_login)):
    """Returns registrations belonging to the currently logged in student."""
    user_regs = db.query(Registration).filter(Registration.user_id == user.id).order_by(Registration.id.desc()).all()
    results = []
    for r in user_regs:
        invite = db.query(TelegramInvite).filter(TelegramInvite.registration_id == r.id).first()
        course_link = get_group_link(db, course_id=r.course_id)
        results.append({
            "id": r.id,
            "invoice_id": r.invoice_id,
            "course_title": r.course.title if r.course else "Course",
            "amount": r.amount,
            "currency": r.currency,
            "status": r.status,
            "receipt_image_url": r.receipt_image_url,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M"),
            "invite_link": course_link if (r.status == "PAID" and invite) else None
        })
    return results


@router.post("/redeem-code")
def redeem_access_code(payload: dict, db: Session = Depends(get_db), user: User = Depends(require_login)):
    """
    Unlocks the Telegram group link for a student who was offline when Admin
    approved their payment. Entering the code reveals the group link.
    """
    code = str(payload.get("code", "")).strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="សូមបញ្ចូលលេខកូដ (Please enter your access code)")

    invite = db.query(TelegramInvite).filter(TelegramInvite.access_code == code).first()
    if not invite:
        raise HTTPException(status_code=404, detail="លេខកូដមិនត្រឹមត្រូវ (Invalid access code)")

    reg = db.query(Registration).filter(Registration.id == invite.registration_id).first()
    if not reg or reg.status != "PAID":
        raise HTTPException(status_code=400, detail="ការទូទាត់មិនទាន់ត្រូវបានអនុម័ត (Payment is not approved yet)")

    current_group_link = get_group_link(db, course_id=reg.course_id)

    if invite.is_used:
        # If the logged-in student owns this registration, let them see their link again
        if reg.user_id == user.id:
            return {
                "message": "ជោគជ័យ! សូមចូលរួមក្រុមឥឡូវនេះ (Success - join the group now)",
                "invoice_id": reg.invoice_id,
                "course_title": reg.course.title if reg.course else "",
                "invite_link": current_group_link,
            }
        raise HTTPException(
            status_code=409,
            detail="លេខកូដនេះត្រូវបានប្រើរួចហើយ សូមទាក់ទង Admin (This code has already been used)",
        )

    invite.is_used = True  # spent
    db.commit()

    return {
        "message": "ជោគជ័យ! សូមចូលរួមក្រុមឥឡូវនេះ (Success - join the group now)",
        "invoice_id": reg.invoice_id,
        "course_title": reg.course.title if reg.course else "",
        "invite_link": current_group_link,
    }


@router.get("/{invoice_id}/status")
def check_registration_status(
    invoice_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    # Login required: this reveals the private group link once Admin approves,
    # so a guessed invoice ID alone must not be enough to read it.
    reg = db.query(Registration).filter(Registration.invoice_id == invoice_id).first()
    if not reg:
        raise HTTPException(status_code=404, detail="Invoice ID not found")

    response_data = {
        "invoice_id": reg.invoice_id,
        "status": reg.status,
        "student_name": reg.student_name,
        "amount": reg.amount,
        "currency": reg.currency,
        "course_title": reg.course.title if reg.course else "Course",
        "receipt_image_url": reg.receipt_image_url,
        "invite_link": None
    }

    if reg.status == "PAID":
        invite = db.query(TelegramInvite).filter(TelegramInvite.registration_id == reg.id).first()
        if invite:
            response_data["invite_link"] = get_group_link(db, course_id=reg.course_id)

    return response_data

    return response_data


@router.post("/{invoice_id}/receipt")
async def upload_payment_receipt(
    invoice_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    """Student uploads a screenshot/photo of their KHQR payment as proof, awaiting Admin acceptance."""
    reg = db.query(Registration).filter(Registration.invoice_id == invoice_id).first()
    if not reg:
        raise HTTPException(status_code=404, detail="Invoice ID not found")

    if reg.status == "PAID":
        raise HTTPException(status_code=400, detail="This registration is already confirmed as paid")

    if file.content_type not in ALLOWED_RECEIPT_TYPES:
        raise HTTPException(status_code=400, detail="Only JPG, PNG, WEBP or PDF receipts are accepted")

    os.makedirs(RECEIPT_UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    safe_name = f"{invoice_id}_{uuid.uuid4().hex[:8]}{ext}"
    dest_path = os.path.join(RECEIPT_UPLOAD_DIR, safe_name)

    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    reg.receipt_image_url = f"/static/uploads/receipts/{safe_name}"
    reg.status = "SUBMITTED"
    db.commit()
    db.refresh(reg)

    return {
        "message": "Receipt uploaded. Waiting for Admin to accept your payment.",
        "invoice_id": reg.invoice_id,
        "status": reg.status,
        "receipt_image_url": reg.receipt_image_url
    }
