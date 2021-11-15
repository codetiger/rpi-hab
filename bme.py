#!/usr/bin/env python3

import bme680, time, logging
from threading import Thread

class BME680Module(Thread):
    sensor = None
    temperature = 0.0
    pressure = 0.0
    humidity = 0.0
    airQuality = 0
    healthy = True
    burnInStartTime = time.time()
    burnInDuration = 300
    burnInData = []
    gasBaseline = 0
    isBurnInProgress = True

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
            time.sleep(1.0)

    def readData(self):
        hum_baseline = 40.0
        hum_weighting = 0.25
        try:
            if self.sensor.get_sensor_data():
                self.temperature = self.sensor.data.temperature
                self.pressure = self.sensor.data.pressure
                self.humidity = self.sensor.data.humidity

                if self.isBurnInProgress:
                    if time.time() - self.burnInStartTime < self.burnInDuration:
                        if self.sensor.data.heat_stable:
                            self.burnInData.append(self.sensor.data.gas_resistance)
                    else:
                        self.isBurnInProgress = False
                        self.gasBaseline = sum(self.burnInData[-50:]) / 50.0
                elif self.sensor.data.heat_stable:
                    gas = self.sensor.data.gas_resistance
                    gas_offset = self.gasBaseline - gas

                    hum = self.sensor.data.humidity
                    hum_offset = hum - hum_baseline

                    # Calculate hum_score as the distance from the hum_baseline.
                    if hum_offset > 0:
                        hum_score = (100 - hum_baseline - hum_offset)
                        hum_score /= (100 - hum_baseline)
                    else:
                        hum_score = (hum_baseline + hum_offset)
                        hum_score /= hum_baseline
                    hum_score *= (hum_weighting * 100)

                    # Calculate gas_score as the distance from the gas_baseline.
                    if gas_offset > 0:
                        gas_score = (gas / self.gasBaseline)
                        gas_score *= (100 - (hum_weighting * 100))
                    else:
                        gas_score = 100 - (hum_weighting * 100)

                    # Calculate air_quality_score.
                    self.airQuality = hum_score + gas_score

        except Exception as e:
            logging.error("Unable to read from BME680 sensor - %s" % str(e), exc_info=True)
            self.healthy = False
            self.temperature = 0.0
            self.pressure = 0.0
            self.humidity = 0.0
            self.airQuality = 0.0

    def close(self):
        self.healthy = False
