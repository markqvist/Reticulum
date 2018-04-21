import RNS
import bz2
import math
import time
import threading
import vendor.umsgpack as umsgpack
from time import sleep


class Resource:
	WINDOW_MIN  = 1
	WINDOW_MAX  = 10
	WINDOW      = 5
	MAPHASH_LEN = 4
	SDU         = RNS.Reticulum.MTU - RNS.Packet.HEADER_MAXSIZE
	RANDOM_HASH_SIZE = 4

	DEFAULT_TIMEOUT  = RNS.Packet.TIMEOUT
	MAX_RETRIES      = 3
	ROUNDTRIP_FACTOR = 1.5

	HASHMAP_IS_NOT_EXHAUSTED = 0x00
	HASHMAP_IS_EXHAUSTED = 0xFF

	# Status constants
	NONE 			= 0x00
	QUEUED 			= 0x01
	ADVERTISED 		= 0x02
	TRANSFERRING	= 0x03
	COMPLETE		= 0x04
	FAILED			= 0x05
	CORRUPT			= 0x06

	@staticmethod
	def accept(advertisement_packet, callback=None, progress_callback = None):
		try:
			adv = ResourceAdvertisement.unpack(advertisement_packet.plaintext)

			resource = Resource(None, advertisement_packet.link)
			resource.status = Resource.TRANSFERRING

			resource.flags               = adv.f
			resource.size                = adv.t
			resource.uncompressed_size   = adv.d
			resource.hash                = adv.h
			resource.random_hash         = adv.r
			resource.hashmap_raw         = adv.m
			resource.encrypted           = True if resource.flags & 0x01 else False
			resource.compressed          = True if resource.flags >> 1 & 0x01 else False
			resource.initiator           = False
			resource.callback		     = callback
			resource.__progress_callback = progress_callback
			resource.total_parts	     = int(math.ceil(resource.size/float(Resource.SDU)))
			resource.received_count      = 0
			resource.outstanding_parts   = 0
			resource.parts			     = [None] * resource.total_parts
			resource.window 		     = Resource.WINDOW
			resource.last_activity       = time.time()

			resource.hashmap = [None] * resource.total_parts
			resource.hashmap_height = 0
			resource.waiting_for_hmu = False
			
			resource.link.register_incoming_resource(resource)

			RNS.log("Accepting resource advertisement for "+RNS.prettyhexrep(resource.hash), RNS.LOG_DEBUG)
			resource.link.callbacks.resource_started(resource)

			resource.hashmap_update(0, resource.hashmap_raw)

			return resource
		except Exception as e:
			RNS.log("Could not decode resource advertisement, dropping resource", RNS.LOG_VERBOSE)
			traceback.print_exc()
			return None

	def __init__(self, data, link, advertise=True, auto_compress=True, callback=None, progress_callback=None):
		self.status = Resource.NONE
		self.link = link
		self.rtt = None

		if data != None:
			hashmap_ok = False
			while not hashmap_ok:
				self.initiator         = True
				self.callback          = callback
				self.progress_callback = progress_callback
				self.random_hash       = RNS.Identity.getRandomHash()[:Resource.RANDOM_HASH_SIZE]
				self.uncompressed_data = data
				self.compressed_data   = bz2.compress(self.uncompressed_data)
				self.uncompressed_size = len(self.uncompressed_data)
				self.compressed_size   = len(self.compressed_data)

				self.hash = RNS.Identity.fullHash(data+self.random_hash)
				self.expected_proof = RNS.Identity.fullHash(data+self.hash)

				if (self.compressed_size < self.uncompressed_size and auto_compress):
					self.data = self.compressed_data
					self.compressed = True
					self.uncompressed_data = None
				else:
					self.data = self.uncompressed_data
					self.compressed = False
					self.compressed_data = None

				if not self.link.encryption_disabled():
					self.data = self.link.encrypt(self.data)
					self.encrypted = True
				else:
					self.encrypted = False

				self.size = len(self.data)
				
				self.hashmap = ""
				self.parts  = []
				for i in range(0,int(math.ceil(self.size/float(Resource.SDU)))):
					data = self.data[i*Resource.SDU:(i+1)*Resource.SDU]
					part = RNS.Packet(link, data, context=RNS.Packet.RESOURCE)
					part.pack()
					part.map_hash = self.getMapHash(data)
					self.hashmap += part.map_hash
					self.parts.append(part)

				hashmap_ok = self.checkHashMap()
				if not hashmap_ok:
					RNS.log("Found hash collision in resource map, remapping...", RNS.LOG_VERBOSE)

				if advertise:
					self.advertise()
		else:
			pass


	def checkHashMap(self):
		checked_hashes = []
		for part in self.parts:
			if part.map_hash in checked_hashes:
				return False
			checked_hashes.append(part.map_hash)

		return True

	def hashmap_update_packet(self, plaintext):
		if not self.status == Resource.FAILED:
			update = umsgpack.unpackb(plaintext[RNS.Identity.HASHLENGTH/8:])
			self.hashmap_update(update[0], update[1])


	def hashmap_update(self, segment, hashmap):
		if not self.status == Resource.FAILED:
			seg_len = ResourceAdvertisement.HASHMAP_MAX_LEN
			hashes = len(hashmap)/Resource.MAPHASH_LEN
			for i in range(0,hashes):
				self.hashmap[i+segment*seg_len] = hashmap[i*Resource.MAPHASH_LEN:(i+1)*Resource.MAPHASH_LEN]
				self.hashmap_height += 1

			self.waiting_for_hmu = False
			self.request_next()

	def getMapHash(self, data):
		return RNS.Identity.fullHash(data+self.random_hash)[:Resource.MAPHASH_LEN]

	def advertise(self):
		thread = threading.Thread(target=self.__advertise_job)
		thread.setDaemon(True)
		thread.start()

	def __advertise_job(self):
		data = ResourceAdvertisement(self).pack()
		packet = RNS.Packet(self.link, data, context=RNS.Packet.RESOURCE_ADV)
		while not self.link.ready_for_new_resource():
			self.status = Resource.QUEUED
			sleep(0.25)

		packet.send()
		self.last_activity = time.time()
		self.adv_sent = self.last_activity
		self.rtt = None
		self.status = Resource.ADVERTISED
		self.link.register_outgoing_resource(self)

	def assemble(self):
		if not self.status == Resource.FAILED:
			try:
				RNS.log("Assembling parts...")
				stream = ""
				for part in self.parts:
					stream += part

				if self.encrypted:
					data = self.link.decrypt(stream)
				else:
					data = stream

				if self.compressed:
					self.data = bz2.decompress(data)
				else:
					self.data = data

				calculated_hash = RNS.Identity.fullHash(self.data+self.random_hash)

				if calculated_hash == self.hash:
					self.status = Resource.COMPLETE
					self.prove()
				else:
					self.status = Resource.CORRUPT

			except Exception as e:
				RNS.log("Error while assembling received resource.", RNS.LOG_ERROR)
				RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)
				self.status = Resource.CORRUPT

			if self.callback != None:
				self.callback(self)


	def prove(self):
		if not self.status == Resource.FAILED:
			proof = RNS.Identity.fullHash(self.data+self.hash)
			proof_data = self.hash+proof
			proof_packet = RNS.Packet(self.link, proof_data, packet_type=RNS.Packet.PROOF, context=RNS.Packet.RESOURCE_PRF)
			proof_packet.send()

	def validateProof(self, proof_data):
		if not self.status == Resource.FAILED:
			if len(proof_data) == RNS.Identity.HASHLENGTH/8*2:
				if proof_data[RNS.Identity.HASHLENGTH/8:] == self.expected_proof:
					self.status = Resource.COMPLETE
					if self.callback != None:
						self.callback(self)
				else:
					pass
			else:
				pass


	def receive_part(self, packet):
		self.last_activity = time.time()
		if self.req_resp == None:
			self.req_resp = self.last_activity
			rtt = self.req_resp-self.req_sent
			if self.rtt == None:
				self.rtt = rtt
			elif self.rtt < rtt:
				self.rtt = rtt

		if not self.status == Resource.FAILED:
			self.status = Resource.TRANSFERRING
			part_data = packet.data
			part_hash = self.getMapHash(part_data)

			i = 0
			for map_hash in self.hashmap:
				if map_hash == part_hash:
					if self.parts[i] == None:
						self.parts[i] = part_data
						self.received_count += 1
						self.outstanding_parts -= 1
				i += 1

			if self.__progress_callback != None:
				self.__progress_callback(self)

			if self.outstanding_parts == 0 and self.received_count == self.total_parts:
				self.assemble()
			elif self.outstanding_parts == 0:
				if self.window < Resource.WINDOW_MAX:
					self.window += 1
				self.request_next()

	# Called on incoming resource to send a request for more data
	def request_next(self):
		if not self.status == Resource.FAILED:
			if not self.waiting_for_hmu:
				self.outstanding_parts = 0
				hashmap_exhausted = Resource.HASHMAP_IS_NOT_EXHAUSTED
				requested_hashes = ""

				i = 0; pn = 0
				for part in self.parts:
					
					if part == None:
						part_hash = self.hashmap[pn]
						if part_hash != None:
							requested_hashes += part_hash
							self.outstanding_parts += 1
							i += 1
						else:
							hashmap_exhausted = Resource.HASHMAP_IS_EXHAUSTED

					pn += 1
					if i >= self.window or hashmap_exhausted == Resource.HASHMAP_IS_EXHAUSTED:
						break

				hmu_part = chr(hashmap_exhausted)
				if hashmap_exhausted == Resource.HASHMAP_IS_EXHAUSTED:
					last_map_hash = self.hashmap[self.hashmap_height-1]
					hmu_part += last_map_hash
					self.waiting_for_hmu = True

				request_data = hmu_part + self.hash + requested_hashes
				request_packet = RNS.Packet(self.link, request_data, context = RNS.Packet.RESOURCE_REQ)

				request_packet.send()
				self.last_activity = time.time()
				self.req_sent = self.last_activity
				self.req_resp = None

	# Called on outgoing resource to make it send more data
	def request(self, request_data):
		if not self.status == Resource.FAILED:
			rtt = time.time() - self.adv_sent
			if self.rtt == None:
				self.rtt = rtt

			self.status == Resource.TRANSFERRING
			wants_more_hashmap = True if ord(request_data[0]) == Resource.HASHMAP_IS_EXHAUSTED else False
			pad = 1+Resource.MAPHASH_LEN if wants_more_hashmap else 1

			requested_hashes = request_data[pad+RNS.Identity.HASHLENGTH/8:]

			for i in range(0,len(requested_hashes)/Resource.MAPHASH_LEN):
				requested_hash = requested_hashes[i*Resource.MAPHASH_LEN:(i+1)*Resource.MAPHASH_LEN]
				
				i = 0
				for part in self.parts:
					if part.map_hash == requested_hash:
						if not part.sent:
							part.send()
						else:
							part.resend()
						self.last_activity = time.time()
						break
					i += 1

			if wants_more_hashmap:
				last_map_hash = request_data[1:Resource.MAPHASH_LEN+1]
				
				part_index = 0
				for part in self.parts:
					part_index += 1
					if part.map_hash == last_map_hash:
						break

				if part_index % ResourceAdvertisement.HASHMAP_MAX_LEN != 0:
					RNS.log("Resource sequencing error, cancelling transfer!", RNS.LOG_ERROR)
					self.cancel()
				else:
					segment = part_index / ResourceAdvertisement.HASHMAP_MAX_LEN

				
				hashmap_start = segment*ResourceAdvertisement.HASHMAP_MAX_LEN
				hashmap_end   = min((segment+1)*ResourceAdvertisement.HASHMAP_MAX_LEN, len(self.parts))

				hashmap = ""
				for i in range(hashmap_start,hashmap_end):
					hashmap += self.hashmap[i*Resource.MAPHASH_LEN:(i+1)*Resource.MAPHASH_LEN]

				hmu = self.hash+umsgpack.packb([segment, hashmap])
				hmu_packet = RNS.Packet(self.link, hmu, context = RNS.Packet.RESOURCE_HMU)
				hmu_packet.send()
				self.last_activity = time.time()

	def cancel(self):
		self.status = Resource.FAILED
		if self.initiator:
			cancel_packet = RNS.Packet(self.link, self.hash, context=RNS.Packet.RESOURCE_ICL)
			cancel_packet.send()
			self.link.cancel_outgoing_resource(self)
		else:
			self.link.cancel_incoming_resource(self)
		
		if self.callback != None:
			self.callback(self)

	def progress_callback(self, callback):
		self.__progress_callback = callback

	def progress(self):
		progress = self.received_count / float(self.total_parts)
		return progress

	def __str__(self):
		return RNS.prettyHexRep(self.hash)


