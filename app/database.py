from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def run_light_migrations():
    """
    SQLAlchemy's create_all() only creates missing tables, it never alters
    existing ones. This adds any new columns our models gained since the
    last release so an existing course_sales.db keeps working without
    dropping data.
    """
    inspector = inspect(engine)
    if "registrations" not in inspector.get_table_names():
        return

    existing_columns = {col["name"] for col in inspector.get_columns("registrations")}
    if "receipt_image_url" not in existing_columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE registrations ADD COLUMN receipt_image_url VARCHAR(500)"))

    # Links a registration to the student account that created it.
    if "user_id" not in existing_columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE registrations ADD COLUMN user_id INTEGER"))

    # One-time code a student types to unlock the group link after being offline.
    if "telegram_invites" in inspector.get_table_names():
        invite_columns = {col["name"] for col in inspector.get_columns("telegram_invites")}
        if "access_code" not in invite_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE telegram_invites ADD COLUMN access_code VARCHAR(20)"))

    # Readable copy of the login password, so the dashboard can show it again.
    if "users" in inspector.get_table_names():
        user_columns = {col["name"] for col in inspector.get_columns("users")}
        if "password_plain" not in user_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN password_plain VARCHAR(255)"))
        if "last_seen" not in user_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN last_seen DATETIME"))

    # Course-specific Telegram Group link
    if "courses" in inspector.get_table_names():
        course_columns = {col["name"] for col in inspector.get_columns("courses")}
        if "telegram_group_link" not in course_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE courses ADD COLUMN telegram_group_link VARCHAR(500)"))
