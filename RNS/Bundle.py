import RNS
import time
import os
import os.path
from .vendor import umsgpack as umsgpack

class Bundle:
	NO_CUSTODY     = 0x00;
	TAKING_CUSTODY = 0x01;
	FULL_CUSTODY   = 0x02;

	CHUNK_SIZE     = RNS.Resource.MAX_EFFICIENT_SIZE / 4

	def __init__(self, destination = None, data = None, filepath = None, advertised_id = None):
		self.destination  = destination
		self.state        = None
		self.data_file    = None
		self.meta_file    = None
		self.id           = None
		self.storagepath  = None
		self.size         = None
		self.chunks       = 0
		self.heartbeat    = time.time()
		self.resources    = []

		try:
			if data != None or filepath != None:

				if filepath == None and data != None:
					try:
						self.id = RNS.Identity.fullHash(data)
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
						self.id = RNS.Identity.fullHash(input_file.read())
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

			elif advertised_id != None:
				# Incoming bundle transfer
				self.state = Bundle.TAKING_CUSTODY
			else:
				raise ValueError("No source of data specified for bundle initialisation")

			# Prepare file handles and metadata
			self.size = os.stat(self.datapath).st_size
			if self.size < 1:
				raise IOError("Bundle data is empty")

			self.chunks = ((self.size-1)//Bundle.CHUNK_SIZE)+1
			self.data_file = open(self.datapath, "rb")
			self.flush_metadata()

		except Exception as e:
			RNS.log("Error while initialising bundle. The contained exception was:", RNS.LOG_ERROR)
			RNS.log(str(e), RNS.LOG_ERROR)
			raise e

	def flush_metadata(self):
		try:
			metadata = {
				"destination": self.destination,
				"heartbeat": self.heartbeat,
				"size": self.size,
				"chunks": self.chunks,
				"state": self.state}

			self.meta_file = open(self.metadatapath, "wb")
			self.meta_file.write(umsgpack.packb(metadata))
			self.meta_file.close()

		except Exception as e:
			RNS.log("Error while flushing metadata for bundle "+RNS.prettyhexrep(self.id), RNS.LOG_ERROR)
			RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)

class BundleAdvertisement:
	pass