class ResourceAdvertisement:
	# TODO: Can this be allocated dynamically? Keep in mind hashmap_update inference
	HASHMAP_MAX_LEN = 84

	def __init__(self, resource=None):
		if resource != None:
			self.t = resource.size 				  # Transfer size
			self.d = resource.uncompressed_size   # Data size
			self.n = len(resource.parts) 		  # Number of parts
			self.h = resource.hash 				  # Resource hash
			self.r = resource.random_hash		  # Resource random hash
			self.m = resource.hashmap			  # Resource hashmap
			self.c = resource.compressed   		  # Compression flag
			self.e = resource.encrypted    		  # Encryption flag
			self.f  = 0x00 | self.c << 1 | self.e # Flags

	def pack(self, segment=0):
		hashmap_start = segment*ResourceAdvertisement.HASHMAP_MAX_LEN
		hashmap_end   = min((segment+1)*ResourceAdvertisement.HASHMAP_MAX_LEN, self.n)

		hashmap = ""
		for i in range(hashmap_start,hashmap_end):
			hashmap += self.m[i*Resource.MAPHASH_LEN:(i+1)*Resource.MAPHASH_LEN]

		dictionary = {
			u"t": self.t,
			u"d": self.d,
			u"n": self.n,
			u"h": self.h,
			u"r": self.r,
			u"f": self.f,
			u"m": hashmap
		}

		return umsgpack.packb(dictionary)

	@staticmethod
	def unpack(data):
		dictionary = umsgpack.unpackb(data)
		
		adv   = ResourceAdvertisement()
		adv.t = dictionary["t"]
		adv.d = dictionary["d"]
		adv.n = dictionary["n"]
		adv.h = dictionary["h"]
		adv.r = dictionary["r"]
		adv.m = dictionary["m"]
		adv.f = dictionary["f"]
		adv.e = True if (adv.f & 0x01) == 0x01 else False
		adv.c = True if ((adv.f >> 1) & 0x01) == 0x01 else False

		return adv
