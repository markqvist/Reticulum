import struct
import time
import RNS

class Packet:
	# Constants
	DATA         = 0x00
	ANNOUNCE     = 0x01
	LINKREQUEST  = 0x02
	PROOF        = 0x03
	types        = [DATA, ANNOUNCE, LINKREQUEST, PROOF]

	HEADER_1     = 0x00		# Normal header format
	HEADER_2     = 0x01		# Header format used for link packets in transport
	HEADER_3     = 0x02		# Reserved
	HEADER_4     = 0x03		# Reserved
	header_types = [HEADER_1, HEADER_2, HEADER_3, HEADER_4]

	# Context types
	NONE 		 = 0x00
	RESOURCE     = 0x01
	RESOURCE_ADV = 0x02
	RESOURCE_REQ = 0x03
	RESOURCE_HMU = 0x04
	RESOURCE_PRF = 0x05
	RESOURCE_ICL = 0x06
	RESOURCE_RCL = 0x07
	REQUEST      = 0x08
	RESPONSE     = 0x09
	COMMAND      = 0x0A
	COMMAND_STAT = 0x0B
	KEEPALIVE    = 0xFC
	LINKCLOSE    = 0xFD
	LRRTT		 = 0xFE
	LRPROOF      = 0xFF

	HEADER_MAXSIZE = 23

	# Defaults
	TIMEOUT 	 = 60

	def __init__(self, destination, data, packet_type = DATA, context = NONE, transport_type = RNS.Transport.BROADCAST, header_type = HEADER_1, transport_id = None):
		if destination != None:
			if transport_type == None:
				transport_type = RNS.Transport.BROADCAST

			self.header_type    = header_type
			self.packet_type    = packet_type
			self.transport_type = transport_type
			self.context        = context

			self.hops		    = 0;
			self.destination    = destination
			self.transport_id   = transport_id
			self.data 		    = data
			self.flags	 	    = self.getPackedFlags()
			self.MTU     		= RNS.Reticulum.MTU

			self.raw    		= None
			self.packed 		= False
			self.sent   		= False
			self.receipt 		= None
			self.fromPacked		= False
		else:
			self.raw            = data
			self.packed         = True
			self.fromPacked     = True

		self.sent_at = None
		self.packet_hash = None

	def getPackedFlags(self):
		if self.context == Packet.LRPROOF:
			packed_flags = (self.header_type << 6) | (self.transport_type << 4) | RNS.Destination.LINK | self.packet_type
		else:
			packed_flags = (self.header_type << 6) | (self.transport_type << 4) | (self.destination.type << 2) | self.packet_type
		return packed_flags

	def pack(self):
		self.header = ""
		self.header += struct.pack("!B", self.flags)
		self.header += struct.pack("!B", self.hops)


		if self.context == Packet.LRPROOF:
			self.header += self.destination.link_id
			self.ciphertext = self.data
		else:
			if self.header_type == Packet.HEADER_1:
				self.header += self.destination.hash

				if self.packet_type == Packet.ANNOUNCE:
					# Announce packets are not encrypted
					self.ciphertext = self.data
				elif self.packet_type == Packet.PROOF and self.context == Packet.RESOURCE_PRF:
					# Resource proofs are not encrypted
					self.ciphertext = self.data
				elif self.context == Packet.RESOURCE:
					# A resource takes care of symmetric
					# encryption by itself
					self.ciphertext = self.data
				elif self.context == Packet.KEEPALIVE:
					# Keepalive packets contain no actual
					# data
					self.ciphertext = self.data
				else:
					# In all other cases, we encrypt the packet
					# with the destination's public key
					self.ciphertext = self.destination.encrypt(self.data)

			if self.header_type == Packet.HEADER_2:
				if t_destination != None:
					self.header += self.t_destination
				else:
					raise IOError("Packet with header type 2 must have a transport ID")




		self.header += chr(self.context)

		self.raw = self.header + self.ciphertext

		if len(self.raw) > self.MTU:
			raise IOError("Packet size of "+str(len(self.raw))+" exceeds MTU of "+str(self.MTU)+" bytes")

		self.packed = True

	def unpack(self):
		self.flags = ord(self.raw[0])
		self.hops  = ord(self.raw[1])

		self.header_type      = (self.flags & 0b11000000) >> 6
		self.transport_type   = (self.flags & 0b00110000) >> 4
		self.destination_type = (self.flags & 0b00001100) >> 2
		self.packet_type      = (self.flags & 0b00000011)

		if self.header_type == Packet.HEADER_2:
			self.transport_id = self.raw[2:12]
			self.destination_hash = self.raw[12:22]
			self.context = ord(self.raw[22:23])
			self.data = self.raw[23:]
		else:
			self.transport_id = None
			self.destination_hash = self.raw[2:12]
			self.context = ord(self.raw[12:13])
			self.data = self.raw[13:]

		self.packed = False

	def send(self):
		if not self.sent:
			if self.destination.type == RNS.Destination.LINK:
				if self.destination.status == RNS.Link.CLOSED:
					raise IOError("Attempt to transmit over a closed link")
				else:
					self.destination.last_outbound = time.time()
					self.destination.tx += 1
					self.destination.txbytes += len(self.data)

			if not self.packed:
				self.pack()
	
			if RNS.Transport.outbound(self):
				return self.receipt
			else:
				# TODO: Don't raise error here, handle gracefully
				raise IOError("Packet could not be sent! Do you have any outbound interfaces configured?")
		else:
			raise IOError("Packet was already sent")

	def resend(self):
		if self.sent:
			Transport.outbound(self.raw)
		else:
			raise IOError("Packet was not sent yet")

	def prove(self, destination=None):
		if self.fromPacked and self.destination:
			if self.destination.identity and self.destination.identity.prv:
				self.destination.identity.prove(self, destination)

	# Generates a special destination that allows Reticulum
	# to direct the proof back to the proved packet's sender
	def generateProofDestination(self):
		return ProofDestination(self)

	def validateProofPacket(self, proof_packet):
		return self.receipt.validateProofPacket(proof_packet)

	def validateProof(self, proof):
		return self.receipt.validateProof(proof)

	def updateHash(self):
		self.packet_hash = self.getHash()

	def getHash(self):
		return RNS.Identity.fullHash(self.getHashablePart())

	def getHashablePart(self):
		return self.raw[0:1]+self.raw[2:]

