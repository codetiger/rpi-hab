#!/usr/bin/env python3

import time, io, os, logging
import serial
from pathlib import Path
from picamera import PiCamera
from io import BytesIO
from PIL import Image
from gpiozero import DiskUsage, LoadAverage, CPUTemperature
import bme680
from ublox import *
from controldata import *

logging.basicConfig(format='[%(levelname)s]:[%(asctime)s]:%(message)s', filename='habcontrol.log', level=logging.INFO)
# logging.basicConfig(format='[%(levelname)s]:[%(asctime)s]:%(message)s', level=logging.INFO)

logging.info('Starting High Altitude Balloon Controller...')
control_data = HABControlData()

def setupBME680Sensor():
    try:
        sensor = bme680.BME680(bme680.I2C_ADDR_PRIMARY)
        sensor = bme680.BME680(bme680.I2C_ADDR_PRIMARY)
        sensor.set_humidity_oversample(bme680.OS_2X)
        sensor.set_pressure_oversample(bme680.OS_4X)
        sensor.set_temperature_oversample(bme680.OS_8X)
        sensor.set_filter(bme680.FILTER_SIZE_3)
        sensor.set_gas_status(bme680.ENABLE_GAS_MEAS)

        sensor.set_gas_heater_temperature(320)
        sensor.set_gas_heater_duration(150)
        sensor.select_gas_heater_profile(0)

        return sensor
    except (RuntimeError, IOError):
        return None

logging.info(' Initialising BME680(Temp, Humidity and Pressure) Sensor')
sensor = setupBME680Sensor()
if sensor == None:
    logging.error('Unable to initialise BME680 Sensor')

def updateBME680SensorData():
    try:
        sensor.get_sensor_data()
        control_data.env_temperature = sensor.data.temperature
        control_data.env_pressure = sensor.data.pressure
        control_data.env_humidity = sensor.data.humidity

        if sensor.data.heat_stable:
            control_data.env_gas_resistance = sensor.data.gas_resistance

    except Exception as e:
        logging.error("Unable to read from BME680 sensor - %s" % str(e))
        control_data.env_temperature = 0
        control_data.env_pressure = 0
        control_data.env_humidity = 0

def setupGPS():
    try:
        gps = UBlox(port="/dev/serial0", timeout=2, baudrate=9600)
        gps.set_binary()

        gps.configure_poll_port()
        gps.configure_solution_rate(rate_ms=1000)

        gps.set_preferred_dynamic_model(DYNAMIC_MODEL_PORTABLE)

        gps.configure_message_rate(CLASS_NAV, MSG_NAV_POSLLH, 1)
        gps.configure_message_rate(CLASS_NAV, MSG_NAV_SOL, 1)
        return gps
    except Exception as e:
        logging.error("Could not Open GPS - %s" % str(e))
        return None

logging.info(' Initialising GPS Chip')
gps = setupGPS()
if gps == None:
    logging.error('Unable to initialise GPS')

def updateGPSData():
    try:
        for n in range(3):
            msg = gps.receive_message()
            logging.debug(msg)
            if msg.name() in ("NAV_SOL", "NAV_POSLLH"):
                msg.unpack()
                control_data.updateData(msg)
    except Exception as e:
        logging.error("Unable to read from GPS Chip - %s" % str(e))

def setupLoraChip():
    try:
        ser = serial.Serial('/dev/ttyUSB0', 9600, timeout=5, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE)
        logging.info(ser.name)
        return ser
    except Exception as e:
        logging.error("Could not Open Lora Port - %s" % str(e))
        return None

logging.info(' Initialising Lora Chip')
loraSerial = setupLoraChip()
if loraSerial == None:
    logging.error('Unable to initialise Lora Chip')

def sendData2Lora(ser, data):
    try:
        packet = bytearray()
        packet.append(0xbc)
        packet.append(0x02)
        packet.append(0x04)
        packet += data
        logging.info(packet)
        ser.write(packet)
    except Exception as e:
        logging.error("Could not send data to Lora Port - %s" % str(e))

def setupCamera():
    try:
        camera = PiCamera()
        camera.resolution = (1920, 1080)
        camera.meter_mode = 'matrix'
        camera.start_preview()
        return camera
    except Exception as e:
        logging.error("Could not Open Camera - %s" % str(e))
        return None

logging.info(' Initialising Camera')
camera =  setupCamera()
if camera == None:
    logging.error('Unable to initialise camera')

def saveCameraImage():
    try:
        camera.capture("images/hab-" + time.strftime("%d-%H%M%S") + ".jpg")
    except Exception as e:
        logging.error("Unable to read Camera - %s" % str(e))

rpi_disk = DiskUsage()
rpi_load = LoadAverage()
rpi_cpu = CPUTemperature()

def updateRPIData():
    control_data.rpi_cpu_load = round(rpi_load.value * 100)
    control_data.rpi_cpu_temperature = round(rpi_cpu.temperature)
    control_data.rpi_disk_usage = round(rpi_disk.usage)

logging.info('Polling:')
try:
    count = 0
    while True:
        updateBME680SensorData()
        updateGPSData()
        saveCameraImage()

        logging.info(control_data.getData())
        logging.debug(count)
      
        if count >= 5:
            packed_data = control_data.packData()
            sendData2Lora(loraSerial, packed_data)
            count = 0

        count += 1

except KeyboardInterrupt:
    gps.close()
    loraSerial.close()
    camera.stop_preview()
    camera.close()
