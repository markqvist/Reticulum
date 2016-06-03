import struct
from Transport import *

class Packet:

	def __init__(self, destination, data):
		self.destination = destination
		self.data   = data
		self.flags  = 0x00
		self.header = 0x00
		self.raw	= None
		self.sent   = False
		self.mtu    = 0

	def send(self):
		if not self.sent:
			self.MTU = self.destination.MTU
			self.header =  struct.pack("!B", self.header ^ self.destination.type ^ self.flags)
			self.header += self.destination.hash
			self.ciphertext = self.destination.encrypt(self.data)
			self.raw = self.header + self.ciphertext

			if len(self.raw) > self.MTU:
				raise IOError("Packet size exceeds MTU of "+Packet.MTU+" bytes")

			Transport.outbound(self.raw)
			self.sent = True
		else:
			raise IOError("Packet was already sent")

	def resend(self):
		if self.sent:
			Transport.outbound(self.raw)
		else:
			raise IOError("Packet was not sent yet")