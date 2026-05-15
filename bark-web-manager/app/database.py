from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'data', 'bark.db')}"

os.makedirs(os.path.join(BASE_DIR, 'data'), exist_ok=True)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class PushRecord(Base):
    __tablename__ = "push_records"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, nullable=False, index=True)
    title = Column(String, nullable=True)
    subtitle = Column(String, nullable=True)
    body = Column(Text, nullable=True)
    url = Column(String, nullable=True)
    group_name = Column(String, nullable=True, index=True)
    icon = Column(String, nullable=True)
    sound = Column(String, nullable=True)
    level = Column(String, nullable=True)
    is_archive = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(Integer, default=0)  # 0: pending, 1: success, 2: failed


class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(String, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        default_settings = {
            "bark_server_url": "http://localhost:8080",
            "cleanup_days": "30",
            "cleanup_enabled": "true"
        }
        for key, value in default_settings.items():
            existing = db.query(Setting).filter(Setting.key == key).first()
            if not existing:
                db.add(Setting(key=key, value=value))
        db.commit()
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
