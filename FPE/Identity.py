import base64
import math
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric import padding

class Identity:
	# Configure key size
	KEYSIZE    = 1536;

	# Padding size, not configurable
	PADDINGSIZE= 336;

	def __init__(self):
		# Initialize keys to none
		self.prv = None
		self.pub = None
		self.prv_bytes = None
		self.pub_bytes = None
		self.hash = None
		self.hexhash = None

		self.createKeys()

	@staticmethod
	def getHash(pub_key):
		digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
		digest.update(pub_key)

		return digest.finalize()[:10]

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

		self.hash = Identity.getHash(self.pub_bytes)
		self.hexhash = self.hash.encode("hex_codec")

		print("Identity keys created, private length is "+str(len(self.prv_bytes)))
		print("Identity keys created, public length is "+str(len(self.pub_bytes)))

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
			print("Plaintext size is "+str(len(plaintext))+", with "+str(chunks)+" chunks")

			ciphertext = "";
			for chunk in range(chunks):
				start = chunk*chunksize
				end = (chunk+1)*chunksize
				if (chunk+1)*chunksize > len(plaintext):
					end = len(plaintext)

				print("Processing chunk "+str(chunk+1)+" of "+str(chunks)+". Starting at "+str(start)+" and stopping at "+str(end)+". The length is "+str(len(plaintext[start:end])))
				
				ciphertext += self.pub.encrypt(
					plaintext[start:end],
					padding.OAEP(
						mgf=padding.MGF1(algorithm=hashes.SHA1()),
						algorithm=hashes.SHA1(),
						label=None
					)
				)
			print("Plaintext encrypted, ciphertext length is "+str(len(ciphertext))+" bytes.")
			return ciphertext
		else:
			raise KeyError("Encryption failed because identity does not hold a private key")


	def decrypt(self, ciphertext):
		if self.prv != None:
			print("Ciphertext length is "+str(len(ciphertext))+". ")
			chunksize = (Identity.KEYSIZE)/8
			chunks = int(math.ceil(len(ciphertext)/(float(chunksize))))

			plaintext = "";
			for chunk in range(chunks):
				start = chunk*chunksize
				end = (chunk+1)*chunksize
				if (chunk+1)*chunksize > len(ciphertext):
					end = len(ciphertext)

				print("Processing chunk "+str(chunk+1)+" of "+str(chunks)+". Starting at "+str(start)+" and stopping at "+str(end)+". The length is "+str(len(ciphertext[start:end])))

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

