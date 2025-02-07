import tornado.ioloop
import tornado.web
from modem.modem_manager import ModemManager

modem_manager = ModemManager()
modem_manager.connect()


class BaseHandler(tornado.web.RequestHandler):
    def get_available_ports(self):
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



class SMSHandler(BaseHandler):
    def get(self):
        all_sms_data = {}

        for port in self.get_available_ports():
            sms_data = modem_manager.get_sms(port)
            all_sms_data[port] = sms_data["sms"]

        self.write({"status": "SUCCESS", "data": all_sms_data})



class AuditHandler(BaseHandler):
    def get(self):
        all_audit_data = {}

        for port in self.get_available_ports():
            all_audit_data[port] = {
                "operator": modem_manager.get_operator(port),
                "phone": modem_manager.get_phone_number(port),
                "balance": modem_manager.get_balance(port),
                "messages": modem_manager.get_sms(port)["sms"]
            }

        self.write({"status": "SUCCESS", "data": all_audit_data})

def make_app():
    return tornado.web.Application([
        (r"/sms", SMSHandler),
        (r"/audit", AuditHandler),
    ])

if __name__ == "__main__":
    app = make_app()
    app.listen(7777)
    print("Сервер запущен: http://127.0.0.1:7777")
    tornado.ioloop.IOLoop.current().start()
