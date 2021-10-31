#!/usr/bin/env python3

import logging
from ublox import *
from threading import Thread

class GPSModule(Thread):
    gps = None
    latitude = 0.0
    longitude = 0.0
    altitude = 0.0
    fix_status = 0
    satellites = 0
    healthy = True

    def __init__(self, portname="/dev/ttyUSB0", timeout=2, baudrate=9600):
        logging.getLogger("HABControl")
        logging.info('Initialising GPS Module')
        try:
            self.gps = UBlox(port=portname, timeout=timeout, baudrate=baudrate)
            self.gps.set_binary()

            self.gps.configure_poll_port()
            self.gps.configure_solution_rate(rate_ms=1000)

            self.gps.set_preferred_dynamic_model(DYNAMIC_MODEL_PORTABLE)

            self.gps.configure_message_rate(CLASS_NAV, MSG_NAV_POSLLH, 1)
            self.gps.configure_message_rate(CLASS_NAV, MSG_NAV_SOL, 1)

            Thread.__init__(self)
            self.healthy = True
            self.start()
        except Exception as e:
            logging.error('Unable to initialise GPS: %s' % str(e))
            self.gps = None
            self.healthy = False

    def run(self):
        while self.healthy:
            self.readData()
            time.sleep(1.0)

    def readData(self):
        try:
            msg = self.gps.receive_message()
            logging.debug(msg)
            if msg.name() == "NAV_SOL":
                msg.unpack()
                self.satellites = msg.numSV
                self.fix_status = msg.gpsFix
            elif msg.name() == "NAV_POSLLH":
                msg.unpack()
                self.latitude = msg.Latitude * 1e-7
                self.longitude = msg.Longitude * 1e-7
                self.altitude = msg.hMSL / 1000.0

                if self.altitude < 0.0:
                    self.altitude = 0.0
        except Exception as e:
            logging.error("Unable to read from GPS Chip - %s" % str(e))
            self.healthy = False

    def close(self):
        logging.info("Closing GPS Module object")
        self.healthy = False
        self.gps.close()
        self.gps = None

