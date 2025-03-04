import serial
import glob

BAUD_RATE = 9600

def find_modems():
    return glob.glob("/dev/ttyUSB*")

def connect_modem(port):
    return serial.Serial(port, BAUD_RATE, timeout=1)
