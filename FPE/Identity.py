import base64
import math
import os
import FPE
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
	def remember(hash, public_key, app_data = None):
		FPE.log("Remembering "+FPE.hexrep(hash, False), FPE.LOG_VERBOSE)
		Identity.known_destinations[hash] = [time.time(), public_key, app_data]

	@staticmethod
	def recall(identity):
		pass

	@staticmethod
	def saveKnownDestinations():
		FPE.log("Saving known destinations to storage...", FPE.LOG_VERBOSE)
		file = open(FPE.FlexPE.storagepath+"/known_destinations","w")
		cPickle.dump(Identity.known_destinations, file)
		file.close()
		FPE.log("Done saving known destinations to storage", FPE.LOG_VERBOSE)

	@staticmethod
	def loadKnownDestinations():
		if os.path.isfile(FPE.FlexPE.storagepath+"/known_destinations"):
			file = open(FPE.FlexPE.storagepath+"/known_destinations","r")
			Identity.known_destinations = cPickle.load(file)
			file.close()
			FPE.log("Loaded "+str(len(Identity.known_destinations))+" known destinations from storage", FPE.LOG_VERBOSE)
		else:
			FPE.log("Destinations file does not exist, so no known destinations loaded", FPE.LOG_VERBOSE)

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
		if packet.packet_type == FPE.Packet.ANNOUNCE:
			FPE.log("Validating announce from "+FPE.hexrep(packet.destination_hash), FPE.LOG_VERBOSE)
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

			if announced_identity.validate(signature, signed_data):
				FPE.log("Announce is valid", FPE.LOG_VERBOSE)
				FPE.Identity.remember(destination_hash, public_key)
			else:
				FPE.log("Announce is invalid", FPE.LOG_VERBOSE)

			del announced_identity

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

		self.hash = Identity.truncatedHash(self.pub_bytes)
		self.hexhash = self.hash.encode("hex_codec")

		FPE.log("Identity keys created, private length is "+str(len(self.prv_bytes))+" public length is "+str(len(self.pub_bytes)), FPE.LOG_INFO)

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

	def loadPublicKey(self, key):
		self.pub_bytes = key
		self.pub = load_der_public_key(self.pub_bytes, backend=default_backend())

	def saveIdentity(self):
		pass

	def loadIdentity(self):
		pass

	def encrypt(self, plaintext):
		if self.prv != None:
			chunksize = (Identity.KEYSIZE-Identity.PADDINGSIZE)/8
			chunks = int(math.ceil(len(plaintext)/(float(chunksize))))
			# TODO: Remove debug output print("Plaintext size is "+str(len(plaintext))+", with "+str(chunks)+" chunks")

			ciphertext = "";
			for chunk in range(chunks):
				start = chunk*chunksize
				end = (chunk+1)*chunksize
				if (chunk+1)*chunksize > len(plaintext):
					end = len(plaintext)

				# TODO: Remove debug output print("Processing chunk "+str(chunk+1)+" of "+str(chunks)+". Starting at "+str(start)+" and stopping at "+str(end)+". The length is "+str(len(plaintext[start:end])))
				
				ciphertext += self.pub.encrypt(
					plaintext[start:end],
					padding.OAEP(
						mgf=padding.MGF1(algorithm=hashes.SHA1()),
						algorithm=hashes.SHA1(),
						label=None
					)
				)
			# TODO: Remove debug output print("Plaintext encrypted, ciphertext length is "+str(len(ciphertext))+" bytes.")
			return ciphertext
		else:
			raise KeyError("Encryption failed because identity does not hold a private key")


	def decrypt(self, ciphertext):
		if self.prv != None:
			# TODO: Remove debug output print("Ciphertext length is "+str(len(ciphertext))+". ")
			chunksize = (Identity.KEYSIZE)/8
			chunks = int(math.ceil(len(ciphertext)/(float(chunksize))))

			plaintext = "";
			for chunk in range(chunks):
				start = chunk*chunksize
				end = (chunk+1)*chunksize
				if (chunk+1)*chunksize > len(ciphertext):
					end = len(ciphertext)

				# TODO: Remove debug output print("Processing chunk "+str(chunk+1)+" of "+str(chunks)+". Starting at "+str(start)+" and stopping at "+str(end)+". The length is "+str(len(ciphertext[start:end])))

				plaintext += self.prv.decrypt(
					ciphertext[start:end],
					padding.OAEP(
						mgf=padding.MGF1(algorithm=hashes.SHA1()),
						algorithm=hashes.SHA1(),
						label=None
					)
				)
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

	def getRandomHash(self):
		return self.truncatedHash(os.urandom(10))


def identityExithandler():
	Identity.saveKnownDestinations()

atexit.register(identityExithandler)