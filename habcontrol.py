#!/usr/bin/env python3

import time, logging
from struct import *
from gpiozero import DiskUsage, LoadAverage, CPUTemperature
from datetime import datetime

from gps import *
from bme import *
from lora import *
from camera import *

# logging.basicConfig(format='[%(levelname)s]:[%(asctime)s]:%(message)s', filename='habcontrol.log', level=logging.INFO)
logging.basicConfig(format='[%(levelname)s]:[%(asctime)s]:%(message)s', level=logging.INFO)
logging.getLogger("HABControl")
logging.info('Starting High Altitude Balloon Controller...')

gps = GPSModule()
bme680 = BME680Module()
lora = LoraModule()
camera = CameraModule()
logging.info("Loaded all thread modules")
rpi_disk = DiskUsage()
rpi_load = LoadAverage()
rpi_cpu = CPUTemperature()

fmt = '>fffBBffffBBBL'
logging.info("Size of packet: %d" % calcsize(fmt))

def packData():
    tmstamp = int(datetime.now().timestamp())

    output_data = (
        gps.latitude, gps.longitude, gps.altitude, gps.fix_status, gps.satellites, 
        bme680.temperature, bme680.pressure, bme680.humidity, bme680.gas_resistance,
        round(rpi_disk.usage), round(rpi_load.value * 100.0), round(rpi_cpu.temperature), tmstamp)

    logging.info(output_data)
    packed_data = pack(fmt, *output_data)
    return packed_data

logging.info('Polling:')
try:
    while lora.isAlive():
        lora.sendData(packData())
        lora.join(5)
        # time.sleep(10)

except KeyboardInterrupt:
    logging.info("Closing program")
    gps.close()
    lora.close()
    camera.close()
    bme680.close()