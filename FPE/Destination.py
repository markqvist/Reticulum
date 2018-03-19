import base64
import math
import FPE

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric import padding


class Destination:
	KEYSIZE    = FPE.Identity.KEYSIZE;
	PADDINGSIZE= FPE.Identity.PADDINGSIZE;

	# Constants
	SINGLE     = 0x00;
	GROUP      = 0x01;
	PLAIN      = 0x02;
	LINK       = 0x03;
	types      = [SINGLE, GROUP, PLAIN, LINK]

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
		digest.update(name)

		return digest.finalize()[:10]


	def __init__(self, identity, direction, type, app_name, *aspects):
		# Check input values and build name string
		if "." in app_name: raise ValueError("Dots can't be used in app names") 
		if not type in Destination.types: raise ValueError("Unknown destination type")
		if not direction in Destination.directions: raise ValueError("Unknown destination direction")
		self.type = type
		self.direction = direction
		self.mtu = 0

		if identity == None:
			identity = Identity()
			identity.createKeys()

		self.identity = identity
		aspects = aspects+(identity.hexhash,)

		self.name = Destination.getDestinationName(app_name, *aspects)		
		self.hash = Destination.getDestinationHash(app_name, *aspects)
		self.hexhash = self.hash.encode("hex_codec")

		self.callback = None

		FPE.Transport.registerDestination(self)


	def __str__(self):
		return "<"+self.name+"/"+self.hexhash+">"


	def setCallback(self, callback):
		self.callback = callback


	def receive(self, data):
		plaintext = self.decrypt(data)
		if plaintext != None and self.callback != None:
			self.callback(plaintext, self)


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

		if self.type == Destination.GROUP and self.prv != None:
			try:
				return base64.urlsafe_b64decode(self.prv.encrypt(plaintext))
			except:
				return None


	def decrypt(self, ciphertext):
		if self.type == Destination.PLAIN:
			return ciphertext

		if self.type == Destination.SINGLE and self.identity != None:
			return self.identity.decrypt(ciphertext)

		if self.type == Destination.GROUP:
			return self.prv.decrypt(base64.urlsafe_b64encode(ciphertext))


	def sign(self, message):
		if self.type == Destination.SINGLE and self.identity != None:
			return self.identity.sign(message)
		else:
			return None


	# Creates an announce packet for this destination.
	# Application specific data can be added to the announce.
	def announce(self,app_data=None):
		destination_hash = self.hash
		random_hash = self.identity.getRandomHash()
		
		signed_data = self.hash+self.identity.getPublicKey()+random_hash
		if app_data != None:
			signed_data += app_data

		signature = self.identity.sign(signed_data)

		announce_data = self.hash+self.identity.getPublicKey()+random_hash+signature
		if app_data != None:
			announce_data += app_data

		FPE.Packet(self, announce_data, FPE.Packet.ANNOUNCE).send()

