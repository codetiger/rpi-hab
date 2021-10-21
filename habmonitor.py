#!/usr/bin/env python3

import time, io, os, logging
import serial
import pickle, traceback
from pathlib import Path
from struct import *
from lora import *
import shutil

from datetime import datetime
from influxdb import InfluxDBClient

client = InfluxDBClient(host='127.0.0.1', port=8086)
client.switch_database('hab')

logging.basicConfig(format='[%(levelname)s]:[%(asctime)s]:%(message)s', filename='habcontrol.log', level=logging.INFO)

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
            "latitude": gps_latitude, "longitude": gps_longitude, "altitude": gps_altitude, "fixstatus": gps_fix_status, "satellites": gps_satellites,
            "temperature": env_temperature, "pressure": env_pressure, "humidity": env_humidity, "gasresistance": env_gas_resistance,
            "rpicputemperature": rpi_cpu_temperature,
        }
    }]
    res = client.write_points(json_body, time_precision='s')
    logging.debug("Write to Influx: %d" %(res))

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
    fileData[data[0]] = data[2:]
    logging.debug("File chunk index: %d / %d" % (data[0], data[1]))
    if len(fileData) == data[1]:
        file = open('images/latest.jpg', 'wb')
        for i in range(0, len(fileData)):
            file.write(fileData[i])
        file.close()
        shutil.copyfile('images/latest.jpg', 'images/hab-' + time.strftime("%d-%H%M%S") + ".jpg")
        fileData = {}
    updateChunkData(fileData)

logging.info('Waiting for signal:')
try:
    while True:
        try:
            callsign = lora.waitForData(1)

            if callsign[0] == 0xda:
                header = lora.waitForData(3)
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
            logging.error("Error while parsing data - %s" % str(e))
            traceback.print_exc()

except KeyboardInterrupt:
    lora.close()
    client.close()
    exit(0)
