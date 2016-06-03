from __future__ import print_function
from Interface import Interface
import sys
import serial
import threading

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
			print(self.serial.inter_byte_timeout)
		except Exception as e:
			print("Could not create serial port", file=sys.stderr)
			raise e

		#self.serial.open()
		if self.serial.is_open:
			thread = threading.Thread(target=self.readLoop)
			thread.setDaemon(True)
			thread.start()
		else:
			raise IOError("Could not open serial port")


	def processIncoming(self, data):
		self.owner.__class__.incoming(data)


	def processOutgoing(self,data):
		self.serial.write(data)


	def readLoop(self):
		while self.serial.is_open:
			data = self.serial.read(size=self.owner.__class__.MTU)
			if not data == "":
				self.processIncoming(data)




