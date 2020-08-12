import RNS
import time
import os
import os.path
from .vendor import umsgpack as umsgpack

class Bundle:
	APP_NAME       = "rnsbundle"

	NO_CUSTODY     = 0x00;
	TAKING_CUSTODY = 0x01;
	FULL_CUSTODY   = 0x02;
	REMOVED        = 0xFF;

	CHUNK_SIZE     = RNS.Resource.MAX_EFFICIENT_SIZE / 4

	def __init__(self, destination_hash = None, data = None, filepath = None, advertisement_data = None):
		self.destination_hash  = None
		self.is_originator     = False
		self.state             = None
		self.data_file         = None
		self.meta_file         = None
		self.data_hash         = None
		self.id                = None
		self.storagepath       = None
		self.size              = None
		self.chunks            = 0
		self.created           = time.time()
		self.heartbeat         = created
		self.transferring      = False

		self.chunk_request_destination = None

		try:
			if data != None or filepath != None:
				self.destination_hash  = destination_hash
				self.is_originator = True
				self.id = RNS.Identity.getRandomHash()

				if filepath == None and data != None:
					try:
						self.data_hash = RNS.Identity.fullHash(data)
						self.storagepath  = Reticulum.bundlepath+"/"+self.id.hex()
						self.datapath     = self.storagepath+"/data"
						self.metadatapath = self.storagepath+"/metadata"

						if not os.path.isdir(self.storagepath):
							os.makedirs(self.storagepath)
						else:
							RNS.log("Warning, bundle already exists in storage location, recreating", RNS.LOG_DEBUG)

						self.data_file = open(self.datapath, "wb")
						self.data_file.write(data)
						self.data_file.close()
					except Exception as e:
						RNS.log("Error while initialising bundle from data, the contained exception was:", RNS.LOG_ERROR)
						RNS.log(str(e))

					self.state = Bundle.FULL_CUSTODY

				elif data == None and filepath != None:
					try:
						input_file = open(filepath, "rb")
						self.data_hash = RNS.Identity.fullHash(input_file.read())
						input_file.seek(0)

						self.storagepath  = RNS.Reticulum.bundlepath+"/"+self.id.hex()
						self.datapath     = self.storagepath+"/data"
						self.metadatapath = self.storagepath+"/metadata"

						if not os.path.isdir(self.storagepath):
							os.makedirs(self.storagepath)
						else:
							RNS.log("Warning, bundle already exists in storage location, recreating", RNS.LOG_DEBUG)

						self.data_file = open(self.datapath, "wb")
						self.data_file.write(input_file.read())
						self.data_file.close()
						input_file.close()

					except Exception as e:
						RNS.log("Error while reading input file for bundle, the contained exception was:", RNS.LOG_ERROR)
						RNS.log(str(e))

					self.state = Bundle.FULL_CUSTODY

				else:
					raise ValueError("Bundle cannot be created from data and file path at the same time")

				# Prepare file handles and metadata
				self.size = os.stat(self.datapath).st_size
				if self.size < 1:
					raise IOError("Bundle data is empty")
				self.data_file = open(self.datapath, "rb")

			elif advertisement_data != None:
				# Incoming bundle transfer
				self.id = advertisement_data[1]
				self.destination_hash = advertisement_data[0]
				self.state = Bundle.TAKING_CUSTODY

				self.storagepath  = Reticulum.bundlepath+"/"+self.id.hex()
				self.datapath     = self.storagepath+"/data"
				self.metadatapath = self.storagepath+"/metadata"

				if not os.path.isdir(self.storagepath):
					os.makedirs(self.storagepath)
				else:
					RNS.log("Warning, bundle already exists in storage location, recreating", RNS.LOG_DEBUG)

				self.data_file = open(self.datapath, "wb")
				self.data_file.close()

				self.size = advertisement_data[2]
				self.data_file = open(self.datapath, "wb")

			else:
				raise ValueError("No source of data specified for bundle initialisation")

			self.chunks = ((self.size-1)//Bundle.CHUNK_SIZE)+1
			self.flush_metadata()

			RNS.Transport.register_bundle(self)

		except Exception as e:
			RNS.log("Error while initialising bundle. The contained exception was:", RNS.LOG_ERROR)
			RNS.log(str(e), RNS.LOG_ERROR)
			# TODO: Remove
			raise e

	def get_packed_metadata(self):
		metadata = {
			"destination": self.destination,
			"heartbeat": self.heartbeat,
			"size": self.size,
			"is_originator": self.is_originator
			"state": self.state}

		return umsgpack.packb(metadata)

	def flush_metadata(self):
		try:
			self.meta_file = open(self.metadatapath, "wb")
			self.meta_file.write(self.get_packed_metadata())
			self.meta_file.close()

		except Exception as e:
			RNS.log("Error while flushing metadata for bundle "+RNS.prettyhexrep(self.id), RNS.LOG_ERROR)
			RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)

	def register_destinations(self, destination):
		self.chunk_request_destination = RNS.Destination(None, RNS.Destination.IN, RNS.Destination.SINGLE, APP_NAME, "chunk", "request")
		self.chunk_request_destination.link_established_callback(requester_connected)

	def advertise(self, advertise_to):
		advertisement = [
			self.destination,
			self.id,
			self.size,
			self.chunks]

		advertisement_data = umsgpack.packb(advertisement)
		advertisement_packet = RNS.Packet(advertise_to, advertisement_data)
		advertisement.packet.send()

	def requester_connected(self, link):
		RNS.log("Requester connected to bundle "+RNS.prettyhexrep(self.id), RNS.LOG_DEBUG)
		link.packet_callback(chunk_request)

	def chunk_request(self, data, packet):
		chunk_index = data[0]
		RNS.log("Request for chunk "+str(chunk_index)+"/"+str(self.chunks)+" of bundle "+RNS.prettyhexrep(self.id), RNS.LOG_DEBUG)
		if chunk_index < self.chunks:
			self.emit_resource(packet.link, chunk_index)
		else:
			RNS.log("Bundle transfer client requested chunk index out of range, tearing down link.", RNS.LOG_ERROR)
			packet.link.teardown()

	def emit_resource(self, link, chunk_index):
		if not self.transferring:
			chunk_max   = self.size-1
			chunk_start = chunk_index*CHUNK_SIZE
			chunk_end   = (chunk_index+1)*CHUNK_SIZE-1			
			if chunk_end > chunk_max:
				chunk_end = chunk_max
			read_size = chunk_end - chunk_start

			try:
				file = open(self.datapath, "rb")
				file.seek(chunk_start)
				data = file.read(read_size)
				chunk_resource = RNS.Resource(data, link, callback=resource_concluded)
				chunk_resource.chunk_index = chunk_index
			except Exception as e:
				RNS.log("Could not read bundle data from storage, the contained exception was:", RNS.LOG_ERROR)
				RNS.log(str(e))
				link.teardown()
		else:
			RNS.log("Bundle chunk "+str(chunk_index)+" for "+RNS.prettyhexrep(self.id)+" was requested while a transfer was already in progress", RNS.LOG_ERROR)

	def resource_concluded(self, resource):
		RNS.log("Concluded transferring chunk "+str(resource.chunk_index)+"/"+str(self.chunks)+" of bundle "+RNS.prettyhexrep(self.id), RNS.LOG_DEBUG)
		self.transferring = False

	def resign_custody(self):
		self.state = Bundle.NO_CUSTODY
		self.heartbeat = time.time()

	def custody_proof(self, proof):
		pass

	def remove(self):
		try:
			self.state = Bundle.REMOVED
			RNS.Transport.deregister_destination(self.chunk_request_destination)
			os.unlink(self.datapath)
			os.unlink(self.metadatapath)
			os.rmdir(self.storagepath)
		except Exception as e:
			RNS.log("Error while removing bundle from storage, the contained exception was:", RNS.LOG_ERROR)
			RNS.log(str(e), RNS.LOG_ERROR)




class BundleAdvertisement:
	pass