import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric import padding

class Destination:
	SINGLE     = 0x01;
	GROUP      = 0x02;
	PLAIN      = 0x03;
	types      = [SINGLE, GROUP, PLAIN]

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


	def __init__(self, direction, type, app_name, *aspects):

		# Check input values and build name string
		if "." in app_name: raise ValueError("Dots can't be used in app names") 
		if not type in Destination.types: raise ValueError("Unknown destination type")
		if not direction in Destination.directions: raise ValueError("Unknown destination direction")
		self.type = type
		self.direction = direction

		self.name = Destination.getDestinationName(app_name, *aspects)		
		self.hash = Destination.getDestinationHash(app_name, *aspects)
		self.hexhash = self.hash.encode("hex_codec")

		self.callback = None

		# Initialize keys to none
		self.prv = None
		self.pub = None
		self.prv_bytes = None
		self.pub_bytes = None


	def __str__(self):
		return "<"+self.name+"/"+self.hexhash+">"


	def setCallback(self, callback):
		self.callback = callback


	def receive(self, data):
		plaintext = self.decrypt(data)
		if plaintext != None and self.callback != None:
			self.callback(plaintext, self)


	def createKey(self):
		if self.type == Destination.PLAIN:
			raise TypeError("A plain destination does not hold any keys")

		if self.type == Destination.SINGLE:
			self.prv = rsa.generate_private_key(
				public_exponent=65337,
				key_size=2048,
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

		if self.type == Destination.GROUP:
			self.prv_bytes = Fernet.generate_key()
			self.prv = Fernet(self.prv_bytes)


	def getKey(self):
		if self.type == Destination.PLAIN:
			raise TypeError("A plain destination does not hold any keys")
		else:
			return self.prv_bytes


	def loadKey(self, key):
		if self.type == Destination.PLAIN:
			raise TypeError("A plain destination does not hold any keys")

		if self.type == Destination.SINGLE:
			self.prv_bytes = key
			self.prv = serialization.load_der_private_key(self.prv_bytes, password=None,backend=default_backend())
			self.pub = self.prv.public_key()
			self.pub_bytes = self.pub.public_bytes(
				encoding=serialization.Encoding.DER,
				format=serialization.PublicFormat.SubjectPublicKeyInfo
			)

		if self.type == Destination.GROUP:
			self.prv_bytes = key
			self.prv = Fernet(self.prv_bytes)

	def loadPublicKey(self, key):
		if self.type != Destination.SINGLE:
			raise TypeError("Only the \"single\" destination type can hold a public key")

		self.pub_bytes = key
		self.pub = load_der_public_key(self.pub_bytes, backend=default_backend())


	def encrypt(self, plaintext):
		if self.type == Destination.PLAIN:
			return plaintext

		if self.type == Destination.SINGLE and self.prv != None:
			ciphertext = self.pub.encrypt(
				plaintext,
				padding.OAEP(
					mgf=padding.MGF1(algorithm=hashes.SHA1()),
					algorithm=hashes.SHA1(),
					label=None
				)
			)
			return ciphertext

		if self.type == Destination.GROUP and self.prv != None:
			try:
				return base64.urlsafe_b64decode(self.prv.encrypt(plaintext))
			except:
				return None


	def decrypt(self, ciphertext):
		if self.type == Destination.PLAIN:
			return plaintext

		if self.type == Destination.SINGLE and self.prv != None:
			plaintext = self.prv.decrypt(
				ciphertext,
				padding.OAEP(
					mgf=padding.MGF1(algorithm=hashes.SHA1()),
					algorithm=hashes.SHA1(),
					label=None
				)
			)
			return plaintext;

		if self.type == Destination.GROUP:
			return self.prv.decrypt(base64.urlsafe_b64encode(ciphertext))


	def sign(self, message):
		if self.type == Destination.SINGLE and self.prv != None:
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
			return None