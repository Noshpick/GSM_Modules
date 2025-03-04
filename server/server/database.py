from sqlalchemy.orm import Session
from .models import Modem, SMS, Log, SessionLocal

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def fix_sms_table():
    with SessionLocal() as db:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS sms_fixed (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                modem_id INTEGER NOT NULL,
                sender VARCHAR NOT NULL,
                message TEXT NOT NULL,
                timestamp DATETIME,
                FOREIGN KEY (modem_id) REFERENCES modems (id)
            );
        """))
        db.execute(text("""
            INSERT INTO sms_fixed (modem_id, sender, message, timestamp)
            SELECT modems.id, sms.sender, sms.message, sms.timestamp
            FROM sms
            JOIN modems ON sms.modem_id = modems.port;
        """))
        db.execute(text("DROP TABLE sms;"))
        db.execute(text("ALTER TABLE sms_fixed RENAME TO sms;"))
        db.commit()

def save_modem(db: Session, port, operator, phone, balance):
    modem = db.query(Modem).filter_by(port=port).first()
    if modem:
        modem.operator = operator
        modem.phone = phone
        modem.balance = balance
    else:
        modem = Modem(port=port, operator=operator, phone=phone, balance=balance)
        db.add(modem)
    db.commit()

def save_sms(db: Session, modem_id, sender, message):
    sms = SMS(modem_id=modem_id, sender=sender, message=message)
    db.add(sms)
    db.commit()

def save_log(db: Session, message):
    log = Log(message=message)
    db.add(log)
    db.commit()

def get_all_sms(db: Session):
    return db.query(SMS).all()

def get_all_modems(db: Session):
    return db.query(Modem).all()

def get_logs(db: Session, limit=50):
    return db.query(Log).order_by(Log.timestamp.desc()).limit(limit).all()
