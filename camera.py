#!/usr/bin/env python3

import time, logging
from picamera import PiCamera
from threading import Thread

class CameraModule(Thread):
    camera = None

    def __init__(self):
        logging.getLogger("HABControl")
        logging.info('Initialising Camera Module')
        try:
            self.camera = PiCamera()
            self.camera.resolution = (1920, 1080)
            self.camera.meter_mode = 'matrix'
            self.camera.start_preview()
        except Exception as e:
            logging.error("Could not Open Camera - %s" % str(e))
            self.camera = None

        Thread.__init__(self)
        self.running = True
        self.start()

    def run(self):
        while self.running:
            self.saveCameraImage()
            time.sleep(1)

    def saveCameraImage(self, folder="./images/"):
        try:
            self.camera.capture(folder + "hab-" + time.strftime("%d-%H%M%S") + ".jpg")
        except Exception as e:
            logging.error("Unable to read Camera - %s" % str(e))

    def close(self):
        self.running = False
        self.camera.stop_preview()
        self.camera.close()
