#!/usr/bin/env python3

import time, logging
from picamera import PiCamera
from threading import Thread
from PIL import Image
import io

class CameraModule(Thread):
    camera = None
    thumbnail = None

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
            filename = folder + "hab-" + time.strftime("%d-%H%M%S") + ".jpg"
            self.camera.capture(filename)

            thbnl = Image.open(filename)
            thbnl.thumbnail((320,180))
            imgByteArr = io.BytesIO()
            thbnl.save(imgByteArr, format="jpeg", quality=75)
            self.thumbnail = imgByteArr.getvalue()
            # logging.info("Compressed Image Size: %d" % (len(self.thumbnail)))
        except Exception as e:
            logging.error("Unable to read Camera - %s" % str(e))

    def close(self):
        self.running = False
        self.camera.stop_preview()
        self.camera.close()
