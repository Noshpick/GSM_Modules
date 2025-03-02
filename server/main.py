import tornado.ioloop
from server.api import make_app
import asyncio
from modem.modem_manager import ModemManager

modem_manager = ModemManager()

async def start_tasks():
    await modem_manager.start_background_tasks()

if __name__ == "__main__":
    app = make_app()
    app.listen(7777, address="0.0.0.0")
    print("Сервер запущен: http://0.0.0.0:7777")

    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_tasks())
    loop.run_forever()
