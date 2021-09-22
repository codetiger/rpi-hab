#!/usr/bin/env python3

import serial
import logging

class LoraModule:
    ser = None

    def __init__(self, portname= "/dev/ttyUSB0", baudrate=9600, timeout=5):
        logging.getLogger("HABControl")
        logging.info('Initialising Lora Module')
        try:
            self.ser = serial.Serial(portname, baudrate, timeout=timeout, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE)
        except Exception as e:
            logging.error("Could not Open Lora Port - %s" % str(e))
            self.ser = None

    def sendData(self, data, addhigh=0xbc, addlow=0x02, channel=0x04):
        try:
            packet = bytearray()
            packet.append(addhigh)
            packet.append(addlow)
            packet.append(channel)
            packet += data
            self.ser.write(packet)
        except Exception as e:
            logging.error("Could not send data to Lora Port - %s" % str(e))

    def close(self):
        self.ser.close()
