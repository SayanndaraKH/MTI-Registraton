from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    """
    Login account. Every account is created by an Admin - there is no public
    sign-up - so students receive their username and password from the Admin.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=True)     # Google Email address
    password_hash = Column(String(255), nullable=False)
    # Readable copy of the same password, shown in the dashboard so the Admin can
    # re-read and re-send the shared login. Deliberate trade-off: the hash above is
    # what authenticates, but anyone with the database file can read this field.
    password_plain = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)
    phone_number = Column(String(50), nullable=True)
    telegram_username = Column(String(100), nullable=True)
    role = Column(String(20), default="STUDENT")  # ADMIN or STUDENT
    failed_attempts = Column(Integer, default=0)    # Consecutive failed password attempts counter
    lockout_until = Column(DateTime, nullable=True)   # Timestamp until 2-hour login lockout expires
    is_active = Column(Boolean, default=True)
    last_seen = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    price_usd = Column(Float, nullable=False)
    price_khr = Column(Float, nullable=False)
    duration = Column(String(100), default="4 Weeks")
    features = Column(Text, nullable=True) # JSON or newline separated text
    image_url = Column(String(500), nullable=True)
    telegram_group_link = Column(String(500), nullable=True)  # Course-specific Telegram group link
    reg_start_date = Column(String(50), nullable=True)       # Registration Start Date
    reg_end_date = Column(String(50), nullable=True)         # Registration End Date / Deadline
    class_start_date = Column(String(50), nullable=True)     # Class Start Date / Start of Study
    class_time = Column(String(100), nullable=True)          # Class Time / Study Hours (e.g. 7:00 PM - 8:30 PM)
    initial_registered_count = Column(Integer, default=0)    # Offline/Initial student count set by Admin
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    registrations = relationship("Registration", back_populates="course")

class Registration(Base):
    __tablename__ = "registrations"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(String(100), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # the logged-in student who registered
    student_name = Column(String(255), nullable=False)
    phone_number = Column(String(50), nullable=False)
    telegram_username = Column(String(100), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="USD") # USD or KHR
    status = Column(String(50), default="PENDING") # PENDING, SUBMITTED, REJECTED, PAID
    receipt_image_url = Column(String(500), nullable=True) # Payment proof/receipt uploaded by student
    created_at = Column(DateTime, default=datetime.utcnow)

    course = relationship("Course", back_populates="registrations")
    payment = relationship("Payment", back_populates="registration", uselist=False)
    invite = relationship("TelegramInvite", back_populates="registration", uselist=False)

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    registration_id = Column(Integer, ForeignKey("registrations.id"), nullable=False)
    invoice_id = Column(String(100), index=True, nullable=False)
    khqr_md5 = Column(String(100), nullable=True)
    transaction_ref = Column(String(255), nullable=True)
    paid_amount = Column(Float, nullable=False)
    currency = Column(String(10), default="USD")
    status = Column(String(50), default="SUCCESS")
    paid_at = Column(DateTime, default=datetime.utcnow)
    raw_webhook_data = Column(Text, nullable=True)

    registration = relationship("Registration", back_populates="payment")

class TelegramInvite(Base):
    """Records the Telegram group link handed out to a student once Admin accepts their payment."""
    __tablename__ = "telegram_invites"

    id = Column(Integer, primary_key=True, index=True)
    registration_id = Column(Integer, ForeignKey("registrations.id"), nullable=False)
    invite_link = Column(String(500), nullable=False)
    # Handed to the student by the Admin when they were offline at approval time.
    # Entering it once reveals the group link; is_used then closes it for good.
    access_code = Column(String(20), index=True, nullable=True)
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expire_at = Column(DateTime, nullable=True)

    registration = relationship("Registration", back_populates="invite")

class SystemSetting(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, index=True, nullable=False)
    value = Column(Text, nullable=False)
    description = Column(String(255), nullable=True)

class ChatMessage(Base):
    """Live message exchange between student and Admin."""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    student_user_id = Column(Integer, ForeignKey("users.id"), nullable=False) # ties conversation to student
    message = Column(Text, nullable=False)
    sender_role = Column(String(20), default="STUDENT") # STUDENT or ADMIN
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    sender = relationship("User", foreign_keys=[sender_id])
    receiver = relationship("User", foreign_keys=[receiver_id])
    student_user = relationship("User", foreign_keys=[student_user_id])

