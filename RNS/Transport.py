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
	pending_links   = []
	active_links	= []
	packet_hashlist = []

	@staticmethod
	def outbound(packet):
		Transport.cacheRaw(packet.raw)
		for interface in Transport.interfaces:
			if interface.OUT:
				should_transmit = True
				if packet.destination.type == RNS.Destination.LINK:
					if interface != packet.destination.attached_interface:
						should_transmit = False

				if should_transmit:
					RNS.log("Transmitting "+str(len(packet.raw))+" bytes via: "+str(interface), RNS.LOG_DEBUG)
					interface.processOutgoing(packet.raw)

	@staticmethod
	def inbound(raw, interface=None):
		packet_hash = RNS.Identity.fullHash(raw)
		RNS.log(str(interface)+" received packet with hash "+RNS.prettyhexrep(packet_hash), RNS.LOG_DEBUG)

		if not packet_hash in Transport.packet_hashlist:
			Transport.packet_hashlist.append(packet_hash)
			packet = RNS.Packet(None, raw)
			packet.unpack()
			packet.packet_hash = packet_hash
			packet.receiving_interface = interface

			if packet.packet_type == RNS.Packet.ANNOUNCE:
				if RNS.Identity.validateAnnounce(packet):
					Transport.cache(packet)

			if packet.packet_type == RNS.Packet.LINKREQUEST:
				for destination in Transport.destinations:
					if destination.hash == packet.destination_hash and destination.type == packet.destination_type:
						packet.destination = destination
						destination.receive(packet)
						Transport.cache(packet)
			
			if packet.packet_type == RNS.Packet.RESOURCE:
				if packet.destination_type == RNS.Destination.LINK:
					for link in Transport.active_links:
						if link.link_id == packet.destination_hash:
							link.receive(packet)
							Transport.cache(packet)
				else:
					for destination in Transport.destinations:
						if destination.hash == packet.destination_hash and destination.type == packet.destination_type:
							packet.destination = destination
							destination.receive(packet)
							Transport.cache(packet)

			if packet.packet_type == RNS.Packet.PROOF:
				if packet.header_type == RNS.Packet.HEADER_3:
					# This is a link request proof, forward
					# to a waiting link request
					for link in Transport.pending_links:
						if link.link_id == packet.destination_hash:
							link.validateProof(packet)
				else:
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
	def registerLink(link):
		RNS.log("Registering link "+str(link))
		if link.initiator:
			Transport.pending_links.append(link)
		else:
			Transport.active_links.append(link)

	@staticmethod
	def activateLink(link):
		RNS.log("Activating link "+str(link))
		if link in Transport.pending_links:
			Transport.pending_links.remove(link)
			Transport.active_links.append(link)
			link.status = RNS.Link.ACTIVE
		else:
			RNS.log("Attempted to activate a link that was not in the pending table", RNS.LOG_ERROR)


	@staticmethod
	def shouldCache(packet):
		# TODO: Implement sensible rules for which
		# packets to cache
		return False

	@staticmethod
	def cache(packet):
		if RNS.Transport.shouldCache(packet):
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