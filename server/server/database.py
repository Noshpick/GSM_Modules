from sqlalchemy.orm import Session
from server.models import Modem, SMS, SessionLocal

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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

def save_sms(db: Session, modem_id, sender, message, timestamp):
    sms = SMS(modem_id=modem_id, sender=sender, message=message, timestamp=timestamp)
    db.add(sms)
    db.commit()
