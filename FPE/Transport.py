import FPE

class Transport:
	# Constants
	BROADCAST    = 0x00;
	TRANSPORT    = 0x01;
	RELAY        = 0x02;
	TUNNEL       = 0x03;
	types        = [BROADCAST, TRANSPORT, RELAY, TUNNEL]

	packet_hashlist = []

	@staticmethod
	def outbound(raw):
		FPE.FlexPE.outbound(raw)

	@staticmethod
	def inbound(raw):
		packet_hash = FPE.Identity.fullHash(raw)

		if not packet_hash in Transport.packet_hashlist:
			Transport.packet_hashlist.append(packet_hash)
			packet = FPE.Packet(None, raw)
			packet.unpack()

			if packet.packet_type == FPE.Packet.ANNOUNCE:
				FPE.Identity.validateAnnounce(packet)
			
			if packet.packet_type == FPE.Packet.RESOURCE:
				for destination in FlexPE.destinations:
					if destination.hash == packet.destination_hash and destination.type == packet.destination_type:
						destination.receive(packet.data)

	@staticmethod
	def registerDestination(destination):
		FPE.FlexPE.addDestination(destination)