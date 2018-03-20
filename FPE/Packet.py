import struct
import time
import FPE

class Packet:
	# Constants
	RESOURCE     = 0x00;
	ANNOUNCE     = 0x01;
	LINKREQUEST  = 0x02;
	PROOF        = 0x03;
	types        = [RESOURCE, ANNOUNCE, LINKREQUEST, PROOF]

	HEADER_1     = 0x00;	# Normal header format
	HEADER_2     = 0x01;	# Header format used for link packets in transport
	HEADER_3     = 0x02;	# Reserved
	HEADER_4     = 0x03;	# Reserved
	header_types = [HEADER_1, HEADER_2, HEADER_3, HEADER_4]

	def __init__(self, destination, data, packet_type = RESOURCE, transport_type = FPE.Transport.BROADCAST, header_type = HEADER_1, transport_id = None):
		if destination != None:
			if transport_type == None:
				transport_type = FPE.Transport.BROADCAST

			self.header_type    = header_type
			self.packet_type    = packet_type
			self.transport_type = transport_type

			self.hops		    = 0;
			self.destination    = destination
			self.transport_id   = transport_id
			self.data 		    = data
			self.flags	 	    = self.getPackedFlags()
			self.MTU     		= self.destination.MTU

			self.raw    		= None
			self.packed 		= False
			self.sent   		= False
			self.fromPacked		= False
		else:
			self.raw            = data
			self.packed         = True
			self.fromPacked     = True

		self.sent_at = None
		self.packet_hash = None

	def getPackedFlags(self):
		packed_flags = (self.header_type << 6) | (self.transport_type << 4) | (self.destination.type << 2) | self.packet_type
		return packed_flags

	def pack(self):
		self.header = ""
		self.header += struct.pack("!B", self.flags)
		self.header += struct.pack("!B", self.hops)
		if self.header_type == Packet.HEADER_2:
			if t_destination != None:
				self.header += self.t_destination
			else:
				raise IOError("Packet with header type 2 must have a transport ID")

		self.header += self.destination.hash
		if self.packet_type != Packet.ANNOUNCE:
			self.ciphertext = self.destination.encrypt(self.data)
		else:
			self.ciphertext = self.data

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
			self.data = self.raw[22:]
		else:
			self.transport_id = None
			self.destination_hash = self.raw[2:12]
			self.data = self.raw[12:]

		self.packed = False

	def send(self):
		if not self.sent:
			self.pack()
			FPE.log("Size: "+str(len(self.raw))+" header is "+str(len(self.header))+" payload is "+str(len(self.ciphertext)), FPE.LOG_DEBUG)
			FPE.Transport.outbound(self.raw)
			self.packet_hash = FPE.Identity.fullHash(self.raw)
			self.sent_at = time.time()
			self.sent = True
		else:
			raise IOError("Packet was already sent")

	def resend(self):
		if self.sent:
			Transport.outbound(self.raw)
		else:
			raise IOError("Packet was not sent yet")

	def prove(self, destination):
		if self.fromPacked and self.destination:
			if self.destination.identity and self.destination.identity.prv:
				self.destination.identity.prove(self, destination)

	def validateProofPacket(self, proof_packet):
		return self.validateProof(proof_packet.data)

	def validateProof(self, proof):
		proof_hash = proof[:32]
		signature = proof[32:]
		if proof_hash == self.packet_hash:
			return self.destination.identity.validate(signature, proof_hash)
		else:
			return False



