from server.api import make_app
from server.models import init_db
import tornado.ioloop
import time

print("🚀 Инициализация базы данных...")
init_db()
print("✅ База данных инициализирована!")

print("⌛ Ожидание 3 секунды перед запуском сервера...")
time.sleep(3)

if __name__ == "__main__":
    app = make_app()
    app.listen(7777, address="0.0.0.0")
    print("Запуск на http://0.0.0.0:7777")
    tornado.ioloop.IOLoop.current().start()
