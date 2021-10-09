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
        self.dbConn.execute("CREATE TABLE IF NOT EXISTS habdata(id INTEGER PRIMARY KEY, data BLOB NOT NULL, chunked INT DEFAULT 0 NOT NULL, created timestamp NOT NULL, ack INT DEFAULT 0 NOT NULL);")

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
        packet.append(0x04) #Channel
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

    def transmit(self):
        try:
            packet = bytearray()
            packet.append(0xbc) #Address High
            packet.append(0x02) #Address Low
            packet.append(0x04) #Channel

            rows = self.dbConn.execute("SELECT * FROM habdata WHERE ack = 0 ORDER BY chunked ASC, created DESC LIMIT 3").fetchall()
            # logging.info(rows)
            for row in rows:
                if len(packet) + len(row[1]) <= 58:
                    packet.append((int(row[0]) & 0xff00) >> 8) # higher byte of id
                    packet.append(int(row[0]) & 0xff) # lower byte of id
                    size = int(len(row[1])) & 0xff
                    size *= (-1 if row[2] else 1)
                    size = size.to_bytes(1, byteorder='big', signed=True)[0]
                    packet.append(size) # size of data
                    packet.extend(row[1]) # data
                else:
                    break

            if len(packet) > 3:
                logging.info("Sending Packet Size: %d Data: %s" % (len(packet), packet.hex()))
                self.ser.write(packet)
                time.sleep(1.25)
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
        CHUNK_SIZE = 53
        isChunked = len(data) > CHUNK_SIZE
        totalChunks = int(len(data) / CHUNK_SIZE) + 1
        try:
            if isChunked:
                logging.info("Data: Chunked %d, totalChunks %d" % (isChunked, totalChunks))
                if totalChunks < 255:
                    for i in range(0, totalChunks):
                        dt = data[i*CHUNK_SIZE:(i+1)*CHUNK_SIZE]
                        packet = bytearray()
                        packet.append(i)
                        packet.append(totalChunks)
                        packet.extend(dt)
                        logging.info("Data added to Queue: %s", packet.hex())
                        self.dbConn.execute("INSERT INTO habdata(data, chunked, created) VALUES (?, 1, datetime('now'));", [sqlite3.Binary(packet)])
                else:
                    logging.error("Unable to send file, check file size")
            else:
                logging.info("Data added to Queue: %s", data.hex())
                self.dbConn.execute("INSERT INTO habdata(data, created) VALUES (?, datetime('now'));", [sqlite3.Binary(data)])
        except Exception as e:
            logging.error("Could not insert to SQLite - %s" % str(e))

    def hasChunkData(self):
        try:
            row = self.dbConn.execute("SELECT COUNT(*) FROM habdata WHERE ack = 0 and chunked = 1").fetchone()
            if row and row[0] > 0:
                logging.info("Chunk pending transmit: %d" % (row[0]))
                return True
            else:
                self.dbConn.execute("DELETE FROM habdata WHERE ack = 1 and chunked = 1")
                return False
        except Exception as e:
            logging.error("Could not read from SQLite - %s" % str(e))
            return False

    def close(self):
        logging.info("Closing Lora Module object")
        GPIO.cleanup()
        self.running = False
        self.ser.close()
        self.ser = None
        self.dbConn.close()
        self.dbConn = None
