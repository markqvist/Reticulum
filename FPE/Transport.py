import FPE

class Transport:
	# Constants
	BROADCAST    = 0x00;
	TRANSPORT    = 0x01;
	RELAY        = 0x02;
	TUNNEL       = 0x03;
	types        = [BROADCAST, TRANSPORT, RELAY, TUNNEL]

	interfaces	 	= []
	destinations    = []
	packet_hashlist = []

	@staticmethod
	def outbound(raw):
		Transport.cacheRaw(raw)
		for interface in Transport.interfaces:
			if interface.OUT:
				FPE.log("Transmitting via: "+str(interface), FPE.LOG_DEBUG)
				interface.processOutgoing(raw)

	@staticmethod
	def inbound(raw):
		packet_hash = FPE.Identity.fullHash(raw)

		if not packet_hash in Transport.packet_hashlist:
			Transport.packet_hashlist.append(packet_hash)
			packet = FPE.Packet(None, raw)
			packet.unpack()
			packet.packet_hash = packet_hash

			if packet.packet_type == FPE.Packet.ANNOUNCE:
				if FPE.Identity.validateAnnounce(packet):
					Transport.cache(packet)
			
			if packet.packet_type == FPE.Packet.RESOURCE:
				for destination in Transport.destinations:
					if destination.hash == packet.destination_hash and destination.type == packet.destination_type:
						packet.destination = destination
						destination.receive(packet)
						Transport.cache(packet)

			if packet.packet_type == FPE.Packet.PROOF:
				for destination in Transport.destinations:
					if destination.hash == packet.destination_hash:
						if destination.proofcallback != None:
							destination.proofcallback(packet)
						# TODO: add universal proof handling

	@staticmethod
	def registerDestination(destination):
		destination.MTU = FPE.FlexPE.MTU
		if destination.direction == FPE.Destination.IN:
			Transport.destinations.append(destination)

	@staticmethod
	def cache(packet):
		FPE.Transport.cacheRaw(packet.raw)

	@staticmethod
	def cacheRaw(raw):
		try:
			file = open(FPE.FlexPE.cachepath+"/"+FPE.hexrep(FPE.Identity.fullHash(raw), delimit=False), "w")
			file.write(raw)
			file.close()
			FPE.log("Wrote packet "+FPE.prettyhexrep(FPE.Identity.fullHash(raw))+" to cache", FPE.LOG_DEBUG)
		except Exception as e:
			FPE.log("Error writing packet to cache", FPE.LOG_ERROR)
			FPE.log("The contained exception was: "+str(e))