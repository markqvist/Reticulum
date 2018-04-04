import RNS

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
				RNS.log("Transmitting via: "+str(interface), RNS.LOG_DEBUG)
				interface.processOutgoing(raw)

	@staticmethod
	def inbound(raw, interface=None):
		packet_hash = RNS.Identity.fullHash(raw)
		RNS.log(str(interface)+" received packet with hash "+RNS.prettyhexrep(packet_hash), RNS.LOG_DEBUG)

		if not packet_hash in Transport.packet_hashlist:
			Transport.packet_hashlist.append(packet_hash)
			packet = RNS.Packet(None, raw)
			packet.unpack()
			packet.packet_hash = packet_hash

			if packet.packet_type == RNS.Packet.ANNOUNCE:
				if RNS.Identity.validateAnnounce(packet):
					Transport.cache(packet)
			
			if packet.packet_type == RNS.Packet.RESOURCE:
				for destination in Transport.destinations:
					if destination.hash == packet.destination_hash and destination.type == packet.destination_type:
						packet.destination = destination
						destination.receive(packet)
						Transport.cache(packet)

			if packet.packet_type == RNS.Packet.PROOF:
				for destination in Transport.destinations:
					if destination.hash == packet.destination_hash:
						if destination.proofcallback != None:
							destination.proofcallback(packet)
						# TODO: add universal proof handling

	@staticmethod
	def registerDestination(destination):
		destination.MTU = RNS.Reticulum.MTU
		if destination.direction == RNS.Destination.IN:
			Transport.destinations.append(destination)

	@staticmethod
	def cache(packet):
		RNS.Transport.cacheRaw(packet.raw)

	@staticmethod
	def cacheRaw(raw):
		try:
			file = open(RNS.Reticulum.cachepath+"/"+RNS.hexrep(RNS.Identity.fullHash(raw), delimit=False), "w")
			file.write(raw)
			file.close()
			RNS.log("Wrote packet "+RNS.prettyhexrep(RNS.Identity.fullHash(raw))+" to cache", RNS.LOG_DEBUG)
		except Exception as e:
			RNS.log("Error writing packet to cache", RNS.LOG_ERROR)
			RNS.log("The contained exception was: "+str(e))