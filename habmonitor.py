#!/usr/bin/env python3

import time, io, os, logging
import serial
from pathlib import Path
from struct import *

from datetime import datetime
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

token = "lmT3TlBem_yckZS4iSkWphYoJudAzvrE9WGD3MNFX4JaJ4OnnAj3CMWuhhdqt8GwGnYEqthXh2I2DeGR4KowfQ=="
org = "HABControl"
bucket = "hab"
client = InfluxDBClient(url="http://localhost:8086", token=token)
write_api = client.write_api(write_options=SYNCHRONOUS)

logging.basicConfig(format='[%(levelname)s]:[%(asctime)s]:%(message)s', level=logging.INFO)

fmt = 'ffHBBffffBBB'
packetSize = calcsize(fmt)
logging.info('Packet Size: %d' % packetSize)

loraSerial = serial.Serial('/dev/tty.usbserial-0001', 9600, timeout=5, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE)
if loraSerial == None:
    logging.error('Unable to initialise Lora Chip')
    exit(0)

logging.info('Polling:')
try:
    while True:
        try:
            bytesToRead = loraSerial.inWaiting()
            while bytesToRead < packetSize:
                bytesToRead = loraSerial.inWaiting()

            data = loraSerial.read(packetSize)
            (gps_latitude, gps_longitude, gps_altitude, gps_fix_status, gps_satellites, 
                env_temperature, env_pressure, env_humidity, env_gas_resistance,
                rpi_disk_usage, rpi_cpu_load, rpi_cpu_temperature) = unpack(fmt, data)
            logging.info((gps_latitude, gps_longitude, gps_altitude, gps_fix_status, gps_satellites, 
                env_temperature, env_pressure, env_humidity, env_gas_resistance,
                rpi_disk_usage, rpi_cpu_load, rpi_cpu_temperature))

            point = Point("payloaddata")\
                .tag("host", "payload")\
                .field("latitude", gps_latitude)\
                .field("longitude", gps_longitude)\
                .field("altitude", gps_altitude)\
                .field("fixstatus", gps_fix_status)\
                .field("satellites", gps_satellites)\
                .field("temperature", env_temperature)\
                .field("pressure", env_pressure)\
                .field("humidity", env_humidity)\
                .field("gasresistance", env_gas_resistance)\
                .field("rpidiskusage", rpi_disk_usage)\
                .field("rpicpuload", rpi_cpu_load)\
                .field("rpicputemperature", rpi_cpu_temperature)\
                .time(datetime.utcnow(), WritePrecision.NS)

            write_api.write(bucket, org, point)

        except Exception as e:
            logging.error("Error while parsing data - %s" % str(e))
            time.sleep(1)

except KeyboardInterrupt:
    exit(0)
