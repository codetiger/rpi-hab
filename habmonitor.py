#!/usr/bin/env python3

import time, io, os, logging, serial, pickle
from pathlib import Path
from struct import *
from lora import *
import shutil
import RPi.GPIO as GPIO

from datetime import datetime
from influxdb import InfluxDBClient

client = InfluxDBClient(host='127.0.0.1', port=8086)
client.switch_database('hab')

logging.basicConfig(format='[%(levelname)s]:[%(asctime)s]:%(message)s', filename='habmonitor.log', level=logging.ERROR)

BUZZER_PIN = 12
GPIO.setmode(GPIO.BCM)
GPIO.setup(BUZZER_PIN, GPIO.OUT)
lora = LoraModule(addressLow=0x02, dataTimer=False, delay=0.25)

def extractSensorData(data):
    fmt = '>ffHBfffIBL'
    packetSize = calcsize(fmt)
    logging.debug('Packet Size: %d' % packetSize)

    (gps_latitude, gps_longitude, gps_altitude, fixpack, 
        env_temperature, env_pressure, env_humidity, env_gas_resistance,
        rpi_cpu_temperature, tmstamp) = unpack(fmt, data)
    gps_fix_status = (fixpack >> 4) & 0xf
    gps_satellites = fixpack & 0xf

    tmstamp = datetime.fromtimestamp(tmstamp)
    logging.debug((gps_latitude, gps_longitude, gps_altitude, gps_fix_status, gps_satellites, 
        env_temperature, env_pressure, env_humidity, env_gas_resistance,
        rpi_cpu_temperature, tmstamp))

    json_body = [{
        "measurement": "payloaddata",
        "time": tmstamp,
        "fields": {
            "fixstatus": gps_fix_status, "satellites": gps_satellites,
            "rpicputemperature": rpi_cpu_temperature,
        }
    }]
    if not (env_temperature == 0 and env_pressure == 0 and env_humidity == 0):
        json_body[0]["fields"]["temperature"] = env_temperature
        json_body[0]["fields"]["pressure"] = env_pressure
        json_body[0]["fields"]["humidity"] = env_humidity
        json_body[0]["fields"]["gasresistance"] = env_gas_resistance

    if gps_fix_status > 2:
        json_body[0]["fields"]["altitude"] = gps_altitude
    if gps_fix_status >= 2:
        json_body[0]["fields"]["latitude"] = gps_latitude
        json_body[0]["fields"]["longitude"] = gps_longitude

    res = client.write_points(json_body, time_precision='s')
    logging.debug("Write to Influx: %d" %(res))
    GPIO.output(BUZZER_PIN, GPIO.HIGH)
    time.sleep(0.02)
    GPIO.output(BUZZER_PIN, GPIO.LOW)

def updateChunkData(fileData):
    filep = open('filechunks', 'wb')
    pickle.dump(fileData, filep)
    filep.close()

def readChunkData():
    filep = open('filechunks', 'rb')
    fileData = pickle.load(filep)
    filep.close()
    return fileData

updateChunkData({})

def wirteFileData(data):
    fileData = readChunkData()
    index = int.from_bytes(data[0:2], byteorder='big', signed=False)
    totalChunks = int.from_bytes(data[2:4], byteorder='big', signed=False)
    fileData[index] = data[4:]
    logging.debug("File chunk index: %d / %d" % (index, totalChunks))
    if len(fileData) == totalChunks:
        file = open('images/latest.jpg', 'wb')
        try:
            for i in range(0, len(fileData)):
                file.write(fileData[i])
            file.flush()
            shutil.copyfile('images/latest.jpg', 'images/hab-' + time.strftime("%d-%H%M%S") + ".jpg")
        except Exception as e:
            logging.error("Error creating image data - %s" % str(e))
        fileData = {}
        file.close()
        GPIO.output(BUZZER_PIN, GPIO.HIGH)
        time.sleep(0.2)
        GPIO.output(BUZZER_PIN, GPIO.LOW)
        time.sleep(0.2)
        GPIO.output(BUZZER_PIN, GPIO.HIGH)
        time.sleep(0.2)
        GPIO.output(BUZZER_PIN, GPIO.LOW)
    updateChunkData(fileData)

logging.info('Waiting for signal:')
try:
    while True:
        callsign = lora.waitForData(1)
        if callsign is not None and callsign[0] == 0xda:
            header = lora.waitForData(3)
            if header is not None:
                try:
                    high = int(header[0]) & 0xff
                    low = int(header[1]) & 0xff
                    dataid = (high << 8) | low
                    dataSize = int.from_bytes([header[2]], byteorder='big', signed=True)
                    isChunked = dataSize < 0
                    if isChunked:
                        dataSize = -dataSize
                    logging.info("DataId: %d Size: %d isChunked: %d" % (dataid, dataSize, isChunked))

                    data = lora.waitForData(dataSize)
                    if not isChunked:
                        extractSensorData(data)
                    else:
                        wirteFileData(data)

                    packet = bytearray()
                    packet.append(0xbc)
                    packet.append(0x01)
                    packet.append(0x04)
                    packet.append(0xac)
                    packet.append(high)
                    packet.append(low)
                    lora.transmit(packet) #sending ack
                except Exception as e:
                    logging.error("Error while parsing data - %s" % str(e), exc_info=True)

except KeyboardInterrupt:
    lora.close()
    client.close()
    exit(0)
