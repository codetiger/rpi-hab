#!/usr/bin/env python3

from struct import *

class HABControlData:
    gps_latitude = 0.0
    gps_longitude = 0.0
    gps_altitude = 0
    gps_fix_status = 0
    gps_satellites = 0
    env_temperature = 0.0
    env_pressure = 0.0
    env_humidity = 0.0
    env_gas_resistance = 0.0
    rpi_disk_usage = 0
    rpi_cpu_load = 0
    rpi_cpu_temperature = 0

    def updateData(self, msg):
        if hasattr(msg, 'numSV'):
            self.gps_satellites = msg.numSV
            self.gps_fix_status = msg.gpsFix

        if hasattr(msg, 'Latitude'):
            if self.gps_fix_status >= 2:
                self.gps_latitude = msg.Latitude * 1e-7
                self.gps_longitude = msg.Longitude * 1e-7
            else:
                self.gps_latitude = 0
                self.gps_longitude = 0

            if self.gps_fix_status >= 3:
                self.gps_altitude = round(msg.hMSL / 1000.0)
            else:
                self.gps_altitude = 0

            if self.gps_altitude < 0:
                self.gps_altitude = 0

    def getData(self):
        return (self.gps_latitude, self.gps_longitude, self.gps_altitude, self.gps_fix_status, self.gps_satellites, 
            self.env_temperature, self.env_pressure, self.env_humidity, self.env_gas_resistance,
            self.rpi_disk_usage, self.rpi_cpu_load, self.rpi_cpu_temperature)

    def packData(self):
        fmt = 'ffHBBffffBBB'
        output_data = (
            self.gps_latitude, self.gps_longitude, self.gps_altitude, self.gps_fix_status, self.gps_satellites, 
            self.env_temperature, self.env_pressure, self.env_humidity, self.env_gas_resistance,
            self.rpi_disk_usage, self.rpi_cpu_load, self.rpi_cpu_temperature)

        packed_data = pack(fmt, *output_data)
        return packed_data
