from server.api import make_app
import tornado.ioloop

if __name__ == "__main__":
    app = make_app()
    app.listen(7777)
    print("Запуск на http://127.0.0.1:7777")
    tornado.ioloop.IOLoop.current().start()
