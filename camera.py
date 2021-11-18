#!/usr/bin/env python3

import time, logging, io
from datetime import datetime
from picamera import PiCamera, Color
from threading import Thread
from PIL import Image

class CameraModule(Thread):
    camera = None
    lastSavedFile = None
    healthy = True

    def __init__(self):
        logging.getLogger("HABControl")
        logging.info('Initialising Camera Module')
        try:
            self.camera = PiCamera()
            self.camera.resolution = (1920, 1080)
            self.camera.meter_mode = 'matrix'
            self.camera.start_preview()
    
            Thread.__init__(self)
            self.healthy = True
            self.start()
        except Exception as e:
            self.healthy = False
            logging.error("Could not Open Camera - %s" % str(e), exc_info=True)
            self.camera = None

    def run(self):
        while self.healthy:
            self.saveCameraImage()
            time.sleep(2)

    def saveCameraImage(self, folder="./images/"):
        try:
            self.camera.annotate_background = Color('black')
            self.camera.annotate_text = "RaliSat-1 : " + datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.camera.annotate_text_size = 32

            filePath = folder + "hab-" + time.strftime("%d-%H%M%S") + ".jpg"
            self.camera.capture(filePath)
            self.lastSavedFile = filePath
        except Exception as e:
            logging.error("Unable to read Camera - %s" % str(e), exc_info=True)
            self.healthy = False

    def getThumbnailImage(self):
        if self.lastSavedFile == None or self.camera == None:
            return None

        try:
            thbnl = Image.open(self.lastSavedFile)
            thbnl.thumbnail((640,360))
            imgByteArr = io.BytesIO()
            thbnl.save(imgByteArr, format="jpeg", quality=75)
            return imgByteArr.getvalue()
        except Exception as e:
            logging.error("Error creating thumbnail image - %s" % str(e), exc_info=True)

    def close(self):
        self.healthy = False
        self.camera.stop_preview()
        self.camera.close()
