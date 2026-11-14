import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///" + (Path(__file__).resolve().parents[1] / "detexis.db").as_posix())
options = {}
if DATABASE_URL.startswith("postgresql+psycopg2:"):
    # Send ORM batch updates in one round trip rather than one per event.
    options = {"executemany_mode": "values_plus_batch", "executemany_batch_page_size": 100}
engine = create_engine(DATABASE_URL, pool_pre_ping=True, **options)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
