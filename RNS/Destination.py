import base64
import math
import RNS

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric import padding

class Callbacks:
	def __init__(self):
		self.link_established = None
		self.packet = None
		self.proof_requested = None

class Destination:
	KEYSIZE    = RNS.Identity.KEYSIZE;
	PADDINGSIZE= RNS.Identity.PADDINGSIZE;

	# Constants
	SINGLE     = 0x00
	GROUP      = 0x01
	PLAIN      = 0x02
	LINK       = 0x03
	types      = [SINGLE, GROUP, PLAIN, LINK]

	PROVE_NONE = 0x21
	PROVE_APP  = 0x22
	PROVE_ALL  = 0x23
	proof_strategies = [PROVE_NONE, PROVE_APP, PROVE_ALL]

	IN         = 0x11;
	OUT        = 0x12;
	directions = [IN, OUT]

	@staticmethod
	def getDestinationName(app_name, *aspects):
		# Check input values and build name string
		if "." in app_name: raise ValueError("Dots can't be used in app names")

		name = app_name
		for aspect in aspects:
			if "." in aspect: raise ValueError("Dots can't be used in aspects")
			name = name + "." + aspect

		return name


	@staticmethod
	def getDestinationHash(app_name, *aspects):
		name = Destination.getDestinationName(app_name, *aspects)

		# Create a digest for the destination
		digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
		digest.update(name.encode("UTF-8"))

		return digest.finalize()[:10]


	def __init__(self, identity, direction, type, app_name, *aspects):
		# Check input values and build name string
		if "." in app_name: raise ValueError("Dots can't be used in app names") 
		if not type in Destination.types: raise ValueError("Unknown destination type")
		if not direction in Destination.directions: raise ValueError("Unknown destination direction")
		self.callbacks = Callbacks()
		self.type = type
		self.direction = direction
		self.proof_strategy = Destination.PROVE_NONE
		self.mtu = 0

		self.links = []

		if identity != None and type == Destination.SINGLE:
			aspects = aspects+(identity.hexhash,)

		if identity == None and direction == Destination.IN and self.type != Destination.PLAIN:
			identity = RNS.Identity()
			aspects = aspects+(identity.hexhash,)

		self.identity = identity

		self.name = Destination.getDestinationName(app_name, *aspects)		
		self.hash = Destination.getDestinationHash(app_name, *aspects)
		self.hexhash = self.hash.hex()

		self.callback = None
		self.proofcallback = None

		RNS.Transport.registerDestination(self)


	def __str__(self):
		return "<"+self.name+"/"+self.hexhash+">"


	def link_established_callback(self, callback):
		self.callbacks.link_established = callback

	def packet_callback(self, callback):
		self.callbacks.packet = callback

	def proof_requested_callback(self, callback):
		self.callbacks.proof_requested = callback

	def set_proof_strategy(self, proof_strategy):
		if not proof_strategy in Destination.proof_strategies:
			raise TypeError("Unsupported proof strategy")
		else:
			self.proof_strategy = proof_strategy

	def receive(self, packet):
		plaintext = self.decrypt(packet.data)
		if plaintext != None:
			if packet.packet_type == RNS.Packet.LINKREQUEST:
				self.incomingLinkRequest(plaintext, packet)

			if packet.packet_type == RNS.Packet.DATA:
				if self.callbacks.packet != None:
					self.callbacks.packet(plaintext, packet)

	def incomingLinkRequest(self, data, packet):
		link = RNS.Link.validateRequest(self, data, packet)
		if link != None:
			self.links.append(link)

	def createKeys(self):
		if self.type == Destination.PLAIN:
			raise TypeError("A plain destination does not hold any keys")

		if self.type == Destination.SINGLE:
			raise TypeError("A single destination holds keys through an Identity instance")

		if self.type == Destination.GROUP:
			self.prv_bytes = Fernet.generate_key()
			self.prv = Fernet(self.prv_bytes)


	def getPrivateKey(self):
		if self.type == Destination.PLAIN:
			raise TypeError("A plain destination does not hold any keys")
		elif self.type == Destination.SINGLE:
			raise TypeError("A single destination holds keys through an Identity instance")
		else:
			return self.prv_bytes


	def loadPrivateKey(self, key):
		if self.type == Destination.PLAIN:
			raise TypeError("A plain destination does not hold any keys")

		if self.type == Destination.SINGLE:
			raise TypeError("A single destination holds keys through an Identity instance")

		if self.type == Destination.GROUP:
			self.prv_bytes = key
			self.prv = Fernet(self.prv_bytes)

	def loadPublicKey(self, key):
		if self.type != Destination.SINGLE:
			raise TypeError("Only the \"single\" destination type can hold a public key")
		else:
			raise TypeError("A single destination holds keys through an Identity instance")


	def encrypt(self, plaintext):
		if self.type == Destination.PLAIN:
			return plaintext

		if self.type == Destination.SINGLE and self.identity != None:
			return self.identity.encrypt(plaintext)

		if self.type == Destination.GROUP:
			if hasattr(self, "prv") and self.prv != None:
				try:
					return base64.urlsafe_b64decode(self.prv.encrypt(plaintext))
				except Exception as e:
					RNS.log("The GROUP destination could not encrypt data", RNS.LOG_ERROR)
					RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)
			else:
				raise ValueError("No private key held by GROUP destination. Did you create or load one?")



	def decrypt(self, ciphertext):
		if self.type == Destination.PLAIN:
			return ciphertext

		if self.type == Destination.SINGLE and self.identity != None:
			return self.identity.decrypt(ciphertext)

		if self.type == Destination.GROUP:
			if hasattr(self, "prv") and self.prv != None:
				try:
					return self.prv.decrypt(base64.urlsafe_b64encode(ciphertext))
				except Exception as e:
					RNS.log("The GROUP destination could not decrypt data", RNS.LOG_ERROR)
					RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)
			else:
				raise ValueError("No private key held by GROUP destination. Did you create or load one?")


	def sign(self, message):
		if self.type == Destination.SINGLE and self.identity != None:
			return self.identity.sign(message)
		else:
			return None


	# Creates an announce packet for this destination.
	# Application specific data can be added to the announce.
	def announce(self, app_data=None, path_response=False):
		destination_hash = self.hash
		random_hash = RNS.Identity.getRandomHash()
		
		signed_data = self.hash+self.identity.getPublicKey()+random_hash
		if app_data != None:
			signed_data += app_data

		signature = self.identity.sign(signed_data)

		# TODO: Check if this could be optimised by only
		# carrying the hash in the destination field, not
		# also redundantly inside the signed blob as here
		announce_data = self.hash+self.identity.getPublicKey()+random_hash+signature

		if app_data != None:
			announce_data += app_data

		if path_response:
			announce_context = RNS.Packet.PATH_RESPONSE
		else:
			announce_context = RNS.Packet.NONE

		RNS.Packet(self, announce_data, RNS.Packet.ANNOUNCE, context = announce_context).send()

