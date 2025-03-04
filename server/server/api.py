import tornado.ioloop
import tornado.web
import tornado.websocket
import json
import asyncio
import re
from server.modem.modem_manager import ModemManager
from server.server.database import get_db, get_all_modems, get_all_sms, get_logs, save_log

modem_manager = ModemManager()
modem_manager.connect()

log_clients = set()

class BaseHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE, PUT")
        self.set_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def options(self, *args, **kwargs):
        self.set_status(204)
        self.finish()

    def get_available_ports(self):
        modem_manager.refresh_modems()
        return list(modem_manager.modems.keys())


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
        with next(get_db()) as db:
            logs = get_logs(db, limit=50)
            log_messages = [log.message for log in logs]
            self.write_message(json.dumps({"status": "SUCCESS", "logs": log_messages}))

    @staticmethod
    def broadcast_log(log_message):
        with next(get_db()) as db:
            save_log(db, log_message)

        for client in list(log_clients):
            try:
                client.write_message(json.dumps({"status": "LOG", "message": log_message}))
            except:
                log_clients.discard(client)


class SMSHandler(BaseHandler):
    def get(self):
        with next(get_db()) as db:
            sms_data = get_all_sms(db)
            formatted_sms = [
                {"port": sms.modem_id, "sender": sms.sender, "message": sms.message, "timestamp": sms.timestamp}
                for sms in sms_data
            ]
            self.write({"status": "SUCCESS", "data": formatted_sms})


class AuditHandler(BaseHandler):
    def get(self):
        with next(get_db()) as db:
            modems = get_all_modems(db)
            all_audit_data = [
                {
                    "port": modem.port,
                    "operator": modem.operator,
                    "phone": modem.phone,
                    "balance": modem.balance if modem.balance is not None else "Недоступно",
                }
                for modem in modems
            ]
            self.write({"status": "SUCCESS", "data": all_audit_data})


class CodeHandler(BaseHandler):
    def get(self):
        phone_number = self.get_argument("phone", None)

        if not phone_number:
            self.write({"status": "ERROR", "message": "Отсутствует параметр 'phone'. Укажите номер отправителя."})
            self.set_status(400)
            self.finish()
            return

        extracted_codes = {}

        with next(get_db()) as db:
            sms_data = get_all_sms(db)
            for sms in sms_data:
                sender = sms.sender.lstrip("+")

                if sender == phone_number:
                    numeric_code = " ".join(re.findall(r'\d+', sms.message))
                    if sms.modem_id not in extracted_codes:
                        extracted_codes[sms.modem_id] = []

                    extracted_codes[sms.modem_id].append({
                        "sender": sms.sender,
                        "message": numeric_code,
                        "timestamp": sms.timestamp
                    })

        if all(len(codes) == 0 for codes in extracted_codes.values()):
            self.write({"status": "ERROR", "message": f"Сообщения от номера {phone_number} не найдены."})
            self.set_status(404)
        else:
            self.write({"status": "SUCCESS", "data": extracted_codes})

        self.finish()


def periodic_refresh():
    modem_manager.refresh_modems()
    tornado.ioloop.IOLoop.current().call_later(10, periodic_refresh)


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
    periodic_refresh()
    tornado.ioloop.IOLoop.current().start()
