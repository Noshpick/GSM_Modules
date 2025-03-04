from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker
import datetime

Base = declarative_base()

class Modem(Base):
    __tablename__ = "modems"

    id = Column(Integer, primary_key=True, autoincrement=True)
    port = Column(String, unique=True, nullable=False)
    operator = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    balance = Column(Float, nullable=True)
    last_updated = Column(DateTime, default=datetime.datetime.utcnow)

class SMS(Base):
    __tablename__ = "sms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    modem_id = Column(Integer, ForeignKey("modems.id"), nullable=False)
    sender = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

DATABASE_URL = "sqlite:///gsm_data.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

def init_db():
    Base.metadata.create_all(bind=engine)
