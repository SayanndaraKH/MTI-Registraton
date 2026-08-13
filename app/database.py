from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

# Some providers (Render, Heroku) hand out "postgres://" URLs, but SQLAlchemy's
# psycopg2 dialect only recognizes "postgresql://".
_database_url = settings.DATABASE_URL or "sqlite:///./course_sales.db"
if _database_url.startswith("postgres://"):
    _database_url = _database_url.replace("postgres://", "postgresql://", 1)

try:
    engine = create_engine(
        _database_url,
        connect_args={"check_same_thread": False} if "sqlite" in _database_url else {},
        pool_pre_ping=True
    )
    with engine.connect() as conn:
        pass
except Exception as e:
    print(f"Warning: Primary database ({_database_url}) connection failed ({e}). Falling back to local SQLite.")
    _database_url = "sqlite:///./course_sales.db"
    engine = create_engine(
        _database_url,
        connect_args={"check_same_thread": False}
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
    try:
        inspector = inspect(engine)
        table_names = inspector.get_table_names()

        # Registrations table migrations
        if "registrations" in table_names:
            existing_columns = {col["name"] for col in inspector.get_columns("registrations")}
            if "receipt_image_url" not in existing_columns:
                try:
                    with engine.begin() as conn:
                        conn.execute(text("ALTER TABLE registrations ADD COLUMN receipt_image_url VARCHAR(500)"))
                except Exception as e:
                    print(f"Migration notice: {e}")
            if "user_id" not in existing_columns:
                try:
                    with engine.begin() as conn:
                        conn.execute(text("ALTER TABLE registrations ADD COLUMN user_id INTEGER"))
                except Exception as e:
                    print(f"Migration notice: {e}")

        # One-time code a student types to unlock the group link after being offline.
        if "telegram_invites" in inspector.get_table_names():
            invite_columns = {col["name"] for col in inspector.get_columns("telegram_invites")}
            if "access_code" not in invite_columns:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE telegram_invites ADD COLUMN access_code VARCHAR(20)"))

        # Readable copy of the login password, email, failed attempts, and lockout timestamp
        if "users" in inspector.get_table_names():
            user_columns = {col["name"] for col in inspector.get_columns("users")}
            if "password_plain" not in user_columns:
                try:
                    with engine.begin() as conn:
                        conn.execute(text("ALTER TABLE users ADD COLUMN password_plain VARCHAR(255)"))
                except Exception as e:
                    print(f"Migration notice: {e}")
            if "last_seen" not in user_columns:
                try:
                    with engine.begin() as conn:
                        conn.execute(text("ALTER TABLE users ADD COLUMN last_seen TIMESTAMP"))
                except Exception as e:
                    print(f"Migration notice: {e}")
            if "email" not in user_columns:
                try:
                    with engine.begin() as conn:
                        conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(255)"))
                except Exception as e:
                    print(f"Migration notice: {e}")
            if "failed_attempts" not in user_columns:
                try:
                    with engine.begin() as conn:
                        conn.execute(text("ALTER TABLE users ADD COLUMN failed_attempts INTEGER DEFAULT 0"))
                except Exception as e:
                    print(f"Migration notice: {e}")
            if "lockout_until" not in user_columns:
                try:
                    with engine.begin() as conn:
                        conn.execute(text("ALTER TABLE users ADD COLUMN lockout_until TIMESTAMP"))
                except Exception as e:
                    print(f"Migration notice: {e}")

        # Course-specific Telegram Group link & registration/class dates
        if "courses" in inspector.get_table_names():
            course_columns = {col["name"] for col in inspector.get_columns("courses")}
            if "telegram_group_link" not in course_columns:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE courses ADD COLUMN telegram_group_link VARCHAR(500)"))
            if "reg_start_date" not in course_columns:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE courses ADD COLUMN reg_start_date VARCHAR(50)"))
            if "reg_end_date" not in course_columns:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE courses ADD COLUMN reg_end_date VARCHAR(50)"))
            if "class_start_date" not in course_columns:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE courses ADD COLUMN class_start_date VARCHAR(50)"))
            if "class_time" not in course_columns:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE courses ADD COLUMN class_time VARCHAR(100)"))
            if "initial_registered_count" not in course_columns:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE courses ADD COLUMN initial_registered_count INTEGER DEFAULT 0"))
    except Exception as err:
        print(f"Migration notice: {err}")
