#!/usr/bin/env python3

import bme680, time, logging
from threading import Thread

class BME680Module(Thread):
    sensor = None
    temperature = 0.0
    pressure = 0.0
    humidity = 0.0
    gas_resistance = 0.0
    healthy = True

    def __init__(self):
        logging.getLogger("HABControl")
        logging.info('Initialising BME680(Temp, Humidity and Pressure) Sensor Module')
        try:
            self.sensor = bme680.BME680(bme680.I2C_ADDR_PRIMARY)
            self.sensor.set_humidity_oversample(bme680.OS_2X)
            self.sensor.set_pressure_oversample(bme680.OS_4X)
            self.sensor.set_temperature_oversample(bme680.OS_8X)
            self.sensor.set_filter(bme680.FILTER_SIZE_3)
            self.sensor.set_gas_status(bme680.ENABLE_GAS_MEAS)

            self.sensor.set_gas_heater_temperature(320)
            self.sensor.set_gas_heater_duration(150)
            self.sensor.select_gas_heater_profile(0)

            Thread.__init__(self)
            self.healthy = True
            self.start()
        except Exception as e:
            logging.error('Unable to initialise BME680 Sensor: %s' % str(e), exc_info=True)
            self.healthy = False
            self.sensor = None

    def run(self):
        while self.healthy:
            self.readData()
            time.sleep(2.0)

    def readData(self):
        try:
            if self.sensor.get_sensor_data():
                self.temperature = self.sensor.data.temperature
                self.pressure = self.sensor.data.pressure
                self.humidity = self.sensor.data.humidity

                if self.sensor.data.heat_stable:
                    self.gas_resistance = self.sensor.data.gas_resistance
        except Exception as e:
            logging.error("Unable to read from BME680 sensor - %s" % str(e), exc_info=True)
            self.healthy = False
            self.temperature = 0.0
            self.pressure = 0.0
            self.humidity = 0.0
            self.gas_resistance = 0.0

    def close(self):
        self.healthy = False
