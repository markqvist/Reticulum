from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.fernet import Fernet
from time import sleep
from .vendor import umsgpack as umsgpack
import threading
import base64
import math
import time
import RNS

import traceback

class LinkCallbacks:
    def __init__(self):
        self.link_established = None
        self.link_closed = None
        self.packet = None
        self.resource = None
        self.resource_started = None
        self.resource_concluded = None

class Link:
    """
    This class.

    :param destination: A :ref:`RNS.Destination<api-destination>` instance which to establish a link to.
    :param owner: Internal use by :ref:`RNS.Transport<api-Transport>`, ignore this argument.
    :param peer_pub_bytes: Internal use, ignore this argument.
    :param peer_sig_pub_bytes: Internal use, ignore this argument.
    """
    CURVE = "Curve25519"
    """
    The curve used for Elliptic Curve DH key exchanges
    """

    ECPUBSIZE = 32+32
    BLOCKSIZE = 16
    KEYSIZE   = 32

    AES_HMAC_OVERHEAD = 58
    MDU = math.floor((RNS.Reticulum.MDU-AES_HMAC_OVERHEAD)/BLOCKSIZE)*BLOCKSIZE - 1

    # TODO: This should not be hardcoded,
    # but calculated from something like 
    # first-hop RTT latency and distance 
    DEFAULT_TIMEOUT = 15.0
    """
    Default timeout for link establishment in seconds.
    """
    TIMEOUT_FACTOR = 3
    STALE_GRACE = 2
    KEEPALIVE = 180
    """
    Interval for sending keep-alive packets on established links in seconds.
    """

    PENDING   = 0x00
    HANDSHAKE = 0x01
    ACTIVE    = 0x02
    STALE     = 0x03
    CLOSED    = 0x04

    TIMEOUT            = 0x01
    INITIATOR_CLOSED   = 0x02
    DESTINATION_CLOSED = 0x03

    ACCEPT_NONE = 0x00
    ACCEPT_APP  = 0x01
    ACCEPT_ALL  = 0x02
    resource_strategies = [ACCEPT_NONE, ACCEPT_APP, ACCEPT_ALL]

    @staticmethod
    def validate_request(owner, data, packet):
        if len(data) == (Link.ECPUBSIZE):
            try:
                link = Link(owner = owner, peer_pub_bytes=data[:Link.ECPUBSIZE//2], peer_sig_pub_bytes=data[Link.ECPUBSIZE//2:Link.ECPUBSIZE])
                link.set_link_id(packet)
                link.destination = packet.destination
                RNS.log("Validating link request "+RNS.prettyhexrep(link.link_id), RNS.LOG_VERBOSE)
                link.handshake()
                link.attached_interface = packet.receiving_interface
                link.prove()
                link.request_time = time.time()
                RNS.Transport.register_link(link)
                link.last_inbound = time.time()
                link.start_watchdog()

                # TODO: Why was link_established callback here? Seems weird
                # to call this before RTT packet has been received
                #if self.owner.callbacks.link_established != None:
                #   self.owner.callbacks.link_established(link)
                
                RNS.log("Incoming link request "+str(link)+" accepted", RNS.LOG_VERBOSE)
                return link

            except Exception as e:
                RNS.log("Validating link request failed", RNS.LOG_VERBOSE)
                traceback.print_exc()
                return None

        else:
            RNS.log("Invalid link request payload size, dropping request", RNS.LOG_VERBOSE)
            return None


    def __init__(self, destination=None, owner=None, peer_pub_bytes = None, peer_sig_pub_bytes = None):
        if destination != None and destination.type != RNS.Destination.SINGLE:
            raise TypeError("Links can only be established to the \"single\" destination type")
        self.rtt = None
        self.callbacks = LinkCallbacks()
        self.resource_strategy = Link.ACCEPT_NONE
        self.outgoing_resources = []
        self.incoming_resources = []
        self.last_inbound = 0
        self.last_outbound = 0
        self.tx = 0
        self.rx = 0
        self.txbytes = 0
        self.rxbytes = 0
        self.default_timeout = Link.DEFAULT_TIMEOUT
        self.proof_timeout = self.default_timeout
        self.timeout_factor = Link.TIMEOUT_FACTOR
        self.keepalive = Link.KEEPALIVE
        self.watchdog_lock = False
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

        self.fernet  = None
        
        self.prv     = X25519PrivateKey.generate()
        self.sig_prv = Ed25519PrivateKey.generate()
        
        self.pub = self.prv.public_key()
        self.pub_bytes = self.pub.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )

        self.sig_pub = self.sig_prv.public_key()
        self.sig_pub_bytes = self.sig_pub.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )

        if peer_pub_bytes == None:
            self.peer_pub = None
            self.peer_pub_bytes = None
        else:
            self.load_peer(peer_pub_bytes, peer_sig_pub_bytes)

        if (self.initiator):
            self.request_data = self.pub_bytes+self.sig_pub_bytes
            self.packet = RNS.Packet(destination, self.request_data, packet_type=RNS.Packet.LINKREQUEST)
            self.packet.pack()
            self.set_link_id(self.packet)
            RNS.Transport.register_link(self)
            self.request_time = time.time()
            self.start_watchdog()
            self.packet.send()
            self.had_outbound()
            RNS.log("Link request "+RNS.prettyhexrep(self.link_id)+" sent to "+str(self.destination), RNS.LOG_VERBOSE)


    def load_peer(self, peer_pub_bytes, peer_sig_pub_bytes):
        self.peer_pub_bytes = peer_pub_bytes
        self.peer_pub = X25519PublicKey.from_public_bytes(self.peer_pub_bytes)

        self.peer_sig_pub_bytes = peer_sig_pub_bytes
        self.peer_sig_pub = Ed25519PublicKey.from_public_bytes(self.peer_sig_pub_bytes)

        if not hasattr(self.peer_pub, "curve"):
            self.peer_pub.curve = Link.CURVE

    def set_link_id(self, packet):
        self.link_id = packet.getTruncatedHash()
        self.hash = self.link_id

    def handshake(self):
        self.status = Link.HANDSHAKE
        self.shared_key = self.prv.exchange(self.peer_pub)
        self.derived_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.get_salt(),
            info=self.get_context(),
        ).derive(self.shared_key)

    def prove(self):
        signed_data = self.link_id+self.pub_bytes+self.sig_pub_bytes
        signature = self.owner.identity.sign(signed_data)

        proof_data = self.pub_bytes+self.sig_pub_bytes+signature
        proof = RNS.Packet(self, proof_data, packet_type=RNS.Packet.PROOF, context=RNS.Packet.LRPROOF)
        proof.send()
        self.had_outbound()

    def prove_packet(self, packet):
        signature = self.sign(packet.packet_hash)
        # TODO: Hardcoded as explicit proof for now
        # if RNS.Reticulum.should_use_implicit_proof():
        #   proof_data = signature
        # else:
        #   proof_data = packet.packet_hash + signature
        proof_data = packet.packet_hash + signature

        proof = RNS.Packet(self, proof_data, RNS.Packet.PROOF)
        proof.send()
        self.had_outbound()

    def validate_proof(self, packet):
        if self.initiator and len(packet.data) == Link.ECPUBSIZE+RNS.Identity.KEYSIZE//8:
            peer_pub_bytes = packet.data[:Link.ECPUBSIZE//2]
            peer_sig_pub_bytes = packet.data[Link.ECPUBSIZE//2:Link.ECPUBSIZE]
            signed_data = self.link_id+peer_pub_bytes+peer_sig_pub_bytes
            signature = packet.data[Link.ECPUBSIZE:RNS.Identity.KEYSIZE//8+Link.ECPUBSIZE]

            if self.destination.identity.validate(signature, signed_data):
                self.load_peer(peer_pub_bytes, peer_sig_pub_bytes)
                self.handshake()
                self.rtt = time.time() - self.request_time
                self.attached_interface = packet.receiving_interface
                RNS.Transport.activate_link(self)
                RNS.log("Link "+str(self)+" established with "+str(self.destination)+", RTT is "+str(self.rtt), RNS.LOG_VERBOSE)
                rtt_data = umsgpack.packb(self.rtt)
                rtt_packet = RNS.Packet(self, rtt_data, context=RNS.Packet.LRRTT)
                RNS.log("Sending RTT packet", RNS.LOG_EXTREME);
                rtt_packet.send()
                self.had_outbound()

                self.status = Link.ACTIVE
                if self.callbacks.link_established != None:
                    thread = threading.Thread(target=self.callbacks.link_established, args=(self,))
                    thread.setDaemon(True)
                    thread.start()
            else:
                RNS.log("Invalid link proof signature received by "+str(self)+". Ignoring.", RNS.LOG_DEBUG)


    def rtt_packet(self, packet):
        try:
            # TODO: This is crude, we should use the delta
            # to model a more representative per-bit round
            # trip time, and use that to set a sensible RTT
            # expectancy for the link. This will have to do
            # for now though.
            measured_rtt = time.time() - self.request_time
            plaintext = self.decrypt(packet.data)
            rtt = umsgpack.unpackb(plaintext)
            self.rtt = max(measured_rtt, rtt)
            self.status = Link.ACTIVE
            
            if self.owner.callbacks.link_established != None:
                    self.owner.callbacks.link_established(self)
        except Exception as e:
            RNS.log("Error occurred while processing RTT packet, tearing down link", RNS.LOG_ERROR)
            traceback.print_exc()
            self.teardown()

    def get_salt(self):
        return self.link_id

    def get_context(self):
        return None

    def no_inbound_for(self):
        """
        :returns: The time in seconds since last inbound packet on the link.
        """
        return time.time() - self.last_inbound

    def no_outbound_for(self):
        """
        :returns: The time in seconds since last outbound packet on the link.
        """
        return time.time() - self.last_outbound

    def inactive_for(self):
        """
        :returns: The time in seconds since activity on the link.
        """
        return min(self.no_inbound_for(), self.no_outbound_for())

    def had_outbound(self):
        self.last_outbound = time.time()

    def teardown(self):
        """
        Closes the link and purges encryption keys. New keys will
        be used if a new link to the same destination is established.
        """
        if self.status != Link.PENDING and self.status != Link.CLOSED:
            teardown_packet = RNS.Packet(self, self.link_id, context=RNS.Packet.LINKCLOSE)
            teardown_packet.send()
            self.had_outbound()
        self.status = Link.CLOSED
        if self.initiator:
            self.teardown_reason = Link.INITIATOR_CLOSED
        else:
            self.teardown_reason = Link.DESTINATION_CLOSED
        self.link_closed()

    def teardown_packet(self, packet):
        try:
            plaintext = self.decrypt(packet.data)
            if plaintext == self.link_id:
                self.status = Link.CLOSED
                if self.initiator:
                    self.teardown_reason = Link.DESTINATION_CLOSED
                else:
                    self.teardown_reason = Link.INITIATOR_CLOSED
                self.link_closed()
        except Exception as e:
            pass

    def link_closed(self):
        for resource in self.incoming_resources:
            resource.cancel()
        for resource in self.outgoing_resources:
            resource.cancel()
            
        self.prv = None
        self.pub = None
        self.pub_bytes = None
        self.shared_key = None
        self.derived_key = None

        if self.callbacks.link_closed != None:
            self.callbacks.link_closed(self)

    def start_watchdog(self):
        thread = threading.Thread(target=self.__watchdog_job)
        thread.setDaemon(True)
        thread.start()

    def __watchdog_job(self):
        while not self.status == Link.CLOSED:
            while (self.watchdog_lock):
                sleep(max(self.rtt, 0.025))

            if not self.status == Link.CLOSED:
                # Link was initiated, but no response
                # from destination yet
                if self.status == Link.PENDING:
                    next_check = self.request_time + self.proof_timeout
                    sleep_time = next_check - time.time()
                    if time.time() >= self.request_time + self.proof_timeout:
                        RNS.log("Link establishment timed out", RNS.LOG_VERBOSE)
                        self.status = Link.CLOSED
                        self.teardown_reason = Link.TIMEOUT
                        self.link_closed()
                        sleep_time = 0.001

                elif self.status == Link.HANDSHAKE:
                    next_check = self.request_time + self.proof_timeout
                    sleep_time = next_check - time.time()
                    if time.time() >= self.request_time + self.proof_timeout:
                        RNS.log("Timeout waiting for RTT packet from link initiator", RNS.LOG_DEBUG)
                        self.status = Link.CLOSED
                        self.teardown_reason = Link.TIMEOUT
                        self.link_closed()
                        sleep_time = 0.001

                elif self.status == Link.ACTIVE:
                    if time.time() >= self.last_inbound + self.keepalive:
                        sleep_time = self.rtt * self.timeout_factor + Link.STALE_GRACE
                        self.status = Link.STALE
                        if self.initiator:
                            self.send_keepalive()
                    else:
                        sleep_time = (self.last_inbound + self.keepalive) - time.time()

                elif self.status == Link.STALE:
                    sleep_time = 0.001
                    self.status = Link.CLOSED
                    self.teardown_reason = Link.TIMEOUT
                    self.link_closed()


                if sleep_time == 0:
                    RNS.log("Warning! Link watchdog sleep time of 0!", RNS.LOG_ERROR)
                if sleep_time == None or sleep_time < 0:
                    RNS.log("Timing error! Tearing down link "+str(self)+" now.", RNS.LOG_ERROR)
                    self.teardown()
                    sleep_time = 0.1

                sleep(sleep_time)


    def send_keepalive(self):
        keepalive_packet = RNS.Packet(self, bytes([0xFF]), context=RNS.Packet.KEEPALIVE)
        keepalive_packet.send()
        self.had_outbound()

    def receive(self, packet):
        self.watchdog_lock = True
        if not self.status == Link.CLOSED and not (self.initiator and packet.context == RNS.Packet.KEEPALIVE and packet.data == bytes([0xFF])):
            if packet.receiving_interface != self.attached_interface:
                RNS.log("Link-associated packet received on unexpected interface! Someone might be trying to manipulate your communication!", RNS.LOG_ERROR)
            else:
                self.last_inbound = time.time()
                self.rx += 1
                self.rxbytes += len(packet.data)
                if self.status == Link.STALE:
                    self.status = Link.ACTIVE

                if packet.packet_type == RNS.Packet.DATA:
                    if packet.context == RNS.Packet.NONE:
                        plaintext = self.decrypt(packet.data)
                        if self.callbacks.packet != None:
                            thread = threading.Thread(target=self.callbacks.packet, args=(plaintext, packet))
                            thread.setDaemon(True)
                            thread.start()
                        
                        if self.destination.proof_strategy == RNS.Destination.PROVE_ALL:
                            packet.prove()

                        elif self.destination.proof_strategy == RNS.Destination.PROVE_APP:
                            if self.destination.callbacks.proof_requested:
                                self.destination.callbacks.proof_requested(packet)

                    elif packet.context == RNS.Packet.LRRTT:
                        if not self.initiator:
                            self.rtt_packet(packet)

                    elif packet.context == RNS.Packet.LINKCLOSE:
                        self.teardown_packet(packet)

                    elif packet.context == RNS.Packet.RESOURCE_ADV:
                        packet.plaintext = self.decrypt(packet.data)
                        if self.resource_strategy == Link.ACCEPT_NONE:
                            pass
                        elif self.resource_strategy == Link.ACCEPT_APP:
                            if self.callbacks.resource != None:
                                if self.callbacks.resource(resource):
                                    RNS.Resource.accept(packet, self.callbacks.resource_concluded)
                        elif self.resource_strategy == Link.ACCEPT_ALL:
                            RNS.Resource.accept(packet, self.callbacks.resource_concluded)

                    elif packet.context == RNS.Packet.RESOURCE_REQ:
                        plaintext = self.decrypt(packet.data)
                        if ord(plaintext[:1]) == RNS.Resource.HASHMAP_IS_EXHAUSTED:
                            resource_hash = plaintext[1+RNS.Resource.MAPHASH_LEN:RNS.Identity.HASHLENGTH//8+1+RNS.Resource.MAPHASH_LEN]
                        else:
                            resource_hash = plaintext[1:RNS.Identity.HASHLENGTH//8+1]
                        for resource in self.outgoing_resources:
                            if resource.hash == resource_hash:
                                resource.request(plaintext)

                    elif packet.context == RNS.Packet.RESOURCE_HMU:
                        plaintext = self.decrypt(packet.data)
                        resource_hash = plaintext[:RNS.Identity.HASHLENGTH//8]
                        for resource in self.incoming_resources:
                            if resource_hash == resource.hash:
                                resource.hashmap_update_packet(plaintext)

                    elif packet.context == RNS.Packet.RESOURCE_ICL:
                        plaintext = self.decrypt(packet.data)
                        resource_hash = plaintext[:RNS.Identity.HASHLENGTH//8]
                        for resource in self.incoming_resources:
                            if resource_hash == resource.hash:
                                resource.cancel()

                    elif packet.context == RNS.Packet.KEEPALIVE:
                        if not self.initiator and packet.data == bytes([0xFF]):
                            keepalive_packet = RNS.Packet(self, bytes([0xFE]), context=RNS.Packet.KEEPALIVE)
                            keepalive_packet.send()
                            self.had_outbound()


                    # TODO: find the most efficient way to allow multiple
                    # transfers at the same time, sending resource hash on
                    # each packet is a huge overhead. Probably some kind
                    # of hash -> sequence map
                    elif packet.context == RNS.Packet.RESOURCE:
                        for resource in self.incoming_resources:
                            resource.receive_part(packet)

                elif packet.packet_type == RNS.Packet.PROOF:
                    if packet.context == RNS.Packet.RESOURCE_PRF:
                        resource_hash = packet.data[0:RNS.Identity.HASHLENGTH//8]
                        for resource in self.outgoing_resources:
                            if resource_hash == resource.hash:
                                resource.validate_proof(packet.data)

        self.watchdog_lock = False


    def encrypt(self, plaintext):
        if self.__encryption_disabled:
            return plaintext
        try:
            if not self.fernet:
                self.fernet = Fernet(base64.urlsafe_b64encode(self.derived_key))

            ciphertext = base64.urlsafe_b64decode(self.fernet.encrypt(plaintext))
            return ciphertext
        except Exception as e:
            RNS.log("Encryption on link "+str(self)+" failed. The contained exception was: "+str(e), RNS.LOG_ERROR)


    def decrypt(self, ciphertext):
        if self.__encryption_disabled:
            return ciphertext
        try:
            if not self.fernet:
                self.fernet = Fernet(base64.urlsafe_b64encode(self.derived_key))
                
            plaintext = self.fernet.decrypt(base64.urlsafe_b64encode(ciphertext))
            return plaintext
        except Exception as e:
            RNS.log("Decryption failed on link "+str(self)+". The contained exception was: "+str(e), RNS.LOG_ERROR)
            RNS.log(traceback.format_exc(), RNS.LOG_ERROR)
            # TODO: Do we really need to do this? Or can we recover somehow?
            self.teardown()


    def sign(self, message):
        return self.sig_prv.sign(message)

    def validate(self, signature, message):
        try:
            self.peer_sig_pub.verify(signature, message)
            return True
        except Exception as e:
            return False

    def link_established_callback(self, callback):
        self.callbacks.link_established = callback

    def link_closed_callback(self, callback):
        self.callbacks.link_closed = callback

    def packet_callback(self, callback):
        """
        Registers a function to be called when a packet has been
        received over this link.

        :param callback: A function or method with the signature *callback(message, packet)* to be called.
        """
        self.callbacks.packet = callback

    def resource_callback(self, callback):
        """
        Registers a function to be called when a resource has been
        advertised over this link. If the function returns *True*
        the resource will be accepted. If it returns *False* it will
        be ignored.

        :param callback: A function or method with the signature *callback(resource)* to be called.
        """
        self.callbacks.resource = callback

    def resource_started_callback(self, callback):
        """
        Registers a function to be called when a resource has begun
        transferring over this link.

        :param callback: A function or method with the signature *callback(resource)* to be called.
        """
        self.callbacks.resource_started = callback

    def resource_concluded_callback(self, callback):
        """
        Registers a function to be called when a resource has concluded
        transferring over this link.

        :param callback: A function or method with the signature *callback(resource)* to be called.
        """
        self.callbacks.resource_concluded = callback

    def resource_concluded(self, resource):
        if resource in self.incoming_resources:
            self.incoming_resources.remove(resource)
        if resource in self.outgoing_resources:
            self.outgoing_resources.remove(resource)

    def set_resource_strategy(self, resource_strategy):
        """
        Sets the resource strategy for the link.

        :param resource_strategy: One of ``RNS.Link.ACCEPT_NONE``, ``RNS.Link.ACCEPT_ALL`` or ``RNS.Link.ACCEPT_APP``. If ``RNS.Link.ACCEPT_APP`` is set, the `resource_callback` will be called to determine whether the resource should be accepted or not.
        :raises: *TypeError* if the resource strategy is unsupported.
        """
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
            RNS.log("Attempt to cancel a non-existing outgoing resource", RNS.LOG_ERROR)

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

    def disable_encryption(self):
        """
        HAZARDOUS. This will downgrade the link to encryptionless. All
        information over the link will be sent in plaintext. Never use
        this in production applications. Should only be used for debugging
        purposes, and will disappear in a future version.

        If encryptionless links are not explicitly allowed in the users
        configuration file, Reticulum will terminate itself along with the
        client application and throw an error message to the user.
        """
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