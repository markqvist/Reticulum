import os
import RNS
import time
import math
import struct
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

	REACHABILITY_UNREACHABLE = 0x00
	REACHABILITY_DIRECT      = 0x01
	REACHABILITY_TRANSPORT	 = 0x02

	# TODO: Document the addition of random windows
	# and max local rebroadcasts.
	PATHFINDER_M    = 18		# Max hops
	PATHFINDER_C    = 2.0		# Decay constant
	PATHFINDER_R	= 2			# Retransmit retries
	PATHFINDER_T	= 10		# Retry grace period
	PATHFINDER_RW   = 10		# Random window for announce rebroadcast
	PATHFINDER_E    = 60*15		# Path expiration in seconds

	# TODO: Calculate an optimal number for this in
	# various situations
	LOCAL_REBROADCASTS_MAX = 2	# How many local rebroadcasts of an announce is allowed

	interfaces	 	= []		# All active interfaces
	destinations    = []		# All active destinations
	pending_links   = []		# Links that are being established
	active_links	= []		# Links that are active
	packet_hashlist = []		# A list of packet hashes for duplicate detection
	receipts		= []		# Receipts of all outgoing packets for proof processing

	announce_table    = {}		# A table for storing announces currently waiting to be retransmitted
	destination_table = {}		# A lookup table containing the next hop to a given destination
	reverse_table	  = {}		# A lookup table for storing packet hashes used to return proofs and replies

	jobs_locked = False
	jobs_running = False
	job_interval = 0.250
	receipts_last_checked    = 0.0
	receipts_check_interval  = 1.0
	announces_last_checked   = 0.0
	announces_check_interval = 1.0
	hashlist_maxsize         = 1000000

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
		outgoing = []
		Transport.jobs_running = True
		try:
			if not Transport.jobs_locked:
				# Process receipts list for timed-out packets
				if time.time() > Transport.receipts_last_checked+Transport.receipts_check_interval:
					for receipt in Transport.receipts:
						thread = threading.Thread(target=receipt.check_timeout)
						thread.setDaemon(True)
						thread.start()
						if receipt.status != RNS.PacketReceipt.SENT:
							Transport.receipts.remove(receipt)

					Transport.receipts_last_checked = time.time()

				# Process announces needing retransmission
				if time.time() > Transport.announces_last_checked+Transport.announces_check_interval:
					for destination_hash in Transport.announce_table:
						announce_entry = Transport.announce_table[destination_hash]
						if announce_entry[2] > Transport.PATHFINDER_R:
							RNS.log("Dropping announce for "+RNS.prettyhexrep(destination_hash)+", retries exceeded", RNS.LOG_DEBUG)
							Transport.announce_table.pop(destination_hash)
							break
						else:
							if time.time() > announce_entry[1]:
								announce_entry[1] = time.time() + math.pow(Transport.PATHFINDER_C, announce_entry[4]) + Transport.PATHFINDER_T + Transport.PATHFINDER_RW
								announce_entry[2] += 1
								packet = announce_entry[5]
								announce_data = packet.data
								announce_identity = RNS.Identity.recall(packet.destination_hash)
								announce_destination = RNS.Destination(announce_identity, RNS.Destination.OUT, RNS.Destination.SINGLE, "unknown", "unknown");
								announce_destination.hash = packet.destination_hash
								announce_destination.hexhash = announce_destination.hash.encode("hex_codec")
								new_packet = RNS.Packet(announce_destination, announce_data, RNS.Packet.ANNOUNCE, header_type = RNS.Packet.HEADER_2, transport_type = Transport.TRANSPORT, transport_id = Transport.identity.hash)
								new_packet.hops = announce_entry[4]
								RNS.log("Rebroadcasting announce for "+RNS.prettyhexrep(announce_destination.hash)+" with hop count "+str(new_packet.hops), RNS.LOG_DEBUG)
								outgoing.append(new_packet)

					Transport.announces_last_checked = time.time()


				# Cull the packet hashlist if it has reached max size
				while (len(Transport.packet_hashlist) > Transport.hashlist_maxsize):
					Transport.packet_hashlist.pop(0)

				# Cull the reverse table according to max size and/or age of entries
				# TODO: Implement this

				# Cull the destination table in some way
				# TODO: Implement this

		except Exception as e:
			RNS.log("An exception occurred while running Transport jobs.", RNS.LOG_ERROR)
			RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)
			traceback.print_exc()

		Transport.jobs_running = False

		for packet in outgoing:
			packet.send()

	@staticmethod
	def outbound(packet):
		while (Transport.jobs_running):
			sleep(0.01)

		Transport.jobs_locked = True
		# TODO: This updateHash call might be redundant
		packet.updateHash()
		sent = False

		# Check if we have a known path for the destination
		# in the destination table
		if packet.packet_type != RNS.Packet.ANNOUNCE and packet.destination_hash in Transport.destination_table:
			outbound_interface = Transport.destination_table[packet.destination_hash][5]

			if Transport.destination_table[packet.destination_hash][2] > 1:
				# Insert packet into transport
				new_flags = (RNS.Packet.HEADER_2) << 6 | (Transport.TRANSPORT) << 4 | (packet.flags & 0b00001111)
				new_raw = struct.pack("!B", new_flags)
				new_raw += packet.raw[1:2]
				new_raw += Transport.destination_table[packet.destination_hash][1]
				new_raw += packet.raw[2:]
				# RNS.log("Transporting "+str(len(packet.raw))+" bytes via "+RNS.prettyhexrep(Transport.destination_table[packet.destination_hash][1])+" on: "+str(outbound_interface), RNS.LOG_EXTREME)
				# RNS.log("Hash is "+RNS.prettyhexrep(packet.packet_hash), RNS.LOG_EXTREME)
				RNS.log("Packet was inserted into transport via "+RNS.prettyhexrep(Transport.destination_table[packet.destination_hash][1])+" on: "+str(outbound_interface), RNS.LOG_DEBUG)
				outbound_interface.processOutgoing(new_raw)
				sent = True
			else:
				# Destination is directly reachable, and we know on
				# what interface, so transmit only on that one

				# TODO: Strip transport headers here
				RNS.log("Transmitting "+str(len(packet.raw))+" bytes on: "+str(outbound_interface), RNS.LOG_EXTREME)
				RNS.log("Hash is "+RNS.prettyhexrep(packet.packet_hash), RNS.LOG_EXTREME)
				outbound_interface.processOutgoing(packet.raw)
				sent = True
			
		else:
			# Broadcast packet on all outgoing interfaces
			for interface in Transport.interfaces:
				if interface.OUT:
					should_transmit = True
					if packet.destination.type == RNS.Destination.LINK:
						if packet.destination.status == RNS.Link.CLOSED:
							should_transmit = False
						if interface != packet.destination.attached_interface:
							should_transmit = False

					if should_transmit:
						RNS.log("Transmitting "+str(len(packet.raw))+" bytes on: "+str(interface), RNS.LOG_EXTREME)
						RNS.log("Hash is "+RNS.prettyhexrep(packet.packet_hash), RNS.LOG_EXTREME)
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
		else:
			if packet.packet_type == RNS.Packet.ANNOUNCE:
				return True

		RNS.log("Filtered packet with hash "+RNS.prettyhexrep(packet.packet_hash), RNS.LOG_DEBUG)
		return False

	@staticmethod
	def inbound(raw, interface=None):
		# TODO: Rewrite the redundant cache calls in this method
		while (Transport.jobs_running):
			sleep(0.1)
			
		Transport.jobs_locked = True
		
		packet = RNS.Packet(None, raw)
		packet.unpack()
		packet.receiving_interface = interface
		packet.hops += 1

		RNS.log(str(interface)+" received packet with hash "+RNS.prettyhexrep(packet.packet_hash), RNS.LOG_EXTREME)

		if Transport.packet_filter(packet):
			Transport.packet_hashlist.append(packet.packet_hash)
			
			if packet.transport_id != None and packet.packet_type != RNS.Packet.ANNOUNCE:
				if packet.transport_id == Transport.identity.hash:
					RNS.log("Received packet in transport for "+RNS.prettyhexrep(packet.destination_hash)+" with matching transport ID, transporting it...", RNS.LOG_DEBUG)
					if packet.destination_hash in Transport.destination_table:
						next_hop = Transport.destination_table[packet.destination_hash][1]
						RNS.log("Next hop to destination is "+RNS.prettyhexrep(next_hop)+", transporting it.", RNS.LOG_DEBUG)
						new_raw = packet.raw[0:1]
						new_raw += struct.pack("!B", packet.hops)
						new_raw += next_hop
						new_raw += packet.raw[12:]
						outbound_interface = Transport.destination_table[packet.destination_hash][5]
						outbound_interface.processOutgoing(new_raw)

						Transport.reverse_table[packet.packet_hash[:10]] = [packet.receiving_interface, outbound_interface, time.time()]
					else:
						# TODO: There should probably be some kind of REJECT
						# mechanism here, to signal to the source that their
						# expected path failed
						RNS.log("Got packet in transport, but no known path to final destination. Dropping packet.", RNS.LOG_DEBUG)
				else:
					# TODO: Remove this log statement
					RNS.log("Received packet in transport, but transport ID doesn't match, not transporting it further.", RNS.LOG_DEBUG)

			# Announce handling. Handles logic related to incoming
			# announces, queueing rebroadcasts of these, and removal
			# of queued announce rebroadcasts once handed to the next node
			if packet.packet_type == RNS.Packet.ANNOUNCE:
				if RNS.Identity.validateAnnounce(packet):
					if packet.transport_id != None:
						received_from = packet.transport_id
						
						# Check if this is a next retransmission from
						# another node. If it is, we're removing the
						# announce in question from our pending table
						if packet.destination_hash in Transport.announce_table:
							announce_entry = Transport.announce_table[packet.destination_hash]
							
							if packet.hops-1 == announce_entry[4]:
								RNS.log("Heard a local rebroadcast of announce for "+RNS.prettyhexrep(packet.destination_hash), RNS.LOG_DEBUG)
								announce_entry[6] += 1
								if announce_entry[6] >= Transport.LOCAL_REBROADCASTS_MAX:
									RNS.log("Max local rebroadcasts of announce for "+RNS.prettyhexrep(packet.destination_hash)+" reached, dropping announce from our table", RNS.LOG_DEBUG)
									Transport.announce_table.pop(packet.destination_hash)

							if packet.hops-1 == announce_entry[4]+1 and announce_entry[2] > 0:
								now = time.time()
								if now < announce_entry[1]:
									RNS.log("Rebroadcasted announce for "+RNS.prettyhexrep(packet.destination_hash)+" has been passed on to next node, no further tries needed", RNS.LOG_DEBUG)
									Transport.announce_table.pop(packet.destination_hash)

					else:
						received_from = packet.destination_hash

					# Check if this announce should be inserted into
					# announce and destination tables
					should_add = False

					# First, check that the announce is not for a destination
					# local to this system, and that hops are less than the max
					if (not any(packet.destination_hash == d.hash for d in Transport.destinations) and packet.hops < Transport.PATHFINDER_M+1):
						random_blob = packet.data[RNS.Identity.DERKEYSIZE/8+10:RNS.Identity.DERKEYSIZE/8+20]
						random_blobs = []
						if packet.destination_hash in Transport.destination_table:
							random_blobs = Transport.destination_table[packet.destination_hash][4]

							# If we already have a path to the announced
							# destination, but the hop count is equal or
							# less, we'll update our tables.
							if packet.hops <= Transport.destination_table[packet.destination_hash][2]:
								# Make sure we haven't heard the random
								# blob before, so announces can't be
								# replayed to forge paths.
								# TODO: Check whether this approach works
								# under all circumstances
								if not random_blob in random_blobs:
									should_add = True
								else:
									should_add = False
							else:
								# If an announce arrives with a larger hop
								# count than we already have in the table,
								# ignore it, unless the path is expired
								if (time.time() > Transport.destination_table[packet.destination_hash][3]):
									# We also check that the announce hash is
									# different from ones we've already heard,
									# to avoid loops in the network
									if not random_blob in random_blobs:
										# TODO: Check that this ^ approach actually
										# works under all circumstances
										RNS.log("Replacing destination table entry for "+str(RNS.prettyhexrep(packet.destination_hash))+" with new announce due to expired path", RNS.LOG_DEBUG)
										should_add = True
									else:
										should_add = False
								else:
									should_add = False
						else:
							# If this destination is unknown in our table
							# we should add it
							should_add = True

						if should_add:
							now = time.time()
							retries = 0
							expires = now + Transport.PATHFINDER_E
							local_rebroadcasts = 0
							random_blobs.append(random_blob)
							retransmit_timeout = now + math.pow(Transport.PATHFINDER_C, packet.hops) + (RNS.rand() * Transport.PATHFINDER_RW)
							Transport.announce_table[packet.destination_hash] = [now, retransmit_timeout, retries, received_from, packet.hops, packet, local_rebroadcasts]
							Transport.destination_table[packet.destination_hash] = [now, received_from, packet.hops, expires, random_blobs, packet.receiving_interface]
							RNS.log("Path to "+RNS.prettyhexrep(packet.destination_hash)+" is now via "+RNS.prettyhexrep(received_from)+" on "+str(packet.receiving_interface), RNS.LOG_DEBUG)
			
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

					# Check if this proof neds to be transported
					if packet.destination_hash in Transport.reverse_table:
						reverse_entry = Transport.reverse_table[packet.destination_hash]
						if packet.receiving_interface == reverse_entry[1]:
							RNS.log("Proof received on correct interface, transporting it via "+str(reverse_entry[0]), RNS.LOG_DEBUG)
							new_raw = packet.raw[0:1]
							new_raw += struct.pack("!B", packet.hops)
							new_raw += packet.raw[2:]
							reverse_entry[0].processOutgoing(new_raw)
						else:
							RNS.log("Proof received on wrong interface, not transporting it.", RNS.LOG_DEBUG)

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
