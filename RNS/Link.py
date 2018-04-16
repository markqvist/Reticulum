from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.fernet import Fernet
import base64
import RNS

import traceback

class LinkCallbacks:
	def __init__(self):
		self.link_established = None
		self.packet = None
		self.resource_started = None
		self.resource_completed = None

class Link:
	CURVE = ec.SECP256R1()
	ECPUBSIZE = 91

	PENDING = 0x00
	ACTIVE = 0x01

	@staticmethod
	def validateRequest(owner, data, packet):
		if len(data) == (Link.ECPUBSIZE):
			try:
				link = Link(owner = owner, peer_pub_bytes = data[:Link.ECPUBSIZE])
				link.setLinkID(packet)
				RNS.log("Validating link request "+RNS.prettyhexrep(link.link_id), RNS.LOG_VERBOSE)
				link.handshake()
				link.attached_interface = packet.receiving_interface
				link.prove()
				RNS.Transport.registerLink(link)
				if link.owner.callbacks.link_established != None:
					link.owner.callbacks.link_established(link)
				RNS.log("Incoming link request "+str(link)+" accepted", RNS.LOG_VERBOSE)

			except Exception as e:
				RNS.log("Validating link request failed", RNS.LOG_VERBOSE)
				return None
			

		else:
			RNS.log("Invalid link request payload size, dropping request", RNS.LOG_VERBOSE)
			return None


	def __init__(self, destination=None, owner=None, peer_pub_bytes = None):
		self.callbacks = LinkCallbacks()
		self.status = Link.PENDING
		self.type = RNS.Destination.LINK
		self.owner = owner
		self.destination = destination
		self.attached_interface = None
		if self.destination == None:
			self.initiator = False
		else:
			self.initiator = True
		
		self.prv = ec.generate_private_key(Link.CURVE, default_backend())
		self.pub = self.prv.public_key()
		self.pub_bytes = self.pub.public_bytes(
			encoding=serialization.Encoding.DER,
			format=serialization.PublicFormat.SubjectPublicKeyInfo
		)

		if peer_pub_bytes == None:
			self.peer_pub = None
			self.peer_pub_bytes = None
		else:
			self.loadPeer(peer_pub_bytes)

		if (self.initiator):
			self.request_data = self.pub_bytes
			self.packet = RNS.Packet(destination, self.request_data, packet_type=RNS.Packet.LINKREQUEST)
			self.packet.pack()
			self.setLinkID(self.packet)
			RNS.Transport.registerLink(self)
			self.packet.send()
			RNS.log("Link request "+RNS.prettyhexrep(self.link_id)+" sent to "+str(self.destination), RNS.LOG_VERBOSE)


	def loadPeer(self, peer_pub_bytes):
		self.peer_pub_bytes = peer_pub_bytes
		self.peer_pub = serialization.load_der_public_key(peer_pub_bytes, backend=default_backend())
		self.peer_pub.curce = Link.CURVE

	def setLinkID(self, packet):
		self.link_id = RNS.Identity.truncatedHash(packet.raw)
		self.hash = self.link_id

	def handshake(self):
		self.shared_key = self.prv.exchange(ec.ECDH(), self.peer_pub)
		self.derived_key = HKDF(
			algorithm=hashes.SHA256(),
			length=32,
			salt=self.getSalt(),
			info=self.getContext(),
			backend=default_backend()
		).derive(self.shared_key)

	def prove(self):
		signed_data = self.link_id+self.pub_bytes
		signature = self.owner.identity.sign(signed_data)

		proof_data = self.pub_bytes+signature
		proof = RNS.Packet(self, proof_data, packet_type=RNS.Packet.PROOF, header_type=RNS.Packet.HEADER_3)
		proof.send()

	def validateProof(self, packet):
		peer_pub_bytes = packet.data[:Link.ECPUBSIZE]
		signed_data = self.link_id+peer_pub_bytes
		signature = packet.data[Link.ECPUBSIZE:RNS.Identity.KEYSIZE/8+Link.ECPUBSIZE]

		if self.destination.identity.validate(signature, signed_data):
			self.loadPeer(peer_pub_bytes)
			self.handshake()
			self.attached_interface = packet.receiving_interface
			RNS.Transport.activateLink(self)
			if self.callbacks.link_established != None:
				self.callbacks.link_established(self)
			RNS.log("Link "+str(self)+" established with "+str(self.destination), RNS.LOG_VERBOSE)
		else:
			RNS.log("Invalid link proof signature received by "+str(self), RNS.LOG_VERBOSE)


	def getSalt(self):
		return self.link_id

	def getContext(self):
		return None

	def receive(self, packet):
		if packet.receiving_interface != self.attached_interface:
			RNS.log("Link-associated packet received on unexpected interface! Someone might be trying to manipulate your communication!", RNS.LOG_ERROR)
		else:
			plaintext = self.decrypt(packet.data)
			if (self.callbacks.packet != None):
				self.callbacks.packet(plaintext, packet)

	def encrypt(self, plaintext):
		try:
			fernet = Fernet(base64.urlsafe_b64encode(self.derived_key))
			ciphertext = base64.urlsafe_b64decode(fernet.encrypt(plaintext))
			return ciphertext
		except Exception as e:
			RNS.log("Encryption on link "+str(self)+" failed. The contained exception was: "+str(e), RNS.LOG_ERROR)


	def decrypt(self, ciphertext):
		try:
			fernet = Fernet(base64.urlsafe_b64encode(self.derived_key))
			plaintext = fernet.decrypt(base64.urlsafe_b64encode(ciphertext))
			return plaintext
		except Exception as e:
			RNS.log("Decryption failed on link "+str(self)+". The contained exception was: "+str(e), RNS.LOG_ERROR)

	def link_established_callback(self, callback):
		self.callbacks.link_established = callback

	def packet_callback(self, callback):
		self.callbacks.packet = callback

	def resource_started_callback(self, callback):
		self.callbacks.resource_started = callback

	def resource_completed_callback(self, callback):
		self.callbacks.resource_completed = callback

	def __str__(self):
		return RNS.prettyhexrep(self.link_id)