import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./openpts.db")

# Neon (and older Heroku/Render) emit "postgres://" — SQLAlchemy requires "postgresql://"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if "sqlite" in DATABASE_URL:
    # Local development — SQLite, single-threaded access is fine
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
else:
    # Production (Vercel serverless + Neon Postgres).
    # NullPool opens/closes a connection per request instead of maintaining a pool.
    # This prevents "too many connections" errors when many serverless function
    # instances run concurrently — each one is short-lived and doesn't hold a slot.
    engine = create_engine(DATABASE_URL, poolclass=NullPool)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()