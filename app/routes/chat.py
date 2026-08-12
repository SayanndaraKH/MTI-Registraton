from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.database import get_db
from app.models import User, ChatMessage, Registration
from app.auth import require_login, require_admin

router = APIRouter(prefix="/api/v1/chat", tags=["Live Chat"])

ONLINE_THRESHOLD_SECONDS = 90


def touch_last_seen(db: Session, user: User) -> None:
    """Updates user's last_seen timestamp so online presence is accurate."""
    user.last_seen = datetime.utcnow()
    db.commit()


def is_user_online(user: Optional[User]) -> bool:
    if not user or not user.last_seen:
        return False
    diff = (datetime.utcnow() - user.last_seen).total_seconds()
    return diff <= ONLINE_THRESHOLD_SECONDS


class SendMessageSchema(BaseModel):
    message: str
    student_user_id: Optional[int] = None


@router.get("/status")
def get_chat_status(
    db: Session = Depends(get_db),
    user: User = Depends(require_login)
):
    """
    Returns Admin online/offline status and student unread count.
    Used by student floating chat widget to display 🟢 Online or ⚪ Offline.
    """
    touch_last_seen(db, user)

    # Check if any active Admin is currently online
    admin_users = db.query(User).filter(User.role == "ADMIN", User.is_active == True).all()
    admin_online = any(is_user_online(a) for a in admin_users)

    # Get student unread message count
    unread_count = 0
    if user.role != "ADMIN":
        unread_count = db.query(ChatMessage).filter(
            ChatMessage.student_user_id == user.id,
            ChatMessage.sender_role == "ADMIN",
            ChatMessage.is_read == False
        ).count()

    return {
        "admin_online": admin_online,
        "unread_count": unread_count,
        "current_user_id": user.id,
        "role": user.role
    }


@router.post("/send")
def send_message(
    payload: SendMessageSchema,
    db: Session = Depends(get_db),
    user: User = Depends(require_login)
):
    touch_last_seen(db, user)

    msg_text = payload.message.strip()
    if not msg_text:
        raise HTTPException(status_code=400, detail="សារមិនអាចទទេបានទេ (Message cannot be empty)")

    if user.role == "ADMIN":
        if not payload.student_user_id:
            raise HTTPException(status_code=400, detail="Target student_user_id is required for Admin reply")
        target_student = db.query(User).filter(User.id == payload.student_user_id).first()
        if not target_student:
            raise HTTPException(status_code=404, detail="Student user not found")

        student_user_id = target_student.id
        receiver_id = target_student.id
        sender_role = "ADMIN"
    else:
        student_user_id = user.id
        receiver_id = None  # Sent to Admin team
        sender_role = "STUDENT"

    chat_msg = ChatMessage(
        sender_id=user.id,
        receiver_id=receiver_id,
        student_user_id=student_user_id,
        message=msg_text,
        sender_role=sender_role,
        is_read=False,
        created_at=datetime.utcnow()
    )
    db.add(chat_msg)
    db.commit()
    db.refresh(chat_msg)

    return {
        "id": chat_msg.id,
        "sender_id": chat_msg.sender_id,
        "student_user_id": chat_msg.student_user_id,
        "sender_name": user.full_name or user.username,
        "sender_role": chat_msg.sender_role,
        "message": chat_msg.message,
        "is_read": chat_msg.is_read,
        "created_at": chat_msg.created_at.strftime("%H:%M · %d/%m/%Y")
    }


