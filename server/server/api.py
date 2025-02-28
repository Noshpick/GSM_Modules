import tornado.ioloop
import tornado.web
import tornado.websocket
import re
import os
import json
from tornado.ioloop import PeriodicCallback
from modem.modem_manager import ModemManager
import asyncio

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

    def get_request_port(self):
        port = self.get_argument("port", None)
        available_ports = self.get_available_ports()

        if not port:
            self.write({
                "status": "ERROR",
                "message": f"Отсутствует параметр 'port'. Доступные порты: {available_ports}"
            })
            self.set_status(400)
            self.finish()
            return None

        if port not in available_ports:
            self.write({
                "status": "ERROR",
                "message": f"Неверный параметр 'port'. Укажите один из доступных портов: {available_ports}"
            })
            self.set_status(400)
            self.finish()
            return None

        return port

class LogsWebSocketHandler(tornado.websocket.WebSocketHandler):

    def check_origin(self, origin):
        return True

    def open(self):
        log_clients.add(self)
        self.write_message(json.dumps({"status": "CONNECTED", "message": "WebSocket открыт"}))
        asyncio.get_event_loop().call_later(1, self.send_latest_logs)
        self.send_latest_logs()

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

class SMSHandler(BaseHandler):
    def get(self):
        self.write({"status": "SUCCESS", "data": modem_manager.sms_cache})


class AuditHandler(BaseHandler):
    def get(self):
        all_audit_data = []

        for port in self.get_available_ports():
            balance = modem_manager.get_balance(port)

            modem_data = {
                "port": port,
                "operator": modem_manager.get_operator(port),
                "phone": modem_manager.get_phone_number(port),
                "balance": balance if balance is not None else "Недоступно",
                "messages": modem_manager.get_sms(port)["sms"]
            }
            all_audit_data.append(modem_data)

        self.write({"status": "SUCCESS", "data": all_audit_data})

class CodeHandler(BaseHandler):
    def get(self):
        modem_phone = self.get_argument("modem_phone", None)
        sender_phone = self.get_argument("sender_phone", None)

        if not modem_phone or not sender_phone:
            self.write({
                "status": "ERROR",
                "message": "Отсутствуют параметры 'modem_phone' и/или 'sender_phone'. Укажите номера."
            })
            self.set_status(400)
            self.finish()
            return

        available_ports = list(modem_manager.modems.keys())
        if not available_ports:
            self.write({"status": "ERROR", "message": "Нет доступных модемов."})
            self.set_status(500)
            self.finish()
            return

        latest_code = None

        modem_numbers = {}
        for port in available_ports:
            if port not in modem_numbers:
                modem_numbers[port] = modem_manager.get_phone_number(port)

        target_port = None
        for port, phone in modem_numbers.items():
            if phone == modem_phone:
                target_port = port
                break

        if not target_port:
            self.write({"status": "ERROR", "message": f"SIM {modem_phone} не найдена в модемах."})
            self.set_status(404)
            self.finish()
            return

        modem_manager.send_at_command(target_port, 'AT+CMGL="REC UNREAD"')
        sms_data = modem_manager.get_sms(target_port)

        for sms in sorted(sms_data["sms"], key=lambda x: x["timestamp"], reverse=True):
            if sms["sender"].lstrip("+") == sender_phone:
                latest_code = " ".join(re.findall(r'\d+', sms["message"]))
                break

        if latest_code:
            self.write({"status": "SUCCESS", "code": latest_code})
        else:
            self.write({
                "status": "ERROR",
                "message": f"Сообщение от {sender_phone} на SIM {modem_phone} не найдено."
            })
            self.set_status(404)

        self.finish()



def tail_logs():
    log_file_path = "logs/app.log"
    if not os.path.exists(log_file_path):
        return
    
    last_pos = 0
    
    def check_new_logs():
        nonlocal last_pos
        if not os.path.exists(log_file_path):
            return
        
        with open(log_file_path, "r") as f:
            f.seek(last_pos)
            new_logs = f.readlines()
            last_pos = f.tell()
        
        for line in new_logs:
            LogsWebSocketHandler.broadcast_log(line.strip())
        
        tornado.ioloop.IOLoop.current().call_later(1, check_new_logs)
    
    check_new_logs()


def periodic_refresh():
    modem_manager.refresh_modems()
    tornado.ioloop.IOLoop.current().call_later(10, periodic_refresh)

def start_log_watcher():
    PeriodicCallback(tail_logs, 4000).start()

periodic_refresh()
start_log_watcher()

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
    modem_manager.refresh_sms()
    tornado.ioloop.IOLoop.current().start()
