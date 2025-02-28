import sqlite3
import time
import re

DB_FILE = "sms_data.db"


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        port TEXT,
        modem_number TEXT,
        sender TEXT,
        message TEXT,  -- Здесь будут только цифры
        timestamp TEXT,
        last_update INTEGER
    )
    """)

    conn.commit()
    conn.close()


def extract_numbers(text):
    numbers = re.findall(r'\d+', text)
    return " ".join(numbers) if numbers else None


def save_sms(port, modem_number, sender, message, timestamp):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO sms (port, modem_number, sender, message, timestamp, last_update)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (port, modem_number, sender, message, timestamp, int(time.time())))

    conn.commit()
    conn.close()


def get_latest_sms(modem_number, sender_phone):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
    SELECT message FROM sms
    WHERE modem_number = ? AND sender = ?
    ORDER BY timestamp DESC
    LIMIT 1
    """, (modem_number, sender_phone))

    sms = cursor.fetchone()
    conn.close()

    return sms[0] if sms else None
