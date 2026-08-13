import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "Cambodian Course KHQR Sales Automation"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # SQLite by default for local dev. In production this should point at a
    # persistent database (e.g. Render PostgreSQL) - a free-tier web service's
    # local disk is wiped on every deploy and on every idle spin-down/up, so a
    # local sqlite file there loses all data (including the seeded Admin
    # account) on every restart.
    DATABASE_URL: str = "sqlite:///./course_sales.db"

    # Admin Dashboard login. Students must never be able to reach /admin,
    # so these gate the dashboard page and every admin API route.
    ADMIN_USERNAME: str = "ADMIN"
    ADMIN_PASSWORD: str = "syd@168"

    # Signs the session cookie. Changing it logs everyone out.
    SECRET_KEY: str = ""

    # First-time visitors may pick their own username and password at the login
    # form; that first attempt creates the account. Turn off to make the Admin
    # the only one who can create accounts.
    ALLOW_SELF_REGISTER: bool = True
    MIN_USERNAME_LENGTH: int = 3
    MIN_PASSWORD_LENGTH: int = 4

    # Comma-separated IPs that reach the dashboard without logging in. Empty by
    # default: any address listed grants admin access to ANY browser coming from
    # it, whichever account is signed in, so only set this if you accept that.
    ADMIN_TRUSTED_IPS: str = ""

    @property
    def trusted_ip_list(self) -> set:
        return {ip.strip() for ip in self.ADMIN_TRUSTED_IPS.split(",") if ip.strip()}

    # KHQR payment image, uploaded by the admin (static image shown to every student)
    KHQR_IMAGE_URL: str = ""

    # Link opened so the student can send their payment code to the Admin on Telegram
    TELEGRAM_CONTACT_LINK: str = "https://t.me/your_telegram_username"

    # Private course group link, only revealed to the student once Admin accepts the payment
    TELEGRAM_GROUP_LINK: str = "https://t.me/+demo_course_group"

    # Contact phone number shown to students for support
    CONTACT_PHONE: str = "012 345 678"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()
