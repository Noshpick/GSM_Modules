import logging
import sqlite3
import tornado.ioloop
import tornado.web
import tornado.websocket
import json
import time
import asyncio
from modem.modem_manager import ModemManager

modem_cache = None
last_cache_update = 0

def init_db():
    conn = sqlite3.connect("modem_data.db")
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS modems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            port TEXT UNIQUE,
            operator TEXT,
            phone TEXT,
            balance TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            port TEXT,
            sender TEXT,
            message TEXT,
            timestamp TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT,
            timestamp TEXT
        )
    ''')

    conn.commit()
    conn.close()

init_db()
modem_manager = ModemManager()
asyncio.create_task(modem_manager.refresh_modems())

log_clients = set()

async def save_modem_data():
    conn = sqlite3.connect("modem_data.db")
    cursor = conn.cursor()

    await modem_manager.refresh_modems()

    for port in modem_manager.modems.keys():
        balance = await asyncio.to_thread(modem_manager.get_balance, port)
        operator = await asyncio.to_thread(modem_manager.get_operator, port)
        phone = await asyncio.to_thread(modem_manager.get_phone_number, port)

        cursor.execute('''
            INSERT INTO modems (port, operator, phone, balance) 
            VALUES (?, ?, ?, ?) 
            ON CONFLICT(port) DO UPDATE SET 
                operator=excluded.operator, 
                phone=excluded.phone, 
                balance=excluded.balance
        ''', (port, operator, phone, balance))

    conn.commit()
    conn.close()

async def save_sms_data():
    conn = sqlite3.connect("modem_data.db")
    cursor = conn.cursor()

    await modem_manager.refresh_modems()

    for port in modem_manager.modems.keys():
        sms_data = await asyncio.to_thread(modem_manager.get_sms, port)
        for sms in sms_data["sms"]:
            cursor.execute('''
                INSERT INTO sms (port, sender, message, timestamp) 
                VALUES (?, ?, ?, ?)
            ''', (port, sms["sender"], sms["message"], sms["timestamp"]))

    conn.commit()
    conn.close()

def save_log(message):
    conn = sqlite3.connect("modem_data.db")
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO logs (message, timestamp) VALUES (?, datetime('now'))
    ''', (message,))

    conn.commit()
    conn.close()

def get_logs():
    conn = sqlite3.connect("modem_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT message FROM logs ORDER BY id DESC LIMIT 50")
    logs = [row[0] for row in cursor.fetchall()]
    conn.close()
    return logs

class LogsWebSocketHandler(tornado.websocket.WebSocketHandler):
    def check_origin(self, origin):
        return True

    def open(self):
        log_clients.add(self)
        self.write_message(json.dumps({"status": "CONNECTED", "logs": get_logs()}))

    def on_close(self):
        log_clients.discard(self)

class SMSHandler(tornado.web.RequestHandler):
    def get(self):
        conn = sqlite3.connect("modem_data.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sms ORDER BY timestamp DESC")
        sms_list = [{"port": row[1], "sender": row[2], "message": row[3], "timestamp": row[4]} for row in cursor.fetchall()]
        conn.close()
        self.write({"status": "SUCCESS", "data": sms_list})

class AuditHandler(tornado.web.RequestHandler):
    def get(self):
        global modem_cache, last_cache_update
        if modem_cache and (time.time() - last_cache_update) < 30:
            logging.info("Используем кешированные данные.")
            self.write({"status": "SUCCESS", "data": modem_cache})
            return

        conn = sqlite3.connect("modem_data.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM modems")
        modem_cache = [{"port": row[1], "operator": row[2], "phone": row[3], "balance": row[4]} for row in cursor.fetchall()]
        last_cache_update = time.time()
        conn.close()

        self.write({"status": "SUCCESS", "data": modem_cache})

async def periodic_tasks():
    while True:
        await save_modem_data()
        await save_sms_data()
        await asyncio.sleep(10)

asyncio.create_task(periodic_tasks())

def make_app():
    return tornado.web.Application([
        (r"/sms", SMSHandler),
        (r"/audit", AuditHandler),
        (r"/ws/logs", LogsWebSocketHandler),
    ])

if __name__ == "__main__":
    app = make_app()
    app.listen(7777, address="0.0.0.0")
    print("Сервер запущен: http://0.0.0.0:7777")
    tornado.ioloop.IOLoop.current().start()
