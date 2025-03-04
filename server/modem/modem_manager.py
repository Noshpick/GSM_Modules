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

CONFIG_PATH = "config/config.json"
with open(CONFIG_PATH) as f:
    CONFIG = json.load(f)

class ModemManager:
    def __init__(self):
        self.modems = {}
        self.sms_cache = {}
        self.sim_cache = {}
        logging.basicConfig(filename="logs/app.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
        self.set_usb_permissions()
        self.refresh_modems()
        tornado.ioloop.IOLoop.current().spawn_callback(self.update_sms_cache)

    def set_usb_permissions(self):
        logging.info("Установка прав на USB-устройства")
        if platform.system() != "Linux":
            logging.info("Система не Linux, пропускаем настройку USB-прав")
            return

        try:
            usb_devices = subprocess.getoutput("ls /dev/ttyUSB* 2>/dev/null").split()
            if not usb_devices:
                logging.warning("Нет подключённых USB-устройств (/dev/ttyUSB*)")
                return

            logging.info(f"Найденные USB-устройства: {usb_devices}")
            sudo_password = CONFIG.get("sudo_password")

            if sudo_password:
                command = f'echo "{sudo_password}" | sudo -S chmod 666 ' + " ".join(usb_devices)
                result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            else:
                result = subprocess.run(["sudo", "chmod", "666"] + usb_devices, check=True, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)

            if result.returncode == 0:
                logging.info(f"Доступ к {', '.join(usb_devices)} разрешён (chmod 666)")
            else:
                logging.error(f"Ошибка при изменении прав USB: {result.stderr.decode()}")

        except Exception as e:
            logging.error(f"Ошибка изменения прав USB: {e}")


    async def update_sim_cache(self):
        while True:
            try:
                self.refresh_modems()
                new_sim_cache = {}

                for port in self.modems.keys():
                    phone_number = self.get_phone_number(port)
                    if phone_number and phone_number != "Номер SIM недоступен":
                        new_sim_cache[port] = phone_number

                self.sim_cache = new_sim_cache
                logging.info(f"Кэш SIM-карт обновлён: {self.sim_cache}")

            except Exception as e:
                logging.error(f"Ошибка в update_sim_cache: {e}")

            await asyncio.sleep(30)


    def find_modem_ports(self):
        logging.info("Поиск доступных модемов...")
        system_os = platform.system()
        available_ports = []

        for port in serial.tools.list_ports.comports():
            if ("USB" in port.description) or ("usb" in port.hwid) or (system_os == "Windows" and "COM" in port.device):
                available_ports.append(port.device)

        logging.info(f"Найденные модемные порты: {available_ports}")
        return available_ports

    def refresh_modems(self):
        logging.info("Обновление списка модемов...")
        current_ports = self.find_modem_ports()
        active_ports = list(self.modems.keys())

        for port in current_ports:
            if port not in active_ports:
                self.connect_modem(port)

        for port in active_ports:
            if port not in current_ports:
                self.disconnect_modem(port)

    def connect(self):
        self.refresh_modems()
        return bool(self.modems)


    def connect_modem(self, port):
        logging.info(f"Подключение модема {port}...")
        if port in self.modems:
            logging.warning(f"Модем {port} уже активен, пропускаем")
            return

        try:
            modem = serial.Serial(port, CONFIG["baudrate"], timeout=CONFIG["timeout"])
            self.modems[port] = modem
            logging.info(f"Новый модем подключен: {port}")

            self.send_at_command(port, "AT+CMGF=1", refresh=False)
            logging.info(f"Включён текстовый режим SMS на {port}")

            self.send_at_command(port, 'AT+CPMS="MT","MT","MT"')
            logging.info(f"Хранилище SMS MT установлено на {port}")

        except serial.SerialException as e:
            logging.warning(f"Не удалось подключиться к {port}: {e}")


    def disconnect_modem(self, port):
        try:
            if port in self.modems and self.modems[port].is_open:
                self.modems[port].close()
                logging.info(f"Соединение с модемом {port} закрыто")

            del self.modems[port]
            logging.info(f"Модем отключен и удалён: {port}")
        except Exception as e:
            logging.warning(f"Ошибка при отключении {port}: {e}")


    def send_at_command(self, port, command, delay=0.2, refresh=True):
        if refresh:
            self.refresh_modems()

        modem = self.modems.get(port)
        if modem:
            logging.info(f"Отправка AT-команды на {port}: {command}")
            modem.flush()
            modem.write((command + "\r\n").encode())
            time.sleep(delay)

            response = ""
            while modem.inWaiting():
                response += modem.read(modem.inWaiting()).decode(errors="ignore")
                time.sleep(0.1)

                logging.debug(f"Ответ от модема {port}: {response.strip()}")
            return response.strip()
        return None

    def get_operator(self, port):
        logging.info(f"Получение оператора SIM-карты на {port}...")
        response = self.send_at_command(port, "AT+COPS?", refresh=False)
        if "+COPS:" in response:
            try:
                operator = response.split(",")[-1].replace('"', "").strip()
                operator = re.sub(r'\s*OK\s*$', '', operator)
                logging.info(f"Оператор {port}: {operator}")
                return operator
            except IndexError:
                logging.warning("Оператор не найден")
                return "Оператор не найден"
        return "Неизвестный оператор"

    def get_phone_number(self, port):
        response = self.send_at_command(port, "AT+CNUM")
        if response and "+CNUM:" in response:
            try:
                parts = response.split(",")
                if len(parts) > 1:
                    return parts[1].replace('"', "").strip()
            except IndexError:
                pass

        self.send_at_command(port, 'AT+CUSD=1,"*111*0887#",15')
        time.sleep(10)

        response = self.get_sms(port, include_111=True)

        phone_number = None
        sms_ids_to_delete = []

        for sms in response["sms"]:
            if sms["sender"] == "111":
                match = re.search(r'\b\d{11}\b', sms["message"])
                if match:
                    phone_number = match.group()
                    sms_ids_to_delete.append(sms["id"])

        for sms_id in sms_ids_to_delete:
            self.send_at_command(port, f"AT+CMGD={sms_id}")

        return phone_number if phone_number else "Номер SIM недоступен"

    def get_balance(self, port):
        response = self.send_at_command(port, 'AT+CUSD=1,"*100#",15')

        if not response or "ERROR" in response:
            return None

        time.sleep(3)
        new_response = self.send_at_command(port, "")

        if "+CUSD:" in new_response:
            try:
                match = re.search(r'"\s*([^"]+)\s*"', new_response)
                if match:
                    balance_text = match.group(1).strip()

                    if re.fullmatch(r"[0-9A-F]+", balance_text, re.IGNORECASE):
                        balance_text = bytes.fromhex(balance_text).decode("utf-16-be").strip()

                    balance_match = re.search(r"\d+[.,]?\d*", balance_text)
                    if balance_match:
                        return float(balance_match.group(0).replace(",", "."))

            except Exception as e:
                return None

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

    def refresh_sms(self):
        for port in self.modems.keys():
            sms_data = self.get_sms(port)
            self.sms_cache[port] = sms_data["sms"]
            logging.info(f"Обновлено SMS для {port}: {len(sms_data['sms'])} сообщений.")

        tornado.ioloop.IOLoop.current().call_later(10, self.refresh_sms)

    def get_sms_json(self, port):
        sms_data = self.get_sms(port)

        try:
            return json.dumps(sms_data, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Ошибка сериализации JSON: {e}")
            return json.dumps({"error": "Ошибка сериализации JSON"})

    def get_sms(self, port, include_111=False):
        try:
            start_time = time.time()

            if port not in self.modems:
                logging.error(f"Модем {port} не подключён!")
                return {"sms": [], "error": f"Модем {port} не подключён"}

            self.send_at_command(port, "AT+CMGF=1")
            response = self.send_at_command(port, 'AT+CMGL="ALL"')
            if not response or "ERROR" in response:
                return {"sms": []}

            messages = response.split("+CMGL: ")[1:]

            sms_dict = {}

            for sms in messages:
                parts = sms.strip().split("\r\n")
                if len(parts) < 2:
                    continue

                header = parts[0].split(",")
                if len(header) < 6:
                    continue

                date = header[4].strip().replace('"', '')
                time_str = header[5].strip().replace('"', '')
                sender = header[2].replace('"', '').strip()
                message = self.pdu_decode("\n".join(parts[1:]).strip())
                timestamp = f"{date} {time_str}"

                if not include_111 and sender == "111":
                    continue

                key = (sender, timestamp)
                if key in sms_dict:
                    sms_dict[key]["message"] += " " + message
                else:
                    sms_dict[key] = {
                        "id": header[0].strip(),
                        "sender": sender,
                        "message": message,
                        "timestamp": timestamp
                    }

            sms_list = list(sms_dict.values())
            logging.info(f"Получено {len(sms_list)} SMS с {port} за {round(time.time() - start_time, 3)} сек")
            return {"sms": sms_list}

        except Exception as e:
            logging.error(f"Ошибка в get_sms ({port}): {e}")
            return {"sms": [], "error": str(e)}

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
            logging.info(f"Модем на {port} отключен")
        self.modems = {}
