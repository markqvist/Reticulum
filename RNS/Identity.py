import base64
import math
import os
import RNS
import time
import atexit
import cPickle
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import load_der_public_key
from cryptography.hazmat.primitives.serialization import load_der_private_key
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric import padding

class Identity:
	# Configure key size
	KEYSIZE    = 1536;
	DERKEYSIZE = 1808;

	# Padding size, not configurable
	PADDINGSIZE= 336;

	# Storage
	known_destinations = {}

	def __init__(self,public_only=False):
		# Initialize keys to none
		self.prv = None
		self.pub = None
		self.prv_bytes = None
		self.pub_bytes = None
		self.hash = None
		self.hexhash = None

		if not public_only:
			self.createKeys()

	@staticmethod
	def remember(packet_hash, destination_hash, public_key, app_data = None):
		RNS.log("Remembering "+RNS.prettyhexrep(destination_hash), RNS.LOG_VERBOSE)
		Identity.known_destinations[destination_hash] = [time.time(), packet_hash, public_key, app_data]


	@staticmethod
	def recall(destination_hash):
		RNS.log("Searching for "+RNS.prettyhexrep(destination_hash)+"...", RNS.LOG_DEBUG)
		if destination_hash in Identity.known_destinations:
			identity_data = Identity.known_destinations[destination_hash]
			identity = Identity(public_only=True)
			identity.loadPublicKey(identity_data[2])
			RNS.log("Found "+RNS.prettyhexrep(destination_hash)+" in known destinations", RNS.LOG_DEBUG)
			return identity
		else:
			RNS.log("Could not find "+RNS.prettyhexrep(destination_hash)+" in known destinations", RNS.LOG_DEBUG)
			return None

	@staticmethod
	def saveKnownDestinations():
		RNS.log("Saving known destinations to storage...", RNS.LOG_VERBOSE)
		file = open(RNS.Reticulum.storagepath+"/known_destinations","w")
		cPickle.dump(Identity.known_destinations, file)
		file.close()
		RNS.log("Done saving known destinations to storage", RNS.LOG_VERBOSE)

	@staticmethod
	def loadKnownDestinations():
		if os.path.isfile(RNS.Reticulum.storagepath+"/known_destinations"):
			file = open(RNS.Reticulum.storagepath+"/known_destinations","r")
			Identity.known_destinations = cPickle.load(file)
			file.close()
			RNS.log("Loaded "+str(len(Identity.known_destinations))+" known destinations from storage", RNS.LOG_VERBOSE)
		else:
			RNS.log("Destinations file does not exist, so no known destinations loaded", RNS.LOG_VERBOSE)

	@staticmethod
	def fullHash(data):
		digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
		digest.update(data)

		return digest.finalize()

	@staticmethod
	def truncatedHash(data):
		digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
		digest.update(data)

		return digest.finalize()[:10]

	@staticmethod
	def validateAnnounce(packet):
		if packet.packet_type == RNS.Packet.ANNOUNCE:
			RNS.log("Validating announce from "+RNS.prettyhexrep(packet.destination_hash), RNS.LOG_VERBOSE)
			destination_hash = packet.destination_hash
			public_key = packet.data[10:Identity.DERKEYSIZE/8+10]
			random_hash = packet.data[Identity.DERKEYSIZE/8+10:Identity.DERKEYSIZE/8+20]
			signature = packet.data[Identity.DERKEYSIZE/8+20:Identity.DERKEYSIZE/8+20+Identity.KEYSIZE/8]
			app_data = ""
			if len(packet.data) > Identity.DERKEYSIZE/8+20+Identity.KEYSIZE/8:
				app_data = packet.data[Identity.DERKEYSIZE/8+20+Identity.KEYSIZE/8:]

			signed_data = destination_hash+public_key+random_hash+app_data

			announced_identity = Identity(public_only=True)
			announced_identity.loadPublicKey(public_key)

			if announced_identity.pub != None and announced_identity.validate(signature, signed_data):
				RNS.log("Announce is valid", RNS.LOG_VERBOSE)
				RNS.Identity.remember(RNS.Identity.fullHash(packet.raw), destination_hash, public_key)
				RNS.log("Stored valid announce from "+RNS.prettyhexrep(destination_hash), RNS.LOG_INFO)
				del announced_identity
				return True
			else:
				RNS.log("Announce is invalid", RNS.LOG_VERBOSE)
				del announced_identity
				return False

	@staticmethod
	def exitHandler():
		Identity.saveKnownDestinations()


	def createKeys(self):
		self.prv = rsa.generate_private_key(
			public_exponent=65337,
			key_size=Identity.KEYSIZE,
			backend=default_backend()
		)
		self.prv_bytes = self.prv.private_bytes(
			encoding=serialization.Encoding.DER,
			format=serialization.PrivateFormat.PKCS8,
			encryption_algorithm=serialization.NoEncryption()
		)
		self.pub = self.prv.public_key()
		self.pub_bytes = self.pub.public_bytes(
			encoding=serialization.Encoding.DER,
			format=serialization.PublicFormat.SubjectPublicKeyInfo
		)

		self.updateHashes()

		RNS.log("Identity keys created for "+RNS.prettyhexrep(self.hash), RNS.LOG_INFO)

	def getPrivateKey(self):
		return self.prv_bytes

	def getPublicKey(self):
		return self.pub_bytes

	def loadPrivateKey(self, key):
		self.prv_bytes = key
		self.prv = serialization.load_der_private_key(self.prv_bytes, password=None,backend=default_backend())
		self.pub = self.prv.public_key()
		self.pub_bytes = self.pub.public_bytes(
			encoding=serialization.Encoding.DER,
			format=serialization.PublicFormat.SubjectPublicKeyInfo
		)
		self.updateHashes()

	def loadPublicKey(self, key):
		try:
			self.pub_bytes = key
			self.pub = load_der_public_key(self.pub_bytes, backend=default_backend())
			self.updateHashes()
		except Exception as e:
			RNS.log("Error while loading public key, the contained exception was: "+str(e), RNS.LOG_ERROR)

	def updateHashes(self):
		self.hash = Identity.truncatedHash(self.pub_bytes)
		self.hexhash = self.hash.encode("hex_codec")

	def saveIdentity(self):
		pass

	def loadIdentity(self):
		pass

	def encrypt(self, plaintext):
		if self.pub != None:
			chunksize = (Identity.KEYSIZE-Identity.PADDINGSIZE)/8
			chunks = int(math.ceil(len(plaintext)/(float(chunksize))))

			ciphertext = "";
			for chunk in range(chunks):
				start = chunk*chunksize
				end = (chunk+1)*chunksize
				if (chunk+1)*chunksize > len(plaintext):
					end = len(plaintext)
				
				ciphertext += self.pub.encrypt(
					plaintext[start:end],
					padding.OAEP(
						mgf=padding.MGF1(algorithm=hashes.SHA1()),
						algorithm=hashes.SHA1(),
						label=None
					)
				)
			return ciphertext
		else:
			raise KeyError("Encryption failed because identity does not hold a public key")


	def decrypt(self, ciphertext):
		if self.prv != None:
			plaintext = None
			try:
				chunksize = (Identity.KEYSIZE)/8
				chunks = int(math.ceil(len(ciphertext)/(float(chunksize))))

				plaintext = "";
				for chunk in range(chunks):
					start = chunk*chunksize
					end = (chunk+1)*chunksize
					if (chunk+1)*chunksize > len(ciphertext):
						end = len(ciphertext)

					plaintext += self.prv.decrypt(
						ciphertext[start:end],
						padding.OAEP(
							mgf=padding.MGF1(algorithm=hashes.SHA1()),
							algorithm=hashes.SHA1(),
							label=None
						)
					)
			except:
				RNS.log("Decryption by "+RNS.prettyhexrep(self.hash)+" failed")
				
			return plaintext;
		else:
			raise KeyError("Decryption failed because identity does not hold a private key")


	def sign(self, message):
		if self.prv != None:
			signer = self.prv.signer(
				padding.PSS(
					mgf=padding.MGF1(hashes.SHA256()),
					salt_length=padding.PSS.MAX_LENGTH
				),
				hashes.SHA256()
			)
			signer.update(message)
			return signer.finalize()
		else:
			raise KeyError("Signing failed because identity does not hold a private key")

	def validate(self, signature, message):
		if self.pub != None:
			try:
				self.pub.verify(
					signature,
					message,
					padding.PSS(
						mgf=padding.MGF1(hashes.SHA256()),
						salt_length=padding.PSS.MAX_LENGTH
					),
					hashes.SHA256()
				)
				return True
			except:
				return False
		else:
			raise KeyError("Signature validation failed because identity does not hold a public key")

	def prove(self, packet, destination):
		proof_data = packet.packet_hash + self.sign(packet.packet_hash)
		proof = RNS.Packet(destination, proof_data, RNS.Packet.PROOF)
		proof.send()


	def getRandomHash(self):
		return self.truncatedHash(os.urandom(10))

