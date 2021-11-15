#!/usr/bin/env python3

import time, logging
from struct import *
from gpiozero import DiskUsage, LoadAverage, CPUTemperature
from datetime import datetime

from gps import *
from bme import *
from lora import *
from camera import *

logging.basicConfig(format='[%(levelname)s]:[%(asctime)s]:%(message)s', filename='habcontrol.log', level=logging.ERROR)
logging.getLogger("HABControl")
logging.info('Starting High Altitude Balloon Controller...')

gps = GPSModule()
bme680 = BME680Module()
lora = LoraModule(addressLow=0x01, dataTimer=True, delay=0.25)
camera = CameraModule()
logging.info("Loaded all thread modules")
rpi_disk = DiskUsage()
rpi_load = LoadAverage()
rpi_cpu = CPUTemperature()

fmt = '>fffBfffHBL'
logging.debug("Size of packet: %d" % calcsize(fmt))

def packData():
    tmstamp = int(datetime.utcnow().timestamp())
    fixpack = ((gps.fix_status & 0xf) << 4) | (gps.satellites & 0xf)
    output_data = (
        gps.latitude, gps.longitude, gps.altitude, fixpack, 
        bme680.temperature, bme680.pressure, bme680.humidity, round(bme680.airQuality),
        round(rpi_cpu.temperature), tmstamp)

    logging.debug(output_data)
    packed_data = pack(fmt, *output_data)
    return packed_data

logging.info('Polling:')
try:
    while lora.healthy and gps.healthy and camera.healthy and bme680.healthy:
        lora.sendData(packData())
        lora.join(5)
        if not lora.hasChunkData():
            thumbnail = camera.getThumbnailImage()
            if thumbnail is not None:
                lora.sendData(thumbnail)
except KeyboardInterrupt:
    logging.info("Closing program")
except Exception as e:
    logging.error("Error in controller - %s" % str(e), exc_info=True)

gps.close()
lora.close()
camera.close()
bme680.close()
logging.info('HAB Controller exits.')
exit(1)