import os
import RNS
import time
import threading
import traceback
from time import sleep
import vendor.umsgpack as umsgpack

class Transport:
	# Constants
	BROADCAST    = 0x00;
	TRANSPORT    = 0x01;
	RELAY        = 0x02;
	TUNNEL       = 0x03;
	types        = [BROADCAST, TRANSPORT, RELAY, TUNNEL]

	interfaces	 	= []	# All active interfaces
	destinations    = []	# All active destinations
	pending_links   = []	# Links that are being established
	active_links	= []	# Links that are active
	packet_hashlist = []	# A list of packet hashes for duplicate detection
	receipts		= []	# Receipts of all outgoing packets for proof processing

	jobs_locked = False
	jobs_running = False
	job_interval = 0.250
	receipts_last_checked   = 0.0
	receipts_check_interval = 1.0
	hashlist_maxsize        = 1000000

	identity = None

	@staticmethod
	def start():
		if Transport.identity == None:
			transport_identity_path = RNS.Reticulum.configdir+"/transportidentity"
			if os.path.isfile(transport_identity_path):
				Transport.identity = RNS.Identity.from_file(transport_identity_path)				

			if Transport.identity == None:
				RNS.log("No valid Transport Identity on disk, creating...", RNS.LOG_VERBOSE)
				Transport.identity = RNS.Identity()
				Transport.identity.save(transport_identity_path)
			else:
				RNS.log("Loaded Transport Identity from disk", RNS.LOG_VERBOSE)

		packet_hashlist_path = RNS.Reticulum.configdir+"/packet_hashlist"
		if os.path.isfile(packet_hashlist_path):
			try:
				file = open(packet_hashlist_path, "r")
				Transport.packet_hashlist = umsgpack.unpackb(file.read())
				file.close()
			except Exception as e:
				RNS.log("Could not load packet hashlist from disk, the contained exception was: "+str(e), RNS.LOG_ERROR)


		thread = threading.Thread(target=Transport.jobloop)
		thread.setDaemon(True)
		thread.start()

		RNS.log("Transport instance "+str(Transport.identity)+" started")

	@staticmethod
	def jobloop():
		while (True):
			Transport.jobs()
			sleep(Transport.job_interval)

	@staticmethod
	def jobs():
		Transport.jobs_running = True
		try:
			if not Transport.jobs_locked:
				# Process receipts list for timed-out packets
				if Transport.receipts_last_checked+Transport.receipts_check_interval < time.time():
					for receipt in Transport.receipts:
						thread = threading.Thread(target=receipt.check_timeout)
						thread.setDaemon(True)
						thread.start()
						if receipt.status != RNS.PacketReceipt.SENT:
							Transport.receipts.remove(receipt)

					Transport.receipts_last_checked = time.time()

				# Cull the packet hashlist if it has reached max size
				while (len(Transport.packet_hashlist) > Transport.hashlist_maxsize):
					Transport.packet_hashlist.pop(0)

		except Exception as e:
			RNS.log("An exception occurred while running Transport jobs.", RNS.LOG_ERROR)
			RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)
			traceback.print_exc()

		Transport.jobs_running = False

	@staticmethod
	def outbound(packet):
		while (Transport.jobs_running):
			sleep(0.01)

		Transport.jobs_locked = True
		packet.updateHash()
		sent = False
		
		for interface in Transport.interfaces:
			if interface.OUT:
				should_transmit = True
				if packet.destination.type == RNS.Destination.LINK:
					if packet.destination.status == RNS.Link.CLOSED:
						should_transmit = False
					if interface != packet.destination.attached_interface:
						should_transmit = False

				if should_transmit:
					RNS.log("Transmitting "+str(len(packet.raw))+" bytes via: "+str(interface), RNS.LOG_DEBUG)
					interface.processOutgoing(packet.raw)
					sent = True

		if sent:
			packet.sent = True
			packet.sent_at = time.time()

			if (packet.packet_type == RNS.Packet.DATA):
				packet.receipt = RNS.PacketReceipt(packet)
				Transport.receipts.append(packet.receipt)
			
			Transport.cache(packet)

		Transport.jobs_locked = False
		return sent

	@staticmethod
	def packet_filter(packet):
		# TODO: Think long and hard about this
		if packet.context == RNS.Packet.KEEPALIVE:
			return True
		if packet.context == RNS.Packet.RESOURCE_REQ:
			return True
		if packet.context == RNS.Packet.RESOURCE_PRF:
			return True
		if not packet.packet_hash in Transport.packet_hashlist:
			return True

		return False

	@staticmethod
	def inbound(raw, interface=None):
		while (Transport.jobs_running):
			sleep(0.1)
			
		Transport.jobs_locked = True
		
		packet = RNS.Packet(None, raw)
		packet.unpack()
		packet.updateHash()
		packet.receiving_interface = interface

		RNS.log(str(interface)+" received packet with hash "+RNS.prettyhexrep(packet.packet_hash), RNS.LOG_EXTREME)

		# TODO: Rewrite these redundant cache calls
		if Transport.packet_filter(packet):
			Transport.packet_hashlist.append(packet.packet_hash)
			
			if packet.packet_type == RNS.Packet.ANNOUNCE:
				if RNS.Identity.validateAnnounce(packet):
					Transport.cache(packet)
			
			elif packet.packet_type == RNS.Packet.LINKREQUEST:
				for destination in Transport.destinations:
					if destination.hash == packet.destination_hash and destination.type == packet.destination_type:
						packet.destination = destination
						destination.receive(packet)
						Transport.cache(packet)
			
			elif packet.packet_type == RNS.Packet.DATA:
				if packet.destination_type == RNS.Destination.LINK:
					for link in Transport.active_links:
						if link.link_id == packet.destination_hash:
							packet.link = link
							link.receive(packet)
							Transport.cache(packet)
				else:
					for destination in Transport.destinations:
						if destination.hash == packet.destination_hash and destination.type == packet.destination_type:
							packet.destination = destination
							destination.receive(packet)
							Transport.cache(packet)

							if destination.proof_strategy == RNS.Destination.PROVE_ALL:
								packet.prove()

							elif destination.proof_strategy == RNS.Destination.PROVE_APP:
								if destination.callbacks.proof_requested:
									if destination.callbacks.proof_requested(packet):
										packet.prove()

			elif packet.packet_type == RNS.Packet.PROOF:
				if packet.context == RNS.Packet.LRPROOF:
					# This is a link request proof, forward
					# to a waiting link request
					for link in Transport.pending_links:
						if link.link_id == packet.destination_hash:
							link.validateProof(packet)
				elif packet.context == RNS.Packet.RESOURCE_PRF:
					for link in Transport.active_links:
						if link.link_id == packet.destination_hash:
							link.receive(packet)
				else:
					if packet.destination_type == RNS.Destination.LINK:
						for link in Transport.active_links:
							if link.link_id == packet.destination_hash:
								packet.link = link
								# plaintext = link.decrypt(packet.data)
								

					# TODO: Make sure everything uses new proof handling
					if len(packet.data) == RNS.PacketReceipt.EXPL_LENGTH:
						proof_hash = packet.data[:RNS.Identity.HASHLENGTH/8]
					else:
						proof_hash = None

					for receipt in Transport.receipts:
						receipt_validated = False
						if proof_hash != None:
							# Only test validation if hash matches
							if receipt.hash == proof_hash:
								receipt_validated = receipt.validateProofPacket(packet)
						else:
							# In case of an implicit proof, we have
							# to check every single outstanding receipt
							receipt_validated = receipt.validateProofPacket(packet)

						if receipt_validated:
							Transport.receipts.remove(receipt)

		Transport.jobs_locked = False

	@staticmethod
	def registerDestination(destination):
		destination.MTU = RNS.Reticulum.MTU
		if destination.direction == RNS.Destination.IN:
			Transport.destinations.append(destination)

	@staticmethod
	def registerLink(link):
		RNS.log("Registering link "+str(link), RNS.LOG_DEBUG)
		if link.initiator:
			Transport.pending_links.append(link)
		else:
			Transport.active_links.append(link)

	@staticmethod
	def activateLink(link):
		RNS.log("Activating link "+str(link), RNS.LOG_DEBUG)
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
		if packet.context == RNS.Packet.RESOURCE_PRF:
			return True

		return False

	@staticmethod
	def cache(packet):
		if RNS.Transport.shouldCache(packet):
			try:
				packet_hash = RNS.hexrep(packet.getHash(), delimit=False)
				file = open(RNS.Reticulum.cachepath+"/"+packet_hash, "w")
				file.write(packet.raw)
				file.close()
				RNS.log("Wrote packet "+packet_hash+" to cache", RNS.LOG_EXTREME)
			except Exception as e:
				RNS.log("Error writing packet to cache", RNS.LOG_ERROR)
				RNS.log("The contained exception was: "+str(e))

	@staticmethod
	def cache_request_packet(packet):
		if len(packet.data) == RNS.Identity.HASHLENGTH/8:
			packet_hash = RNS.hexrep(packet.data, delimit=False)
			path = RNS.Reticulum.cachepath+"/"+packet_hash
			if os.path.isfile(path):
				file = open(path, "r")
				raw = file.read()
				file.close()
				packet = RNS.Packet(None, raw)
				# TODO: Implement outbound for this


	@staticmethod
	def cache_request(packet_hash):
		RNS.log("Cache request for "+RNS.prettyhexrep(packet_hash), RNS.LOG_EXTREME)
		path = RNS.Reticulum.cachepath+"/"+RNS.hexrep(packet_hash, delimit=False)
		if os.path.isfile(path):
			file = open(path, "r")
			raw = file.read()
			Transport.inbound(raw)
			file.close()
		else:
			cache_request_packet = RNS.Packet(Transport.transport_destination(), packet_hash, context = RNS.Packet.CACHE_REQUEST)

	@staticmethod
	def transport_destination():
		# TODO: implement this
		pass

	@staticmethod
	def exitHandler():
		try:
			packet_hashlist_path = RNS.Reticulum.configdir+"/packet_hashlist"
			file = open(packet_hashlist_path, "w")
			file.write(umsgpack.packb(Transport.packet_hashlist))
			file.close()
		except Exception as e:
			RNS.log("Could not save packet hashlist to disk, the contained exception was: "+str(e), RNS.LOG_ERROR)
