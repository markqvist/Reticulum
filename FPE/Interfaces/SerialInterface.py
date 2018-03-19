from __future__ import print_function
from Interface import Interface
from time import sleep
import sys
import serial
import threading
import FPE

class SerialInterface(Interface):
	MAX_CHUNK = 32768
	TIMEOUT_SECONDS = 0.15

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
				timeout = SerialInterface.TIMEOUT_SECONDS,
				xonxoff = False,
				rtscts = False,
				write_timeout = None,
				dsrdtr = False,
			)
		except Exception as e:
			FPE.log("Could not create serial port", FPE.LOG_ERROR)
			raise e

		if self.serial.is_open:
			thread = threading.Thread(target=self.readLoop)
			thread.setDaemon(True)
			thread.start()
			sleep(0.5)
			FPE.log("Serial port "+self.port+" is now open")
		else:
			raise IOError("Could not open serial port")


	def processIncoming(self, data):
		self.owner.inbound(data)


	def processOutgoing(self,data):
		written = self.serial.write(data)
		if written != len(data):
			raise IOError("Serial interface only wrote "+str(written)+" bytes of "+str(len(data)))


	def readLoop(self):
		#pass
		while self.serial.is_open:
			data = self.serial.read(size=self.owner.__class__.MTU)
			if not data == "":
				self.processIncoming(data)




