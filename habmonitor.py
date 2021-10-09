#!/usr/bin/env python3

import time, io, os, logging
import serial
import pickle, traceback
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

loraSerial = serial.Serial('/dev/tty.usbserial-0001', 115200, timeout=5, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE)
if loraSerial == None:
    logging.error('Unable to initialise Lora Chip')
    exit(0)

def waitForData(length):
    bytesToRead = loraSerial.inWaiting()
    while bytesToRead < length:
        bytesToRead = loraSerial.inWaiting()

    data = loraSerial.read(length)
    return data

def extractSensorData(data):
    fmt = '>ffHBHHHIBL'
    packetSize = calcsize(fmt)
    logging.info('Packet Size: %d' % packetSize)

    (gps_latitude, gps_longitude, gps_altitude, fixpack, 
        env_temperature, env_pressure, env_humidity, env_gas_resistance,
        rpi_cpu_temperature, tmstamp) = unpack(fmt, data)
    gps_fix_status = (fixpack >> 4) & 0xf
    gps_satellites = fixpack & 0xf

    tmstamp = datetime.fromtimestamp(tmstamp)
    logging.info((gps_latitude, gps_longitude, gps_altitude, gps_fix_status, gps_satellites, 
        env_temperature, env_pressure, env_humidity, env_gas_resistance,
        rpi_cpu_temperature, tmstamp))

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
        .field("rpicputemperature", rpi_cpu_temperature)\
        .time(tmstamp, WritePrecision.NS)

    # write_api.write(bucket, org, point)

def sendAck(idBytes):
    packet = bytearray()
    packet.append(0xbc) #Address High
    packet.append(0x01) #Address Low
    packet.append(0x04) #Chennal
    packet.append(idBytes[0])
    packet.append(idBytes[1])
    loraSerial.write(packet)


def updateChunkData(fileData):
    filep = open('filechunks', 'wb')
    pickle.dump(fileData, filep)
    filep.close()

def readChunkData():
    filep = open('filechunks', 'rb')
    fileData = pickle.load(filep)
    filep.close()
    return fileData

updateChunkData([])

def wirteFileData(data):
    fileData = readChunkData()
    fileData.append((data[0], data[1], data[2:]))
    logging.info("File chunk index: %d / %d" % (data[0], data[1]))
    if len(fileData) == data[1]:
        fileData.sort(key=lambda tup: tup[0])
        file = open('latest.jpg', 'wb')
        for dt in fileData:
            file.write(dt[2])
        file.close()
        os.replace('latest.jpg', 'images/hab-' + time.strftime("%d-%H%M%S") + ".jpg")
        fileData = []
    updateChunkData(fileData)


logging.info('Waiting for signal:')
try:
    while True:
        try:
            header = waitForData(3)

            high = int(header[0]) & 0xff
            low = int(header[1]) & 0xff
            dataid = (high << 8) | low
            dataSize = int.from_bytes([header[2]], byteorder='big', signed=True)
            isChunked = dataSize < 0
            if isChunked:
                dataSize = -dataSize
            logging.info("DataId: %d Size: %d isChunked: %d" % (dataid, dataSize, isChunked))

            data = waitForData(dataSize)
            if not isChunked:
                extractSensorData(data)
            else:
                wirteFileData(data)

            sendAck(header)
        except Exception as e:
            logging.error("Error while parsing data - %s" % str(e))
            traceback.print_exc()
            # time.sleep(1)

except KeyboardInterrupt:
    exit(0)
