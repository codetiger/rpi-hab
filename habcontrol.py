#!/usr/bin/env python3

import time, logging
from struct import *
from gpiozero import DiskUsage, LoadAverage, CPUTemperature

from gps import *
from bme import *
from lora import *
from camera import *

logging.basicConfig(format='[%(levelname)s]:[%(asctime)s]:%(message)s', filename='habcontrol.log', level=logging.INFO)
logging.getLogger("HABControl")
logging.info('Starting High Altitude Balloon Controller...')

gps = GPSModule()
bme680 = BME680Module()
lora = LoraModule()
camera = CameraModule()
rpi_disk = DiskUsage()
rpi_load = LoadAverage()
rpi_cpu = CPUTemperature()

def packData():
    fmt = 'ffHBBffffBBB'
    output_data = (
        gps.latitude, gps.longitude, gps.altitude, gps.fix_status, gps.satellites, 
        bme680.temperature, bme680.pressure, bme680.humidity, bme680.gas_resistance,
        round(rpi_disk.usage), round(rpi_load.value * 100.0), round(rpi_cpu.temperature))

    logging.info(output_data)
    packed_data = pack(fmt, *output_data)
    return packed_data

logging.info('Polling:')
try:
    while True:
        lora.sendData(packData(), 0xbc, 0x02, 0x04)
        time.sleep(5)

except KeyboardInterrupt:
    gps.close()
    lora.close()
    camera.close()
    bme680.close()