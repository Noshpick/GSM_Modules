import tornado.ioloop
import tornado.web
import json
from datetime import datetime
from server.database import get_db, save_sms, save_modem

class BaseHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.set_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def options(self, *args, **kwargs):
        self.set_status(204)
        self.finish()

class ReceiveSMSHandler(BaseHandler):
    def post(self):
        try:
            data = json.loads(self.request.body.decode("utf-8"))
            modem_id = data.get("modem_id")
            sender = data.get("sender")
            message = data.get("message")
            balance = data.get("balance")
            phone = data.get("phone")
            operator = data.get("operator")
            timestamp = datetime.now()

            if not modem_id or not sender or not message:
                self.write({"status": "ERROR", "message": "Invalid data"})
                self.set_status(400)
                return

            with next(get_db()) as db:
                save_modem(db, modem_id, operator, phone, balance)
                save_sms(db, modem_id, sender, message, timestamp)

            self.write({"status": "SUCCESS"})
        except Exception as e:
            self.write({"status": "ERROR", "message": str(e)})
            self.set_status(500)

def make_app():
    return tornado.web.Application([
        (r"/receive_sms", ReceiveSMSHandler),
    ])

if __name__ == "__main__":
    app = make_app()
    app.listen(7777, address="0.0.0.0")
    print("Сервер запущен: http://0.0.0.0:7777")
    tornado.ioloop.IOLoop.current().start()
