import serial
import time
import json
import requests
from modem.at_commands import AT_COMMANDS
from modem.modem_manager import find_modems, connect_modem

SERVER_URL = "http://45.152.170.77:7777/receive_sms"

def send_at_command(sim800, command, delay=1):
    sim800.write((command + "\r\n").encode())
    time.sleep(delay)
    return sim800.read(sim800.inWaiting()).decode(errors="ignore")

def send_sms_to_server(sim800, modem_id):
    for cmd in AT_COMMANDS["init_gprs"]:
        send_at_command(sim800, cmd)

    operator = send_at_command(sim800, AT_COMMANDS["get_operator"])
    phone = send_at_command(sim800, AT_COMMANDS["get_phone"])
    balance = send_at_command(sim800, AT_COMMANDS["get_balance"])

    data = {"modem_id": modem_id, "operator": operator, "phone": phone, "balance": balance}

    send_at_command(sim800, 'AT+HTTPINIT')
    send_at_command(sim800, f'AT+HTTPPARA="URL","{SERVER_URL}"')
    send_at_command(sim800, 'AT+HTTPACTION=1')
    time.sleep(5)
    send_at_command(sim800, 'AT+HTTPTERM')

def main():
    while True:
        for modem in find_modems():
            sim800 = connect_modem(modem)
            send_sms_to_server(sim800, modem)
            sim800.close()
        time.sleep(10)

if __name__ == "__main__":
    main()
