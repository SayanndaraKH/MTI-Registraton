import os
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Registration, Course, SystemSetting, TelegramInvite, Payment
from app.routes.payments import process_successful_payment
from app.schemas import RegistrationUpdate
from app.auth import require_admin
from app.config import settings

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Admin Dashboard"],
    # Applies to every route below, so no admin endpoint can be reached without the password.
    dependencies=[Depends(require_admin)],
)

KHQR_UPLOAD_DIR = os.path.join("static", "uploads")
RECEIPT_UPLOAD_DIR = os.path.join("static", "uploads", "receipts")
COURSE_UPLOAD_DIR = os.path.join("static", "uploads", "courses")
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}

@router.get("/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    total_registrations = db.query(Registration).count()
    paid_registrations = db.query(Registration).filter(Registration.status == "PAID").count()
    pending_registrations = db.query(Registration).filter(Registration.status.in_(["PENDING", "SUBMITTED"])).count()
    total_courses = db.query(Course).count()

    # Calculate Revenue
    usd_revenue = db.query(func.sum(Registration.amount))\
        .filter(Registration.status == "PAID", Registration.currency == "USD")\
        .scalar() or 0.0

    khr_revenue = db.query(func.sum(Registration.amount))\
        .filter(Registration.status == "PAID", Registration.currency == "KHR")\
        .scalar() or 0.0

    return {
        "total_registrations": total_registrations,
        "paid_registrations": paid_registrations,
        "pending_registrations": pending_registrations,
        "total_courses": total_courses,
        "revenue": {
            "usd": round(usd_revenue, 2),
            "khr": round(khr_revenue, 0)
        }
    }

@router.get("/registrations")
def get_registrations_list(
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Registration)

    if status_filter and status_filter.upper() != "ALL":
        query = query.filter(Registration.status == status_filter.upper())

    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter(
            (Registration.student_name.ilike(search_term)) |
            (Registration.phone_number.ilike(search_term)) |
            (Registration.telegram_username.ilike(search_term)) |
            (Registration.invoice_id.ilike(search_term))
        )

    registrations = query.order_by(Registration.id.desc()).all()

    result = []
    for r in registrations:
        invite = db.query(TelegramInvite).filter(TelegramInvite.registration_id == r.id).first()
        result.append({
            "id": r.id,
            "invoice_id": r.invoice_id,
            "student_name": r.student_name,
            "phone_number": r.phone_number,
            "telegram_username": r.telegram_username,
            "course_id": r.course_id,
            "course_title": r.course.title if r.course else "Unknown Course",
            "amount": r.amount,
            "currency": r.currency,
            "status": r.status,
            "receipt_image_url": r.receipt_image_url,
            "invite_link": invite.invite_link if invite else None,
            "access_code": invite.access_code if invite else None,
            "code_used": invite.is_used if invite else False,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S")
        })

    return result

@router.get("/registrations/{reg_id}")
def get_registration_detail(reg_id: int, db: Session = Depends(get_db)):
    """Returns one registration, used to fill the Admin's edit form and receipt preview."""
    reg = db.query(Registration).filter(Registration.id == reg_id).first()
    if not reg:
        raise HTTPException(status_code=404, detail="Registration not found")

    return {
        "id": reg.id,
        "invoice_id": reg.invoice_id,
        "student_name": reg.student_name,
        "phone_number": reg.phone_number,
        "telegram_username": reg.telegram_username,
        "course_id": reg.course_id,
        "course_title": reg.course.title if reg.course else "Unknown Course",
        "amount": reg.amount,
        "currency": reg.currency,
        "status": reg.status,
        "receipt_image_url": reg.receipt_image_url,
        "created_at": reg.created_at.strftime("%Y-%m-%d %H:%M:%S"),
    }

@router.put("/registrations/{reg_id}")
def update_registration(reg_id: int, payload: RegistrationUpdate, db: Session = Depends(get_db)):
    """Admin corrects a student's details. Changing the course or currency re-prices the invoice."""
    reg = db.query(Registration).filter(Registration.id == reg_id).first()
    if not reg:
        raise HTTPException(status_code=404, detail="Registration not found")

    if payload.student_name is not None:
        reg.student_name = payload.student_name.strip()
    if payload.phone_number is not None:
        reg.phone_number = payload.phone_number.strip()
    if payload.telegram_username is not None:
        reg.telegram_username = payload.telegram_username.strip().lstrip("@")
    if payload.course_id is not None:
        course = db.query(Course).filter(Course.id == payload.course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        reg.course_id = course.id
    if payload.currency is not None:
        currency = payload.currency.upper()
        if currency not in ("USD", "KHR"):
            raise HTTPException(status_code=400, detail="Currency must be USD or KHR")
        reg.currency = currency

    # Re-price whenever the course or currency moved, so the amount never drifts from the course.
    if payload.course_id is not None or payload.currency is not None:
        course = db.query(Course).filter(Course.id == reg.course_id).first()
        if course:
            reg.amount = course.price_usd if reg.currency == "USD" else course.price_khr

    db.commit()
    db.refresh(reg)

    return {
        "message": "Registration updated successfully",
        "id": reg.id,
        "student_name": reg.student_name,
        "amount": reg.amount,
        "currency": reg.currency,
    }

@router.delete("/registrations/{reg_id}")
def delete_registration(reg_id: int, db: Session = Depends(get_db)):
    """Admin removes a registration along with its payment, invite and uploaded receipt file."""
    reg = db.query(Registration).filter(Registration.id == reg_id).first()
    if not reg:
        raise HTTPException(status_code=404, detail="Registration not found")

    # Drop the receipt image from disk. basename() keeps a tampered URL inside the uploads dir.
    if reg.receipt_image_url:
        receipt_path = os.path.join(RECEIPT_UPLOAD_DIR, os.path.basename(reg.receipt_image_url))
        if os.path.isfile(receipt_path):
            try:
                os.remove(receipt_path)
            except OSError:
                pass  # A locked or already-removed file must not block the delete.

    # No cascade is configured on these relationships, so clear the children first.
    db.query(Payment).filter(Payment.registration_id == reg.id).delete()
    db.query(TelegramInvite).filter(TelegramInvite.registration_id == reg.id).delete()

    invoice_id = reg.invoice_id
    db.delete(reg)
    db.commit()

    return {"message": f"Registration {invoice_id} deleted successfully"}

@router.post("/registrations/{reg_id}/approve")
def accept_registration(reg_id: int, db: Session = Depends(get_db)):
    """Admin accepts the uploaded receipt: marks payment PAID and unlocks the Telegram group link."""
    reg = db.query(Registration).filter(Registration.id == reg_id).first()
    if not reg:
        raise HTTPException(status_code=404, detail="Registration not found")

    process_successful_payment(db=db, registration=reg, transaction_ref="MANUAL_ADMIN_ACCEPT")

    return {"message": "Registration accepted & Telegram group link issued", "status": "PAID"}

@router.post("/registrations/{reg_id}/reject")
def reject_registration(reg_id: int, db: Session = Depends(get_db)):
    """Admin rejects the uploaded receipt, sending the student back to PENDING so they can re-submit."""
    reg = db.query(Registration).filter(Registration.id == reg_id).first()
    if not reg:
        raise HTTPException(status_code=404, detail="Registration not found")

    if reg.status == "PAID":
        raise HTTPException(status_code=400, detail="Cannot reject a registration that is already paid")

    reg.status = "REJECTED"
    db.commit()

    return {"message": "Registration rejected. Student can re-upload a receipt.", "status": "REJECTED"}

@router.post("/registrations/{reg_id}/receipt")
async def admin_upload_student_receipt(
    reg_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Admin uploads a payment receipt image on behalf of a student.
    Saves the file, updates receipt_image_url, and automatically approves the registration.
    """
    reg = db.query(Registration).filter(Registration.id == reg_id).first()
    if not reg:
        raise HTTPException(status_code=404, detail="Registration not found")

    filename = file.filename or "receipt.jpg"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp", ".pdf"]:
        raise HTTPException(status_code=400, detail="Only JPG, PNG, WEBP or PDF receipt files are accepted")

    safe_name = f"admin_receipt_{reg.id}_{uuid.uuid4().hex[:8]}{ext}"
    save_path = os.path.join(RECEIPT_UPLOAD_DIR, safe_name)
    os.makedirs(RECEIPT_UPLOAD_DIR, exist_ok=True)

    contents = await file.read()
    with open(save_path, "wb") as f:
        f.write(contents)

    from app.routes.registrations import process_receipt_image_to_b64
    reg.receipt_image_url = process_receipt_image_to_b64(contents, file.content_type)

    # Auto approve and process payment (marks status PAID, issues access code & group link)
    process_successful_payment(db=db, registration=reg, transaction_ref="MANUAL_ADMIN_UPLOAD")

    db.commit()
    db.refresh(reg)

    return {
        "message": "Receipt uploaded & registration approved successfully",
        "status": reg.status,
        "receipt_image_url": reg.receipt_image_url,
    }

@router.get("/settings")
def get_system_settings(db: Session = Depends(get_db)):
    db_settings = db.query(SystemSetting).all()
    setting_map = {s.key: s.value for s in db_settings}

    return {
        "KHQR_IMAGE_URL": setting_map.get("KHQR_IMAGE_URL", settings.KHQR_IMAGE_URL),
        "TELEGRAM_CONTACT_LINK": setting_map.get("TELEGRAM_CONTACT_LINK", settings.TELEGRAM_CONTACT_LINK),
        "TELEGRAM_GROUP_LINK": setting_map.get("TELEGRAM_GROUP_LINK", settings.TELEGRAM_GROUP_LINK),
        "CONTACT_PHONE": setting_map.get("CONTACT_PHONE", settings.CONTACT_PHONE),
    }

@router.post("/settings")
def update_system_settings(settings_dict: dict, db: Session = Depends(get_db)):
    for key, value in settings_dict.items():
        if value is not None:
            val_str = str(value).strip()
            existing = db.query(SystemSetting).filter(SystemSetting.key == key).first()
            if existing:
                existing.value = val_str
            else:
                new_setting = SystemSetting(key=key, value=val_str)
                db.add(new_setting)
    db.commit()
    return {"message": "Settings updated successfully"}

@router.post("/course-image")
async def upload_course_image(file: UploadFile = File(...)):
    """
    Stores a course cover image and returns its URL. Kept separate from the
    course record so a brand-new course, which has no id yet, can be given a
    picture before it is saved.
    """
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Only JPG, PNG or WEBP images are accepted")

    os.makedirs(COURSE_UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1] or ".png"
    safe_name = f"course_{uuid.uuid4().hex[:8]}{ext}"

    with open(os.path.join(COURSE_UPLOAD_DIR, safe_name), "wb") as buffer:
        buffer.write(await file.read())

    return {"message": "Course image uploaded successfully", "image_url": f"/static/uploads/courses/{safe_name}"}

@router.post("/settings/khqr-upload")
async def upload_khqr_image(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Admin uploads the merchant's KHQR payment image, shown to every student at checkout."""
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Only JPG, PNG or WEBP images are accepted")

    os.makedirs(KHQR_UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1] or ".png"
    safe_name = f"khqr_{uuid.uuid4().hex[:8]}{ext}"
    dest_path = os.path.join(KHQR_UPLOAD_DIR, safe_name)

    contents = await file.read()
    with open(dest_path, "wb") as buffer:
        buffer.write(contents)

    from app.routes.registrations import process_receipt_image_to_b64
    image_url = process_receipt_image_to_b64(contents, file.content_type)

    existing = db.query(SystemSetting).filter(SystemSetting.key == "KHQR_IMAGE_URL").first()
    if existing:
        existing.value = image_url
    else:
        db.add(SystemSetting(key="KHQR_IMAGE_URL", value=image_url))
    db.commit()

    return {"message": "KHQR image uploaded successfully", "khqr_image_url": image_url}
