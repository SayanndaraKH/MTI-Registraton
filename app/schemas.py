from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

class CourseBase(BaseModel):
    title: str
    description: Optional[str] = None
    price_usd: float
    price_khr: float
    duration: Optional[str] = "4 Weeks"
    features: Optional[str] = None
    image_url: Optional[str] = None
    telegram_group_link: Optional[str] = None
    is_active: bool = True

class CourseCreate(CourseBase):
    pass

class CourseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    price_usd: Optional[float] = None
    price_khr: Optional[float] = None
    duration: Optional[str] = None
    features: Optional[str] = None
    image_url: Optional[str] = None
    telegram_group_link: Optional[str] = None
    is_active: Optional[bool] = None

class CourseOut(CourseBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class StudentRegistrationCreate(BaseModel):
    student_name: str
    phone_number: str
    telegram_username: str
    course_id: int
    currency: str = "USD" # USD or KHR

class RegistrationUpdate(BaseModel):
    """Admin edits a student's details from the dashboard. Only the fields sent are changed."""
    student_name: Optional[str] = None
    phone_number: Optional[str] = None
    telegram_username: Optional[str] = None
    course_id: Optional[int] = None
    currency: Optional[str] = None

class RegistrationOut(BaseModel):
    id: int
    invoice_id: str
    student_name: str
    phone_number: str
    telegram_username: str
    course_id: int
    amount: float
    currency: str
    status: str
    created_at: datetime
    course: Optional[CourseOut] = None

    class Config:
        from_attributes = True

class PublicSettingsOut(BaseModel):
    khqr_image_url: str
    telegram_contact_link: str
    contact_phone: str

class SystemSettingSchema(BaseModel):
    key: str
    value: str
    description: Optional[str] = None

    class Config:
        from_attributes = True
