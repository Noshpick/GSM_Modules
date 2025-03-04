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
        phone_number = self.get_argument("phone", None)

        if not phone_number:
            self.write({
                "status": "ERROR",
                "message": "Отсутствует параметр 'phone'. Укажите номер отправителя."
            })
            self.set_status(400)
            self.finish()
            return

        extracted_codes = {}

        available_ports = self.get_available_ports()

        if not available_ports:
            self.write({"status": "ERROR", "message": "Нет доступных модемов."})
            self.set_status(500)
            self.finish()
            return

        for port in available_ports:
            modem_manager.send_at_command(port, 'AT+CMGL="ALL"')
            sms_data = modem_manager.sms_cache.get(port, {"sms": []})
            codes = []

            for sms in sms_data["sms"]:
                sender = sms["sender"].lstrip("+")

                if sender == phone_number:
                    numeric_code = " ".join(re.findall(r'\d+', sms["message"]))

                    codes.append({
                        "id": sms["id"],
                        "sender": sms["sender"],
                        "message": numeric_code,
                        "timestamp": sms["timestamp"]
                    })

            extracted_codes[port] = codes

        if all(len(codes) == 0 for codes in extracted_codes.values()):
            self.write({"status": "ERROR", "message": f"Сообщения от номера {phone_number} не найдены."})
            self.set_status(404)
        else:
            self.write({"status": "SUCCESS", "data": extracted_codes})

        self.finish()


class LastCodeHandler(BaseHandler):
    def get(self):
        modem_phone = self.get_argument("modem_phone", None)
        sender_phone = self.get_argument("phone", None)

        if not modem_phone or not sender_phone:
            self.write({
                "status": "ERROR",
                "message": "Отсутствует параметр 'modem_phone' или 'phone'."
            })
            self.set_status(400)
            self.finish()
            return

        target_port = None
        for port in self.get_available_ports():
            if modem_manager.get_phone_number(port) == modem_phone:
                target_port = port
                break

        if not target_port:
            self.write({
                "status": "ERROR",
                "message": f"Модем с номером {modem_phone} не найден."
            })
            self.set_status(404)
            self.finish()
            return

        sms_data = modem_manager.sms_cache.get(target_port, {"sms": []})

        last_sms = next(
            (sms for sms in reversed(sms_data["sms"]) if sms["sender"].lstrip("+") == sender_phone), None
        )

        if last_sms:
            numeric_code = " ".join(re.findall(r'\d+', last_sms["message"]))  # Оставляем только цифры
            self.write({
                "status": "SUCCESS",
                "data": {
                    "id": last_sms["id"],
                    "sender": last_sms["sender"],
                    "message": numeric_code,
                    "timestamp": last_sms["timestamp"]
                }
            })
        else:
            self.write({
                "status": "ERROR",
                "message": f"Последнее SMS от номера {sender_phone} не найдено."
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
    tornado.ioloop.IOLoop.current().call_later(30, periodic_refresh)

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
        (r"/last_code", LastCodeHandler),
    ])



if __name__ == "__main__":
    app = make_app()
    app.listen(7777, address="0.0.0.0")
    print("Сервер запущен: http://0.0.0.0:7777")
    modem_manager.refresh_sms()
    tornado.ioloop.IOLoop.current().start()
