from __future__ import print_function
from Interface import Interface
from time import sleep
import sys
import serial
import threading
import time
import FPE

class SerialInterface(Interface):
	MAX_CHUNK = 32768

	owner    = None
	port     = None
	speed    = None
	databits = None
	parity   = None
	stopbits = None
	serial   = None

	def __init__(self, owner, port, speed, databits, parity, stopbits):
		self.serial   = None
		self.owner    = owner
		self.port     = port
		self.speed    = speed
		self.databits = databits
		self.parity   = serial.PARITY_NONE
		self.stopbits = stopbits
		self.timeout  = 100
		self.online   = False

		if parity.lower() == "e" or parity.lower() == "even":
			self.parity = serial.PARITY_EVEN

		if parity.lower() == "o" or parity.lower() == "odd":
			self.parity = serial.PARITY_ODD

		try:
			FPE.log("Opening serial port "+self.port+"...")
			self.serial = serial.Serial(
				port = self.port,
				baudrate = self.speed,
				bytesize = self.databits,
				parity = self.parity,
				stopbits = self.stopbits,
				xonxoff = False,
				rtscts = False,
				timeout = 0,
				inter_byte_timeout = None,
				write_timeout = None,
				dsrdtr = False,
			)
		except Exception as e:
			FPE.log("Could not create serial port", FPE.LOG_ERROR)
			raise e

		if self.serial.is_open:
			sleep(0.5)
			thread = threading.Thread(target=self.readLoop)
			thread.setDaemon(True)
			thread.start()
			self.online = True
			FPE.log("Serial port "+self.port+" is now open")
		else:
			raise IOError("Could not open serial port")


	def processIncoming(self, data):
		self.owner.inbound(data)


	def processOutgoing(self,data):
		if self.online:
			written = self.serial.write(data)
			if written != len(data):
				raise IOError("Serial interface only wrote "+str(written)+" bytes of "+str(len(data)))


	def readLoop(self):
		try:
			data_buffer = ""
			last_read_ms = int(time.time()*1000)
			while self.serial.is_open:
				if self.serial.in_waiting:
					data = self.serial.read(size=self.serial.in_waiting)
					data_buffer += data
					last_read_ms = int(time.time()*1000)
				else:
					time_since_last = int(time.time()*1000) - last_read_ms
					if len(data_buffer) > 0 and time_since_last > self.timeout:
						self.processIncoming(data_buffer)
						data_buffer = ""
					sleep(0.08)
		except Exception as e:
			self.online = False
			FPE.log("A serial port error occurred, the contained exception was: "+str(e), FPE.LOG_ERROR)
			FPE.log("The interface "+str(self.name)+" is now offline. Restart FlexPE to attempt reconnection.", FPE.LOG_ERROR)

