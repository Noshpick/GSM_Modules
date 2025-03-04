import asyncio
import subprocess
import serial
import serial.tools.list_ports
import json
import logging
import platform
import re
import time
import tornado
from sqlalchemy.orm import Session
from server.server.database import get_db, save_modem, save_sms, save_log

CONFIG_PATH = "config/config.json"
with open(CONFIG_PATH) as f:
    CONFIG = json.load(f)

class ModemManager:
    def __init__(self):
        self.modems = {}
        self.sms_cache = {}
        logging.basicConfig(filename="logs/app.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
        self.set_usb_permissions()
        self.refresh_modems()
        tornado.ioloop.IOLoop.current().spawn_callback(self.update_sms_cache)

    def set_usb_permissions(self):
        logging.info("Установка прав на USB-устройства")
        if platform.system() != "Linux":
            return

        try:
            usb_devices = subprocess.getoutput("ls /dev/ttyUSB* 2>/dev/null").split()
            if not usb_devices:
                logging.warning("Нет подключённых USB-устройств (/dev/ttyUSB*)")
                return

            sudo_password = CONFIG.get("sudo_password")
            if sudo_password:
                command = f'echo "{sudo_password}" | sudo -S chmod 666 ' + " ".join(usb_devices)
                subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            else:
                subprocess.run(["sudo", "chmod", "666"] + usb_devices, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        except Exception as e:
            logging.error(f"Ошибка изменения прав USB: {e}")

    def find_modem_ports(self):
        logging.info("Поиск доступных модемов...")
        return [port.device for port in serial.tools.list_ports.comports() if "USB" in port.description]

    def refresh_modems(self):
        logging.info("Обновление списка модемов...")
        with next(get_db()) as db:
            current_ports = self.find_modem_ports()
            active_ports = list(self.modems.keys())

            for port in current_ports:
                if port not in active_ports:
                    self.connect_modem(db, port)

            for port in active_ports:
                if port not in current_ports:
                    self.disconnect_modem(port)

    def connect_modem(self, db: Session, port):
        logging.info(f"Подключение модема {port}...")
        if port in self.modems:
            return

        try:
            modem = serial.Serial(port, CONFIG["baudrate"], timeout=CONFIG["timeout"])
            self.modems[port] = modem
            self.send_at_command(port, "AT+CMGF=1", refresh=False)
            self.send_at_command(port, 'AT+CPMS="MT","MT","MT"')

            operator = self.get_operator(port)
            phone = self.get_phone_number(port)
            balance = self.get_balance(port)

            save_modem(db, port, operator, phone, balance)
            save_log(db, f"Модем {port} подключен. Оператор: {operator}, Номер: {phone}, Баланс: {balance}")


        except serial.SerialException as e:
            logging.warning(f"Не удалось подключиться к {port}: {e}")

    def connect(self):
                print("Модем подключается...")

    def disconnect_modem(self, port):
        if port in self.modems and self.modems[port].is_open:
            self.modems[port].close()
        del self.modems[port]

    def send_at_command(self, port, command, delay=0.5, refresh=True):
        if refresh:
            self.refresh_modems()

        modem = self.modems.get(port)
        if modem:
            modem.write((command + "\r\n").encode())
            time.sleep(delay)

            response = ""
            while modem.inWaiting():
                response += modem.read(modem.inWaiting()).decode(errors="ignore")
                time.sleep(0.1)

            return response.strip()
        return None

    def get_operator(self, port):
        response = self.send_at_command(port, "AT+COPS?", refresh=False)
        if "+COPS:" in response:
            return response.split(",")[-1].replace('"', "").strip()
        return "Неизвестный оператор"

    def get_phone_number(self, port):
        response = self.send_at_command(port, "AT+CNUM")
        if response and "+CNUM:" in response:
            parts = response.split(",")
            if len(parts) > 1:
                return parts[1].replace('"', "").strip()
        return "Номер SIM недоступен"

    def get_balance(self, port):
        response = self.send_at_command(port, 'AT+CUSD=1,"*100#",15')
        if response and "+CUSD:" in response:
            match = re.search(r'\d+[.,]?\d*', response)
            if match:
                return float(match.group(0).replace(",", "."))
        return None

    def pdu_decode(self, pdu_string):
        try:
            if re.fullmatch(r'\d+', pdu_string) and len(pdu_string) < 10:
                return pdu_string

            if re.fullmatch(r"[0-9A-F]+", pdu_string, re.IGNORECASE) and len(pdu_string) % 2 == 0:
                for encoding in ["utf-16-be", "ISO-8859-1", "ascii"]:
                    try:
                        return bytes.fromhex(pdu_string).decode(encoding).strip()
                    except UnicodeDecodeError:
                        continue
                return pdu_string

            return pdu_string
        except Exception:
            return pdu_string

    def get_sms(self, port):
        try:
            if port not in self.modems:
                return {"sms": [], "error": f"Модем {port} не подключён"}

            self.send_at_command(port, "AT+CMGF=1")
            response = self.send_at_command(port, 'AT+CMGL="ALL"')
            if not response or "ERROR" in response:
                return {"sms": []}

            messages = response.split("+CMGL: ")[1:]
            sms_list = []

            with next(get_db()) as db:
                for sms in messages:
                    parts = sms.strip().split("\r\n")
                    if len(parts) < 2:
                        continue

                    header = parts[0].split(",")
                    if len(header) < 6:
                        continue

                    sender = header[2].replace('"', '').strip()
                    date = header[4].strip().replace('"', '')
                    time_str = header[5].strip().replace('"', '')
                    timestamp = f"{date} {time_str}"
                    message = self.pdu_decode("\n".join(parts[1:]).strip())

                    sms_list.append({"sender": sender, "message": message, "timestamp": timestamp})
                    save_sms(db, port, sender, message)

            return {"sms": sms_list}

        except Exception as e:
            logging.error(f"Ошибка в get_sms ({port}): {e}")
            return {"sms": [], "error": str(e)}

    def refresh_sms(self):
        for port in self.modems.keys():
            sms_data = self.get_sms(port)
            self.sms_cache[port] = sms_data["sms"]
            logging.info(f"Обновлено SMS для {port}: {len(sms_data['sms'])} сообщений.")

        tornado.ioloop.IOLoop.current().call_later(5, self.refresh_sms)

    def get_sms_json(self, port):
        sms_data = self.get_sms(port)
        try:
            return json.dumps(sms_data, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Ошибка сериализации JSON: {e}")
            return json.dumps({"error": "Ошибка сериализации JSON"})

    async def update_sms_cache(self):
        while True:
            try:
                self.refresh_modems()
                new_sms_cache = {port: self.get_sms(port)["sms"] for port in self.modems.keys()}
                self.sms_cache = new_sms_cache
                logging.info(f"Кэш SMS обновлён. Найденные порты: {list(self.modems.keys())}")
            except Exception as e:
                logging.error(f"Ошибка в update_sms_cache: {e}")
            await asyncio.sleep(10)

    def close(self):
        for port, modem in self.modems.items():
            modem.close()
        self.modems = {}
