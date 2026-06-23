import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Local dev: defaults to a SQLite file so each developer can work without
# touching the shared Render Postgres. Set DATABASE_URL to the Render
# Postgres connection string when running against the shared environment.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ajo.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
