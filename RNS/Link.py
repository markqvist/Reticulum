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
		self.resource_concluded = None

class Link:
	CURVE = ec.SECP256R1()
	ECPUBSIZE = 91
	BLOCKSIZE = 16

	PENDING = 0x00
	ACTIVE = 0x01

	ACCEPT_NONE = 0x00
	ACCEPT_APP = 0x01
	ACCEPT_ALL = 0x02
	resource_strategies = [ACCEPT_NONE, ACCEPT_APP, ACCEPT_ALL]

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
				traceback.print_exc()
				return None

		else:
			RNS.log("Invalid link request payload size, dropping request", RNS.LOG_VERBOSE)
			return None


	def __init__(self, destination=None, owner=None, peer_pub_bytes = None):
		if destination != None and destination.type != RNS.Destination.SINGLE:
			raise TypeError("Links can only be established to the \"single\" destination type")
		self.rtt = None
		self.callbacks = LinkCallbacks()
		self.resource_strategy = Link.ACCEPT_NONE
		self.outgoing_resources = []
		self.incoming_resources = []
		self.status = Link.PENDING
		self.type = RNS.Destination.LINK
		self.owner = owner
		self.destination = destination
		self.attached_interface = None
		self.__encryption_disabled = False
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
		proof = RNS.Packet(self, proof_data, packet_type=RNS.Packet.PROOF, context=RNS.Packet.LRPROOF)
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
			RNS.log("Link "+str(self)+" established with "+str(self.destination), RNS.LOG_VERBOSE)
			if self.callbacks.link_established != None:
				self.callbacks.link_established(self)
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
			if packet.packet_type == RNS.Packet.DATA:
				if packet.context == RNS.Packet.NONE:
					plaintext = self.decrypt(packet.data)
					if (self.callbacks.packet != None):
						self.callbacks.packet(plaintext, packet)

				elif packet.context == RNS.Packet.RESOURCE_ADV:
					packet.plaintext = self.decrypt(packet.data)
					if self.resource_strategy == Link.ACCEPT_NONE:
						pass
					elif self.resource_strategy == Link.ACCEPT_APP:
						if self.callbacks.resource != None:
							self.callbacks.resource(packet)
					elif self.resource_strategy == Link.ACCEPT_ALL:
						RNS.Resource.accept(packet, self.callbacks.resource_concluded)

				elif packet.context == RNS.Packet.RESOURCE_REQ:
					plaintext = self.decrypt(packet.data)
					if ord(plaintext[:1]) == RNS.Resource.HASHMAP_IS_EXHAUSTED:
						resource_hash = plaintext[1+RNS.Resource.MAPHASH_LEN:RNS.Identity.HASHLENGTH/8+1+RNS.Resource.MAPHASH_LEN]
					else:
						resource_hash = plaintext[1:RNS.Identity.HASHLENGTH/8+1]
					for resource in self.outgoing_resources:
						if resource.hash == resource_hash:
							resource.request(plaintext)

				elif packet.context == RNS.Packet.RESOURCE_HMU:
					plaintext = self.decrypt(packet.data)
					resource_hash = plaintext[:RNS.Identity.HASHLENGTH/8]
					for resource in self.incoming_resources:
						if resource_hash == resource.hash:
							resource.hashmap_update_packet(plaintext)

				elif packet.context == RNS.Packet.RESOURCE_ICL:
					plaintext = self.decrypt(packet.data)
					resource_hash = plaintext[:RNS.Identity.HASHLENGTH/8]
					for resource in self.incoming_resources:
						if resource_hash == resource.hash:
							resource.cancel()

				# TODO: find the most efficient way to allow multiple
				# transfers at the same time, sending resource hash on
				# each packet is a huge overhead
				elif packet.context == RNS.Packet.RESOURCE:
					for resource in self.incoming_resources:
						resource.receive_part(packet)

			elif packet.packet_type == RNS.Packet.PROOF:
				if packet.context == RNS.Packet.RESOURCE_PRF:
					resource_hash = packet.data[0:RNS.Identity.HASHLENGTH/8]
					for resource in self.outgoing_resources:
						if resource_hash == resource.hash:
							resource.validateProof(packet.data)


	def encrypt(self, plaintext):
		if self.__encryption_disabled:
			return plaintext
		try:
			fernet = Fernet(base64.urlsafe_b64encode(self.derived_key))
			ciphertext = base64.urlsafe_b64decode(fernet.encrypt(plaintext))
			return ciphertext
		except Exception as e:
			RNS.log("Encryption on link "+str(self)+" failed. The contained exception was: "+str(e), RNS.LOG_ERROR)


	def decrypt(self, ciphertext):
		if self.__encryption_disabled:
			return ciphertext
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

	# Called when an incoming resource transfer is started
	def resource_started_callback(self, callback):
		self.callbacks.resource_started = callback

	# Called when a resource transfer is concluded
	def resource_concluded_callback(self, callback):
		self.callbacks.resource_concluded = callback

	def setResourceStrategy(self, resource_strategy):
		if not resource_strategy in Link.resource_strategies:
			raise TypeError("Unsupported resource strategy")
		else:
			self.resource_strategy = resource_strategy

	def register_outgoing_resource(self, resource):
		self.outgoing_resources.append(resource)

	def register_incoming_resource(self, resource):
		self.incoming_resources.append(resource)

	def cancel_outgoing_resource(self, resource):
		if resource in self.outgoing_resources:
			self.outgoing_resources.remove(resource)
		else:
			RNS.log("Attempt to cancel a non-existing incoming resource", RNS.LOG_ERROR)

	def cancel_incoming_resource(self, resource):
		if resource in self.incoming_resources:
			self.incoming_resources.remove(resource)
		else:
			RNS.log("Attempt to cancel a non-existing incoming resource", RNS.LOG_ERROR)

	def ready_for_new_resource(self):
		if len(self.outgoing_resources) > 0:
			return False
		else:
			return True

	def disableEncryption(self):
		if (RNS.Reticulum.should_allow_unencrypted()):
			RNS.log("The link "+str(self)+" was downgraded to an encryptionless link", RNS.LOG_NOTICE)
			self.__encryption_disabled = True
		else:
			RNS.log("Attempt to disable encryption on link, but encryptionless links are not allowed by config.", RNS.LOG_CRITICAL)
			RNS.log("Shutting down Reticulum now!", RNS.LOG_CRITICAL)
			RNS.panic()

	def encryption_disabled(self):
		return self.__encryption_disabled

	def __str__(self):
		return RNS.prettyhexrep(self.link_id)