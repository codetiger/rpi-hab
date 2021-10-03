#!/usr/bin/env python3

import serial
import logging, time
from datetime import datetime
import sqlite3
from threading import Thread
import RPi.GPIO as GPIO

AUX_PIN = 18
M0_PIN = 17
M1_PIN = 27

MODE_NORMAL = 0
MODE_WAKEUP = 1
MODE_POWER_SAVING = 2
MODE_SLEEP = 3

class LoraModule(Thread):
    ser = None
    dbConn = None
    running = True

    def __init__(self):
        logging.getLogger("HABControl")
        logging.info('Initialising Lora Module')
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(AUX_PIN, GPIO.IN)
        GPIO.setup(M0_PIN, GPIO.OUT)
        GPIO.setup(M1_PIN, GPIO.OUT)

        self.setupPort()
        self.dbConn = sqlite3.connect('data.db', detect_types=sqlite3.PARSE_DECLTYPES, check_same_thread=False)
        self.dbConn.execute("CREATE TABLE IF NOT EXISTS habdata(id INTEGER PRIMARY KEY, data BLOB NOT NULL, created timestamp NOT NULL, ack INT DEFAULT 0 NOT NULL);")

        Thread.__init__(self)
        self.running = True
        self.start()

    def setupPort(self):
        self.setMode(MODE_SLEEP)
        try:
            self.ser = serial.Serial("/dev/serial0", 9600, timeout=1, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE)
        except Exception as e:
            logging.error("Could not Open Lora Port - %s" % str(e))
            self.ser = None

        packet = bytearray()
        packet.append(0xc0)
        packet.append(0xbc) #Address High
        packet.append(0x01) #Address Low
        packet.append(0x3a)
        packet.append(0x04) #Chennal
        packet.append(0xc4)

        logging.info("Sending Config Packet Size: %d Data: %s" % (len(packet), packet.hex()))
        self.ser.write(packet)
        time.sleep(0.1)
        self.setMode(MODE_NORMAL)
        time.sleep(0.1)
        self.ser.baudrate = 115200

    def setMode(self, mode):
        if mode == MODE_NORMAL:
            logging.info("Setting Lora for Normal Mode")
            GPIO.output(M0_PIN, GPIO.LOW)
            GPIO.output(M1_PIN, GPIO.LOW)
        elif mode == MODE_WAKEUP:
            logging.info("Setting Lora for Wakeup Mode")
            GPIO.output(M0_PIN, GPIO.HIGH)
            GPIO.output(M1_PIN, GPIO.LOW)
        elif mode == MODE_POWER_SAVING:
            logging.info("Setting Lora for Power Saving Mode")
            GPIO.output(M0_PIN, GPIO.LOW)
            GPIO.output(M1_PIN, GPIO.HIGH)
        elif mode == MODE_SLEEP:
            logging.info("Setting Lora for Sleep Mode")
            GPIO.output(M0_PIN, GPIO.HIGH)
            GPIO.output(M1_PIN, GPIO.HIGH)

    def run(self):
        while self.running:
            aux_state = GPIO.input(AUX_PIN)
            # logging.info("Aux State: %d Bytes Waiting: %d" % (aux_state, self.ser.in_waiting))

            if self.ser and self.ser.in_waiting > 0:
                self.recieve()

            if self.ser and aux_state and self.ser.in_waiting == 0:
                self.transmit()

            time.sleep(1.2)

    def transmit(self):
        try:
            row = self.dbConn.execute("SELECT * FROM habdata WHERE ack = 0 ORDER BY created DESC LIMIT 1").fetchone()

            if row:
                packet = bytearray()
                packet.append(0xbc) #Address High
                packet.append(0x02) #Address Low
                packet.append(0x04) #Chennal
                packet.append((int(row[0]) & 0xff00) >> 8) # higher byte of id
                packet.append(int(row[0]) & 0xff) # lower byte of id
                packet.append(int(len(row[1])) & 0xff) # size of data
                packet.extend(row[1]) # data

                logging.info("Sending Packet Size: %d Data: %s" % (len(packet), packet.hex()))
                self.ser.write(packet)
            else:
                logging.info("No data to send")

        except Exception as e:
            logging.error("Could not send data to Lora Port - %s" % str(e))

    def recieve(self):
        if self.ser.in_waiting >= 2:
            try:
                data = self.ser.read(2)
                if len(data) == 2:
                    high = int(data[0])
                    low = int(data[1])
                    dataid = (high << 8) | low
                    logging.info("Recieved ACK for %d" % (dataid))
                    self.dbConn.execute("UPDATE habdata SET ack = 1 WHERE id = ?", [dataid])
            except Exception as e:
                logging.error("Could not update ack to SQLite - %s" % str(e))

    def sendData(self, data):
        try:
            self.dbConn.execute("INSERT INTO habdata(data, created) VALUES (?, datetime('now'));", [sqlite3.Binary(data)])
        except Exception as e:
            logging.error("Could not insert to SQLite - %s" % str(e))

    def close(self):
        logging.info("Closing Lora Module object")
        GPIO.cleanup()
        self.running = False
        self.ser.close()
        self.ser = None
        self.dbConn.close()
        self.dbConn = None
