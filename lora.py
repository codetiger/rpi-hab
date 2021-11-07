#!/usr/bin/env python3

import serial
import logging, time
from datetime import datetime
import sqlite3
from struct import *
from threading import Thread
import RPi.GPIO as GPIO

AUX_PIN = 18
M0_PIN = 17
M1_PIN = 27

MODE_NORMAL = 0
MODE_WAKEUP = 1
MODE_POWER_SAVING = 2
MODE_SLEEP = 3

MAX_PACKET_SIZE = 58

class LoraModule(Thread):
    ser = None
    dbConn = None
    delayAfterTransmit = 1.5
    lastTransmitTime = None
    addressHigh = 0x0
    addressLow = 0x0
    port = ""
    healthy = True

    def __init__(self, port="/dev/serial0", addressHigh=0xbc, addressLow=0x01, dataTimer=True, delay=1.5):
        logging.getLogger("HABControl")
        logging.info('Initialising Lora Module')
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(AUX_PIN, GPIO.IN)
        GPIO.setup(M0_PIN, GPIO.OUT)
        GPIO.setup(M1_PIN, GPIO.OUT)
        self.delayAfterTransmit = delay
        self.lastTransmitTime = datetime.now()
        self.addressHigh = addressHigh
        self.addressLow = addressLow
        self.port = port

        self.setupPort()

        if dataTimer:
            self.dbConn = sqlite3.connect('data.db', detect_types=sqlite3.PARSE_DECLTYPES, check_same_thread=False)
            self.dbConn.execute("CREATE TABLE IF NOT EXISTS habdata(id INTEGER PRIMARY KEY, data BLOB NOT NULL, chunked INT DEFAULT 0 NOT NULL, created timestamp NOT NULL, ack INT DEFAULT 0 NOT NULL, lasttry timestamp NOT NULL);")

            Thread.__init__(self)
            self.healthy = True
            self.start()

    def setupPort(self):
        self.setMode(MODE_SLEEP)
        try:
            self.ser = serial.Serial(self.port, 9600, timeout=1, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE)
        except Exception as e:
            logging.error("Could not Open Lora Port - %s" % str(e))
            self.ser = None

        self.resetLoraModule(False)
        self.ser.baudrate = 115200

    def resetLoraModule(self, hard=False):
        self.setMode(MODE_SLEEP)
        time.sleep(0.2)

        if hard:
            packet = bytes([0xc4, 0xc4, 0xc4])
            logging.info("Reset Lora Module Data: %s" % (packet.hex()))
            self.ser.write(packet)
            time.sleep(0.2)

        packet = bytes([0xc0, self.addressHigh, self.addressLow, 0x3d, 0x04, 0xc4])
        logging.info("Sending Config Packet Size: %d Data: %s" % (len(packet), packet.hex()))
        self.ser.write(packet)
        time.sleep(0.1)
        res = self.waitForData(6)
        if res is not None:
            logging.info("Config confirmation: %s" % (res.hex()))
        else:
            logging.info("Config confirmation timeout")
        time.sleep(0.1)

        self.setMode(MODE_NORMAL)
        time.sleep(0.1)

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
        while self.healthy:
            if self.ser == None:
                break

            duration = datetime.now() - self.lastTransmitTime
            secondsFromLastTransmit = duration.total_seconds()
            while not GPIO.input(AUX_PIN):
                time.sleep(0.025)
                duration = datetime.now() - self.lastTransmitTime
                secondsFromLastTransmit = duration.total_seconds()
                if secondsFromLastTransmit > 25:
                    self.healthy = False
            time.sleep(0.025)

            if self.ser.in_waiting > 0:
                self.recieveThread()
            elif secondsFromLastTransmit > self.delayAfterTransmit:
                self.transmitThread()

    def transmit(self, data):
        try:
            logging.info("Sending Packet Size: %d Data: %s" % (len(data), data.hex()))
            self.ser.write(data)
            self.ser.flush()
            self.lastTransmitTime = datetime.now()
        except Exception as e:
            logging.error("Could not send data to Lora Port - %s" % str(e), exc_info=True)
            self.healthy = False

    def transmitThread(self):
        try:
            packet = bytearray()
            packet.append(0xbc)
            packet.append(0x02)
            packet.append(0x04)
            rows = self.dbConn.execute("SELECT * FROM habdata WHERE ack = 0 and lasttry < Datetime('now', '-10 seconds') ORDER BY chunked ASC, created DESC LIMIT 5").fetchall()
            for row in rows:
                if len(packet) + len(row[1]) <= MAX_PACKET_SIZE:
                    packet.append(0xda)
                    packet.append((int(row[0]) & 0xff00) >> 8) # higher byte of id
                    packet.append(int(row[0]) & 0xff) # lower byte of id
                    size = int(len(row[1])) & 0xff
                    size *= (-1 if row[2] else 1)
                    size = size.to_bytes(1, byteorder='big', signed=True)[0]
                    packet.append(size) # size of data
                    packet.extend(row[1]) # data
                    self.dbConn.execute("UPDATE habdata SET lasttry = datetime('now') WHERE id = ?", [row[0]])
                else:
                    break

            if len(packet) > 3:
                self.transmit(packet)
        except Exception as e:
            logging.error("Could not send data to Lora - %s" % str(e), exc_info=True)
            self.healthy = False

    def waitForData(self, length, timeout=10):
        callTime = datetime.now()
        while self.ser.in_waiting < length:
            time.sleep(0.025)
            duration = datetime.now() - callTime
            secondsFromCallTime = duration.total_seconds()
            if secondsFromCallTime > timeout:
                return None

        data = self.ser.read(length)
        return data

    def recieveThread(self):
        if self.ser.in_waiting >= 3:
            try:
                data = self.ser.read(3)
                if len(data) == 3 and data[0] == 0xac:
                    high = int(data[1])
                    low = int(data[2])
                    dataid = (high << 8) | low
                    logging.info("Recieved ACK for %d" % (dataid))
                    self.dbConn.execute("UPDATE habdata SET ack = 1 WHERE id = ?", [dataid])
            except Exception as e:
                logging.error("Could not update ack to SQLite - %s" % str(e), exc_info=True)

    def sendData(self, data):
        CHUNK_SIZE = MAX_PACKET_SIZE - 8 # CallSign (1 byte) Dataid (2 bytes), Size (1 byte), Chunk index (2 byte), Total Chunks (2 byte)

        try:
            isChunked = len(data) > CHUNK_SIZE
            totalChunks = int(len(data) / CHUNK_SIZE) + 1
            if totalChunks > 255 * 255:
                logging.error("Unable to send file, check file size")
                return

            if isChunked:
                logging.debug("Data: Chunked %d, totalChunks %d" % (isChunked, totalChunks))
                for i in range(0, totalChunks):
                    dt = data[i*CHUNK_SIZE:(i+1)*CHUNK_SIZE]
                    packet = bytearray()
                    indexBytes = i.to_bytes(2, byteorder='big', signed=False)
                    packet.append(indexBytes[0])
                    packet.append(indexBytes[1])
                    totalChunksBytes = totalChunks.to_bytes(2, byteorder='big', signed=False)
                    packet.append(totalChunksBytes[0])
                    packet.append(totalChunksBytes[1])
                    packet.extend(dt)
                    logging.debug("Data added to Queue: %s", packet.hex())
                    self.dbConn.execute("INSERT INTO habdata(data, chunked, created, lasttry) VALUES (?, 1, datetime('now'), datetime('now'));", [sqlite3.Binary(packet)])
            else:
                logging.debug("Data added to Queue: %s", data.hex())
                self.dbConn.execute("INSERT INTO habdata(data, created, lasttry) VALUES (?, datetime('now'), datetime('now'));", [sqlite3.Binary(data)])
        except Exception as e:
            logging.error("Could not insert to SQLite - %s" % str(e), exc_info=True)

    def hasChunkData(self):
        try:
            row = self.dbConn.execute("SELECT COUNT(*) FROM habdata WHERE ack = 0 and chunked = 1").fetchone()
            if row and row[0] > 0:
                logging.debug("Chunk pending transmit: %d" % (row[0]))
                return True
            else:
                self.dbConn.execute("DELETE FROM habdata WHERE ack = 1 and chunked = 1")
                return False
        except Exception as e:
            logging.error("Could not read from SQLite - %s" % str(e), exc_info=True)
            return False

    def close(self):
        logging.info("Closing Lora Module object")
        self.healthy = False
        self.ser.close()
        self.ser = None
        self.dbConn.close()
        self.dbConn = None
        GPIO.cleanup()