@router.get("/messages")
def get_messages(
    student_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_login)
):
    touch_last_seen(db, user)

    if user.role == "ADMIN":
        if not student_id:
            return []
        target_student_id = student_id
        # Mark unread messages sent by student as read
        db.query(ChatMessage).filter(
            ChatMessage.student_user_id == target_student_id,
            ChatMessage.sender_role == "STUDENT",
            ChatMessage.is_read == False
        ).update({"is_read": True})
        db.commit()
    else:
        target_student_id = user.id
        # Mark unread messages sent by Admin as read
        db.query(ChatMessage).filter(
            ChatMessage.student_user_id == target_student_id,
            ChatMessage.sender_role == "ADMIN",
            ChatMessage.is_read == False
        ).update({"is_read": True})
        db.commit()

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.student_user_id == target_student_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )

    result = []
    for m in messages:
        sender_name = "Admin" if m.sender_role == "ADMIN" else (m.sender.full_name or m.sender.username if m.sender else "Student")
        result.append({
            "id": m.id,
            "sender_id": m.sender_id,
            "student_user_id": m.student_user_id,
            "sender_name": sender_name,
            "sender_role": m.sender_role,
            "message": m.message,
            "is_read": m.is_read,
            "created_at": m.created_at.strftime("%H:%M · %d/%m/%Y")
        })

    return result


@router.get("/conversations")
def get_conversations(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """Admin dashboard endpoint: lists all student chat conversations with online status."""
    touch_last_seen(db, admin_user)

    # Find all unique student_user_ids who have messages
    student_ids = db.query(ChatMessage.student_user_id).distinct().all()
    student_ids = [s[0] for s in student_ids]

    conversations = []
    for sid in student_ids:
        student = db.query(User).filter(User.id == sid).first()
        if not student:
            continue

        latest_msg = (
            db.query(ChatMessage)
            .filter(ChatMessage.student_user_id == sid)
            .order_by(ChatMessage.created_at.desc())
            .first()
        )

        unread_count = (
            db.query(ChatMessage)
            .filter(
                ChatMessage.student_user_id == sid,
                ChatMessage.sender_role == "STUDENT",
                ChatMessage.is_read == False
            )
            .count()
        )

        # Retrieve user's registration course titles if available
        user_regs = db.query(Registration).filter(Registration.user_id == sid).all()
        courses_summary = ", ".join([r.course.title for r in user_regs if r.course]) if user_regs else "គ្មានវគ្គសិក្សា"

        conversations.append({
            "student_id": student.id,
            "username": student.username,
            "full_name": student.full_name or student.username,
            "phone_number": student.phone_number or "—",
            "telegram_username": student.telegram_username or "—",
            "courses_summary": courses_summary,
            "unread_count": unread_count,
            "is_online": is_user_online(student),
            "latest_message": latest_msg.message if latest_msg else "",
            "latest_time": latest_msg.created_at.strftime("%H:%M · %d/%m") if latest_msg else "",
            "sort_time": latest_msg.created_at if latest_msg else datetime.min
        })

    # Sort conversations by latest message timestamp DESC
    conversations.sort(key=lambda x: x["sort_time"], reverse=True)
    for c in conversations:
        c.pop("sort_time", None)

    return conversations


@router.delete("/messages/{message_id}")
def delete_message(
    message_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_login)
):
    """Delete a single chat message."""
    touch_last_seen(db, user)

    msg = db.query(ChatMessage).filter(ChatMessage.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="មិនរកឃើញសារនេះទេ (Message not found)")

    # Permission check: Admin can delete any message. Student can delete messages in their thread.
    if user.role != "ADMIN" and msg.student_user_id != user.id:
        raise HTTPException(status_code=403, detail="គ្មានសិទ្ធិលុបសារនេះទេ (Unauthorized)")

    db.delete(msg)
    db.commit()

    return {"detail": "លុបសារបានជោគជ័យ (Message deleted successfully)"}


@router.delete("/history")
def clear_chat_history(
    student_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_login)
):
    """Clear all chat history for a student or student conversation."""
    touch_last_seen(db, user)

    if user.role == "ADMIN":
        if not student_id:
            raise HTTPException(status_code=400, detail="student_id is required for Admin to clear history")
        target_student_id = student_id
    else:
        target_student_id = user.id

    db.query(ChatMessage).filter(ChatMessage.student_user_id == target_student_id).delete()
    db.commit()

    return {"detail": "បានលុបប្រវត្តិឆាតទាំងអស់ជោគជ័យ (Chat history cleared successfully)"}
