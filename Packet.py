import struct
from Transport import *

class Packet:
	MTU = 960

	def __init__(self, destination, data):
		self.destination = destination
		self.data   = data
		self.flags  = 0x00
		self.header = 0x00
		self.raw	= None
		self.sent   = False

	def send(self):
		self.header =  struct.pack("!B", self.header ^ self.destination.type ^ self.flags)
		self.header += self.destination.hash
		self.ciphertext = self.destination.encrypt(self.data)
		self.raw = self.header + self.ciphertext

		if len(self.raw) > Packet.MTU:
			raise IOError("Packet size exceeds MTU of "+Packet.MTU+" bytes")

		Transport.outbound(self.raw)