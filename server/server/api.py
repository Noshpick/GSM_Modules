import tornado.web
import tornado.websocket
import json
import re
import os
import asyncio
from modem.modem_manager import ModemManager

modem_manager = ModemManager()

log_clients = set()

class BaseHandler(tornado.web.RequestHandler):
    """Базовый обработчик API"""
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE, PUT")
        self.set_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def options(self, *args, **kwargs):
        self.set_status(204)
        self.finish()

class AuditHandler(BaseHandler):
    def get(self):
        self.write(json.dumps({"status": "SUCCESS", "data": modem_manager.get_all_modems_info()}))

class SMSHandler(BaseHandler):
    def get(self):
        self.write(json.dumps({"status": "SUCCESS", "data": modem_manager.sms_cache}))

class CodeHandler(BaseHandler):
    def get(self):
        phone_number = self.get_argument("phone", None)
        if not phone_number:
            self.write(json.dumps({"status": "ERROR", "message": "Укажите номер телефона"}))
            self.set_status(400)
            return

        extracted_codes = {}
        for port, messages in modem_manager.sms_cache.items():
            codes = [
                {
                    "id": sms["id"],
                    "sender": sms["sender"],
                    "message": " ".join(re.findall(r'\d+', sms["message"])),
                    "timestamp": sms["timestamp"]
                }
                for sms in messages if sms["sender"].lstrip("+") == phone_number
            ]
            extracted_codes[port] = codes

        if all(len(codes) == 0 for codes in extracted_codes.values()):
            self.set_status(404)
            self.write(json.dumps({"status": "ERROR", "message": f"Сообщения от номера {phone_number} не найдены."}))
        else:
            self.write(json.dumps({"status": "SUCCESS", "data": extracted_codes}))

class LogsWebSocketHandler(tornado.websocket.WebSocketHandler):
    def check_origin(self, origin):
        return True

    def open(self):
        log_clients.add(self)
        self.write_message(json.dumps({"status": "CONNECTED", "message": "WebSocket открыт"}))
        asyncio.get_event_loop().call_later(1, self.send_latest_logs)

    def on_close(self):
        log_clients.discard(self)

    def send_latest_logs(self):
        log_file_path = "logs/app.log"
        if os.path.exists(log_file_path):
            with open(log_file_path, "r") as log_file:
                logs = log_file.readlines()[-50:]
                self.write_message(json.dumps({"status": "SUCCESS", "logs": logs}))

    @staticmethod
    def broadcast_log(log_message):
        for client in list(log_clients):
            try:
                client.write_message(json.dumps({"status": "LOG", "message": log_message}))
            except:
                log_clients.discard(client)

def make_app():
    return tornado.web.Application([
        (r"/sms", SMSHandler),
        (r"/audit", AuditHandler),
        (r"/code", CodeHandler),
        (r"/ws/logs", LogsWebSocketHandler),
    ])

if __name__ == "__main__":
    app = make_app()
    app.listen(7777, address="0.0.0.0")
    print("Сервер запущен: http://0.0.0.0:7777")
    tornado.ioloop.IOLoop.current().start()
