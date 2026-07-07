from sqlalchemy import create_engine, Column, Integer, String, Float, Text, DateTime, JSON, func
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime, timezone

DATABASE_URL = "sqlite+aiosqlite:///./outreach.db"

class Base(DeclarativeBase):
    pass

class Scrape(Base):
    __tablename__ = "scrapes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    status = Column(String(20), default="pending")
    category = Column(String(200), nullable=False)
    city = Column(String(200), nullable=False)
    country = Column(String(10), nullable=False)
    max_results = Column(Integer, default=20)
    apify_run_id = Column(String(100), default="")
    total_leads = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scrape_id = Column(Integer, nullable=False)
    name = Column(String(300), default="")
    email = Column(String(300), default="")
    phone = Column(String(100), default="")
    website = Column(String(500), default="")
    rating = Column(Float, default=0.0)
    address = Column(Text, default="")
    profile_json = Column(JSON, default=dict)

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lead_id = Column(Integer, nullable=False)
    scrape_id = Column(Integer, nullable=False)
    provider = Column(String(20), default="openrouter")
    model_used = Column(String(200), default="")
    webhook_url = Column(String(500), default="")
    custom_instructions = Column(Text, default="")
    content = Column(Text, default="")
    subject = Column(String(500), default="")
    status = Column(String(20), default="draft")
    error = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class Setting(Base):
    __tablename__ = "settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, default="")

class TaskProgress(Base):
    __tablename__ = "task_progress"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_type = Column(String(50), nullable=False)
    ref_id = Column(Integer, default=0)
    total = Column(Integer, default=0)
    completed = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    status = Column(String(20), default="running")
    error = Column(Text, default="")

def init_db():
    engine = create_engine("sqlite:///./outreach.db", echo=False)
    Base.metadata.create_all(engine)
    return engine
