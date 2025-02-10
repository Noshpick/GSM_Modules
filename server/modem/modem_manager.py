import subprocess
import serial
import serial.tools.list_ports
import time
import json
import logging
import platform
import re

CONFIG_PATH = "config/config.json"
with open(CONFIG_PATH) as f:
    CONFIG = json.load(f)

class ModemManager:
    def __init__(self):
        self.modems = {}
        logging.basicConfig(filename="logs/app.log", level=logging.INFO)
        self.set_usb_permissions()

    def set_usb_permissions(self):
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

    def find_modem_ports(self):
        system_os = platform.system()
        available_ports = []

        for port in serial.tools.list_ports.comports():
            if ("USB" in port.description) or ("usb" in port.hwid) or (system_os == "Windows" and "COM" in port.device):
                available_ports.append(port.device)

        logging.info(f"Найденные модемные порты: {available_ports}")
        return available_ports

    def connect(self):
        ports = self.find_modem_ports()

        if not ports:
            logging.error("Модемы не найдены")
            return False

        for port in ports:
            try:
                modem = serial.Serial(port, CONFIG["baudrate"], timeout=CONFIG["timeout"])
                self.modems[port] = modem
                logging.info(f"Подключен к модему на {port} ({platform.system()})")

                response = self.send_at_command(port, "AT+CMGF=1")
                logging.info(f"Установлен текстовый режим SMS на {port}: {response}")

            except serial.SerialException as e:
                logging.warning(f"Не удалось подключиться к {port}: {e}")

        return bool(self.modems)

    def send_at_command(self, port, command, delay=0.2):
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
        response = self.send_at_command(port, "AT+COPS?")

        if "+COPS:" in response:
            try:
                operator = response.split(",")[-1].replace('"', "").strip()
                operator = re.sub(r'\s*OK\s*$', '', operator)
                return operator
            except IndexError:
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

    def get_sms(self, port, include_111=False):
        self.send_at_command(port, "AT+CNMI=2,1,0,0,0")
        self.send_at_command(port, 'AT+CPMS="MT","MT","MT"')

        response = self.send_at_command(port, 'AT+CMGL="ALL"')

        if not response or "CMGL:" not in response:
            return {"sms": []}

        messages = []
        sms_list = response.split("+CMGL: ")

        for sms in sms_list[1:]:
            parts = sms.strip().split("\r\n")
            if len(parts) < 2:
                continue

            header = parts[0].split(",")
            if len(header) < 6:
                continue

            sender = header[2].replace('"', "").strip()
            date = header[4].replace('"', "").strip()
            time = header[5].replace('"', "").strip()
            timestamp = f"{date} {time}"
            sms_id = header[0].strip()

            sms_body = "\n".join(parts[1:]).strip()
            sms_body = re.sub(r'\n*OK\n*', '', sms_body).strip()

            try:
                decoded_text = bytes.fromhex(sms_body).decode("utf-16-be") if re.fullmatch(r"[0-9A-F]+", sms_body, re.IGNORECASE) else sms_body
            except ValueError:
                decoded_text = sms_body

            if not include_111 and sender == "111":
                continue

            messages.append({
                "id": sms_id,
                "sender": sender,
                "message": decoded_text,
                "timestamp": timestamp
            })

        logging.info(f"Полученные SMS на {port}: {json.dumps(messages, indent=4, ensure_ascii=False)}")
        return {"sms": messages}

    def close(self):
        for port, modem in self.modems.items():
            modem.close()
            logging.info(f"Модем на {port} отключен")
        self.modems = {}