class ProofDestination:
	def __init__(self, packet):
		self.hash = packet.getHash()[:10];
		self.type = RNS.Destination.SINGLE

	def encrypt(self, plaintext):
		return plaintext


class PacketReceipt:
	# Receipt status constants
	FAILED    = 0x00
	SENT	  = 0x01
	DELIVERED = 0x02


	EXPL_LENGTH = RNS.Identity.HASHLENGTH/8+RNS.Identity.SIGLENGTH/8
	IMPL_LENGTH = RNS.Identity.SIGLENGTH/8

	# Creates a new packet receipt from a sent packet
	def __init__(self, packet):
		self.hash    = packet.getHash()
		self.sent    = True
		self.sent_at = time.time()
		self.timeout = Packet.TIMEOUT
		self.proved  = False
		self.status  = PacketReceipt.SENT
		self.destination = packet.destination
		self.callbacks   = PacketReceiptCallbacks()
		self.concluded_at = None

	# Validate a proof packet
	def validateProofPacket(self, proof_packet):
		return self.validateProof(proof_packet.data)

	# Validate a raw proof
	def validateProof(self, proof):
		if len(proof) == PacketReceipt.EXPL_LENGTH:
			# This is an explicit proof
			proof_hash = proof[:RNS.Identity.HASHLENGTH/8]
			signature = proof[RNS.Identity.HASHLENGTH/8:RNS.Identity.HASHLENGTH/8+RNS.Identity.SIGLENGTH/8]
			if proof_hash == self.hash:
				proof_valid = self.destination.identity.validate(signature, self.hash)
				if proof_valid:
					self.status = PacketReceipt.DELIVERED
					self.proved = True
					if self.callbacks.delivery != None:
						self.callbacks.delivery(self)
					return True
				else:
					return False
			else:
				return False
		elif len(proof) == PacketReceipt.IMPL_LENGTH:
			# This is an implicit proof
			signature = proof[:RNS.Identity.SIGLENGTH/8]
			proof_valid = self.destination.identity.validate(signature, self.hash)
			if proof_valid:
					self.status = PacketReceipt.DELIVERED
					self.proved = True
					if self.callbacks.delivery != None:
						self.callbacks.delivery(self)
					return True
			else:
				return False
		else:
			return False


	def isTimedOut(self):
		return (self.sent_at+self.timeout < time.time())

	def checkTimeout(self):
		if self.isTimedOut():
			self.status = PacketReceipt.FAILED
			self.concluded_at = time.time()
			if self.callbacks.timeout:
				self.callbacks.timeout(self)


	# Set the timeout in seconds
	def setTimeout(self, timeout):
		self.timeout = float(timeout)

	# Set a function that gets called when
	# a successfull delivery has been proved
	def delivery_callback(self, callback):
		self.callbacks.delivery = callback

	# Set a function that gets called if the
	# delivery times out
	def timeout_callback(self, callback):
		self.callbacks.timeout = callback

class PacketReceiptCallbacks:
	def __init__(self):
		self.delivery = None
		self.timeout  = None