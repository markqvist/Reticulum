# MIT License
#
# Copyright (c) 2016-2022 Mark Qvist / unsigned.io
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from RNS.Cryptography import X25519PrivateKey, X25519PublicKey, Ed25519PrivateKey, Ed25519PublicKey
from RNS.Cryptography import Fernet

from time import sleep
from .vendor import umsgpack as umsgpack
import threading
import math
import time
import RNS


class LinkCallbacks:
    def __init__(self):
        self.link_established = None
        self.link_closed = None
        self.packet = None
        self.resource = None
        self.resource_started = None
        self.resource_concluded = None
        self.remote_identified = None

class Link:
    """
    This class is used to establish and manage links to other peers. When a
    link instance is created, Reticulum will attempt to establish verified
    and encrypted connectivity with the specified destination.

    :param destination: A :ref:`RNS.Destination<api-destination>` instance which to establish a link to.
    :param established_callback: An optional function or method with the signature *callback(link)* to be called when the link has been established.
    :param closed_callback: An optional function or method with the signature *callback(link)* to be called when the link is closed.
    """
    CURVE = RNS.Identity.CURVE
    """
    The curve used for Elliptic Curve DH key exchanges
    """

    ECPUBSIZE         = 32+32
    KEYSIZE           = 32

    MDU = math.floor((RNS.Reticulum.MTU-RNS.Reticulum.IFAC_MIN_SIZE-RNS.Reticulum.HEADER_MINSIZE-RNS.Identity.FERNET_OVERHEAD)/RNS.Identity.AES128_BLOCKSIZE)*RNS.Identity.AES128_BLOCKSIZE - 1

    ESTABLISHMENT_TIMEOUT_PER_HOP = RNS.Reticulum.DEFAULT_PER_HOP_TIMEOUT
    """
    Timeout for link establishment in seconds per hop to destination.
    """

    TRAFFIC_TIMEOUT_FACTOR = 6
    KEEPALIVE_TIMEOUT_FACTOR = 4
    """
    RTT timeout factor used in link timeout calculation.
    """
    STALE_GRACE = 2
    """
    Grace period in seconds used in link timeout calculation.
    """
    KEEPALIVE = 360
    """
    Interval for sending keep-alive packets on established links in seconds.
    """
    STALE_TIME = 2*KEEPALIVE
    """
    If no traffic or keep-alive packets are received within this period, the
    link will be marked as stale, and a final keep-alive packet will be sent.
    If after this no traffic or keep-alive packets are received within ``RTT`` *
    ``KEEPALIVE_TIMEOUT_FACTOR`` + ``STALE_GRACE``, the link is considered timed out,
    and will be torn down.
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
                link.establishment_timeout = Link.ESTABLISHMENT_TIMEOUT_PER_HOP * max(1, packet.hops)
                link.establishment_cost += len(packet.raw)
                RNS.log("Validating link request "+RNS.prettyhexrep(link.link_id), RNS.LOG_VERBOSE)
                link.handshake()
                link.attached_interface = packet.receiving_interface
                link.prove()
                link.request_time = time.time()
                RNS.Transport.register_link(link)
                link.last_inbound = time.time()
                link.start_watchdog()
                
                RNS.log("Incoming link request "+str(link)+" accepted", RNS.LOG_VERBOSE)
                return link

            except Exception as e:
                RNS.log("Validating link request failed", RNS.LOG_VERBOSE)
                RNS.log("exc: "+str(e))
                return None

        else:
            RNS.log("Invalid link request payload size, dropping request", RNS.LOG_VERBOSE)
            return None


    def __init__(self, destination=None, established_callback = None, closed_callback = None, owner=None, peer_pub_bytes = None, peer_sig_pub_bytes = None):
        if destination != None and destination.type != RNS.Destination.SINGLE:
            raise TypeError("Links can only be established to the \"single\" destination type")
        self.rtt = None
        self.establishment_cost = 0
        self.callbacks = LinkCallbacks()
        self.resource_strategy = Link.ACCEPT_NONE
        self.outgoing_resources = []
        self.incoming_resources = []
        self.pending_requests   = []
        self.last_inbound = 0
        self.last_outbound = 0
        self.tx = 0
        self.rx = 0
        self.txbytes = 0
        self.rxbytes = 0
        self.traffic_timeout_factor = Link.TRAFFIC_TIMEOUT_FACTOR
        self.keepalive_timeout_factor = Link.KEEPALIVE_TIMEOUT_FACTOR
        self.keepalive = Link.KEEPALIVE
        self.stale_time = Link.STALE_TIME
        self.watchdog_lock = False
        self.status = Link.PENDING
        self.activated_at = None
        self.type = RNS.Destination.LINK
        self.owner = owner
        self.destination = destination
        self.attached_interface = None
        self.__remote_identity = None
        if self.destination == None:
            self.initiator = False
            self.prv     = X25519PrivateKey.generate()
            self.sig_prv = self.owner.identity.sig_prv
        else:
            self.initiator = True
            self.establishment_timeout = Link.ESTABLISHMENT_TIMEOUT_PER_HOP * max(1, RNS.Transport.hops_to(destination.hash))
            self.prv     = X25519PrivateKey.generate()
            self.sig_prv = Ed25519PrivateKey.generate()

        self.fernet  = None
        
        self.pub = self.prv.public_key()
        self.pub_bytes = self.pub.public_bytes()

        self.sig_pub = self.sig_prv.public_key()
        self.sig_pub_bytes = self.sig_pub.public_bytes()

        if peer_pub_bytes == None:
            self.peer_pub = None
            self.peer_pub_bytes = None
        else:
            self.load_peer(peer_pub_bytes, peer_sig_pub_bytes)

        if established_callback != None:
            self.set_link_established_callback(established_callback)

        if closed_callback != None:
            self.set_link_closed_callback(closed_callback)

        if (self.initiator):
            self.request_data = self.pub_bytes+self.sig_pub_bytes
            self.packet = RNS.Packet(destination, self.request_data, packet_type=RNS.Packet.LINKREQUEST)
            self.packet.pack()
            self.establishment_cost += len(self.packet.raw)
            self.set_link_id(self.packet)
            RNS.Transport.register_link(self)
            self.request_time = time.time()
            self.start_watchdog()
            self.packet.send()
            self.had_outbound()
            RNS.log("Link request "+RNS.prettyhexrep(self.link_id)+" sent to "+str(self.destination), RNS.LOG_DEBUG)


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

        self.derived_key = RNS.Cryptography.hkdf(
            length=32,
            derive_from=self.shared_key,
            salt=self.get_salt(),
            context=self.get_context(),
        )


    def prove(self):
        signed_data = self.link_id+self.pub_bytes+self.sig_pub_bytes
        signature = self.owner.identity.sign(signed_data)

        proof_data = signature+self.pub_bytes
        proof = RNS.Packet(self, proof_data, packet_type=RNS.Packet.PROOF, context=RNS.Packet.LRPROOF)
        proof.send()
        self.establishment_cost += len(proof.raw)
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
        if self.status == Link.PENDING:
            if self.initiator and len(packet.data) == RNS.Identity.SIGLENGTH//8+Link.ECPUBSIZE//2:
                peer_pub_bytes = packet.data[RNS.Identity.SIGLENGTH//8:RNS.Identity.SIGLENGTH//8+Link.ECPUBSIZE//2]
                peer_sig_pub_bytes = self.destination.identity.get_public_key()[Link.ECPUBSIZE//2:Link.ECPUBSIZE]
                self.load_peer(peer_pub_bytes, peer_sig_pub_bytes)
                self.handshake()

                self.establishment_cost += len(packet.raw)
                signed_data = self.link_id+self.peer_pub_bytes+self.peer_sig_pub_bytes
                signature = packet.data[:RNS.Identity.SIGLENGTH//8]
                
                if self.destination.identity.validate(signature, signed_data):
                    self.rtt = time.time() - self.request_time
                    self.attached_interface = packet.receiving_interface
                    self.__remote_identity = self.destination.identity
                    self.status = Link.ACTIVE
                    self.activated_at = time.time()
                    RNS.Transport.activate_link(self)
                    RNS.log("Link "+str(self)+" established with "+str(self.destination)+", RTT is "+str(round(self.rtt, 3))+"s", RNS.LOG_VERBOSE)
                    rtt_data = umsgpack.packb(self.rtt)
                    rtt_packet = RNS.Packet(self, rtt_data, context=RNS.Packet.LRRTT)
                    rtt_packet.send()
                    self.had_outbound()

                    if self.callbacks.link_established != None:
                        thread = threading.Thread(target=self.callbacks.link_established, args=(self,))
                        thread.daemon = True
                        thread.start()
                else:
                    RNS.log("Invalid link proof signature received by "+str(self)+". Ignoring.", RNS.LOG_DEBUG)


    def identify(self, identity):
        """
        Identifies the initiator of the link to the remote peer. This can only happen
        once the link has been established, and is carried out over the encrypted link.
        The identity is only revealed to the remote peer, and initiator anonymity is
        thus preserved. This method can be used for authentication.

        :param identity: An RNS.Identity instance to identify as.
        """
        if self.initiator:
            signed_data = self.link_id + identity.get_public_key()
            signature = identity.sign(signed_data)
            proof_data = identity.get_public_key() + signature

            proof = RNS.Packet(self, proof_data, RNS.Packet.DATA, context = RNS.Packet.LINKIDENTIFY)
            proof.send()
            self.had_outbound()


    def request(self, path, data = None, response_callback = None, failed_callback = None, progress_callback = None, timeout = None):
        """
        Sends a request to the remote peer.

        :param path: The request path.
        :param response_callback: An optional function or method with the signature *response_callback(request_receipt)* to be called when a response is received. See the :ref:`Request Example<example-request>` for more info.
        :param failed_callback: An optional function or method with the signature *failed_callback(request_receipt)* to be called when a request fails. See the :ref:`Request Example<example-request>` for more info.
        :param progress_callback: An optional function or method with the signature *progress_callback(request_receipt)* to be called when progress is made receiving the response. Progress can be accessed as a float between 0.0 and 1.0 by the *request_receipt.progress* property.
        :param timeout: An optional timeout in seconds for the request. If *None* is supplied it will be calculated based on link RTT.
        :returns: A :ref:`RNS.RequestReceipt<api-requestreceipt>` instance if the request was sent, or *False* if it was not.
        """
        request_path_hash = RNS.Identity.truncated_hash(path.encode("utf-8"))
        unpacked_request  = [time.time(), request_path_hash, data]
        packed_request    = umsgpack.packb(unpacked_request)

        if timeout == None:
            timeout = self.rtt * self.traffic_timeout_factor + RNS.Resource.RESPONSE_MAX_GRACE_TIME/4.0

        if len(packed_request) <= Link.MDU:
            request_packet   = RNS.Packet(self, packed_request, RNS.Packet.DATA, context = RNS.Packet.REQUEST)
            packet_receipt   = request_packet.send()

            if packet_receipt == False:
                return False
            else:
                packet_receipt.set_timeout(timeout)
                return RequestReceipt(
                    self,
                    packet_receipt = packet_receipt,
                    response_callback = response_callback,
                    failed_callback = failed_callback,
                    progress_callback = progress_callback,
                    timeout = timeout,
                    request_size = len(packed_request),
                )
            
        else:
            request_id = RNS.Identity.truncated_hash(packed_request)
            RNS.log("Sending request "+RNS.prettyhexrep(request_id)+" as resource.", RNS.LOG_DEBUG)
            request_resource = RNS.Resource(packed_request, self, request_id = request_id, is_response = False, timeout = timeout)

            return RequestReceipt(
                self,
                resource = request_resource,
                response_callback = response_callback,
                failed_callback = failed_callback,
                progress_callback = progress_callback,
                timeout = timeout,
                request_size = len(packed_request),
            )


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
            self.activated_at = time.time()

            
            if self.owner.callbacks.link_established != None:
                    self.owner.callbacks.link_established(self)
        except Exception as e:
            RNS.log("Error occurred while processing RTT packet, tearing down link. The contained exception was: "+str(e), RNS.LOG_ERROR)
            self.teardown()

    def get_salt(self):
        return self.link_id

    def get_context(self):
        return None

    def no_inbound_for(self):
        """
        :returns: The time in seconds since last inbound packet on the link.
        """
        activated_at = self.activated_at if self.activated_at != None else 0
        last_inbound = max(self.last_inbound, activated_at)
        return time.time() - last_inbound

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

    def get_remote_identity(self):
        """
        :returns: The identity of the remote peer, if it is known. Calling this method will not query the remote initiator to reveal its identity. Returns ``None`` if the link initiator has not already independently called the ``identify(identity)`` method.
        """
        return self.__remote_identity

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

        if self.destination != None:
            if self.destination.direction == RNS.Destination.IN:
                if self in self.destination.links:
                    self.destination.links.remove(self)

        if self.callbacks.link_closed != None:
            try:
                self.callbacks.link_closed(self)
            except Exception as e:
                RNS.log("Error while executing link closed callback from "+str(self)+". The contained exception was: "+str(e), RNS.LOG_ERROR)


    def start_watchdog(self):
        thread = threading.Thread(target=self.__watchdog_job)
        thread.daemon = True
        thread.start()

    def __watchdog_job(self):
        while not self.status == Link.CLOSED:
            while (self.watchdog_lock):
                sleep(max(self.rtt, 0.025))

            if not self.status == Link.CLOSED:
                # Link was initiated, but no response
                # from destination yet
                if self.status == Link.PENDING:
                    next_check = self.request_time + self.establishment_timeout
                    sleep_time = next_check - time.time()
                    if time.time() >= self.request_time + self.establishment_timeout:
                        RNS.log("Link establishment timed out", RNS.LOG_VERBOSE)
                        self.status = Link.CLOSED
                        self.teardown_reason = Link.TIMEOUT
                        self.link_closed()
                        sleep_time = 0.001

                elif self.status == Link.HANDSHAKE:
                    next_check = self.request_time + self.establishment_timeout
                    sleep_time = next_check - time.time()
                    if time.time() >= self.request_time + self.establishment_timeout:
                        if self.initiator:
                            RNS.log("Timeout waiting for link request proof", RNS.LOG_DEBUG)
                        else:
                            RNS.log("Timeout waiting for RTT packet from link initiator", RNS.LOG_DEBUG)

                        self.status = Link.CLOSED
                        self.teardown_reason = Link.TIMEOUT
                        self.link_closed()
                        sleep_time = 0.001

                elif self.status == Link.ACTIVE:
                    activated_at = self.activated_at if self.activated_at != None else 0
                    last_inbound = max(self.last_inbound, activated_at)

                    if time.time() >= last_inbound + self.keepalive:
                        if self.initiator:
                            self.send_keepalive()

                        if time.time() >= last_inbound + self.stale_time:
                            sleep_time = self.rtt * self.keepalive_timeout_factor + Link.STALE_GRACE
                            self.status = Link.STALE
                        else:
                            sleep_time = self.keepalive
                    
                    else:
                        sleep_time = (last_inbound + self.keepalive) - time.time()

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

    def handle_request(self, request_id, unpacked_request):
        if self.status == Link.ACTIVE:
            requested_at = unpacked_request[0]
            path_hash    = unpacked_request[1]
            request_data = unpacked_request[2]

            if path_hash in self.destination.request_handlers:
                request_handler = self.destination.request_handlers[path_hash]
                path               = request_handler[0]
                response_generator = request_handler[1]
                allow              = request_handler[2]
                allowed_list       = request_handler[3]

                allowed = False
                if not allow == RNS.Destination.ALLOW_NONE:
                    if allow == RNS.Destination.ALLOW_LIST:
                        if self.__remote_identity != None and self.__remote_identity.hash in allowed_list:
                            allowed = True
                    elif allow == RNS.Destination.ALLOW_ALL:
                        allowed = True

                if allowed:
                    RNS.log("Handling request "+RNS.prettyhexrep(request_id)+" for: "+str(path), RNS.LOG_DEBUG)
                    response = response_generator(path, request_data, request_id, self.__remote_identity, requested_at)
                    if response != None:
                        packed_response = umsgpack.packb([request_id, response])

                        if len(packed_response) <= Link.MDU:
                            RNS.Packet(self, packed_response, RNS.Packet.DATA, context = RNS.Packet.RESPONSE).send()
                        else:
                            response_resource = RNS.Resource(packed_response, self, request_id = request_id, is_response = True)
                else:
                    identity_string = str(self.get_remote_identity()) if self.get_remote_identity() != None else "<Unknown>"
                    RNS.log("Request "+RNS.prettyhexrep(request_id)+" from "+identity_string+" not allowed for: "+str(path), RNS.LOG_DEBUG)

    def handle_response(self, request_id, response_data, response_size, response_transfer_size):
        if self.status == Link.ACTIVE:
            remove = None
            for pending_request in self.pending_requests:
                if pending_request.request_id == request_id:
                    remove = pending_request
                    try:
                        pending_request.response_size = response_size
                        pending_request.response_transfer_size = response_transfer_size
                        pending_request.response_received(response_data)
                    except Exception as e:
                        RNS.log("Error occurred while handling response. The contained exception was: "+str(e), RNS.LOG_ERROR)

                    break

            if remove != None:
                if remove in self.pending_requests:
                    self.pending_requests.remove(remove)

    def request_resource_concluded(self, resource):
        if resource.status == RNS.Resource.COMPLETE:
            packed_request    = resource.data.read()
            unpacked_request  = umsgpack.unpackb(packed_request)
            request_id        = RNS.Identity.truncated_hash(packed_request)
            request_data      = unpacked_request

            self.handle_request(request_id, request_data)
        else:
            RNS.log("Incoming request resource failed with status: "+RNS.hexrep([resource.status]), RNS.LOG_DEBUG)

    def response_resource_concluded(self, resource):
        if resource.status == RNS.Resource.COMPLETE:
            packed_response   = resource.data.read()
            unpacked_response = umsgpack.unpackb(packed_response)
            request_id        = unpacked_response[0]
            response_data     = unpacked_response[1]

            self.handle_response(request_id, response_data, resource.total_size, resource.size)
        else:
            RNS.log("Incoming response resource failed with status: "+RNS.hexrep([resource.status]), RNS.LOG_DEBUG)
            for pending_request in self.pending_requests:
                if pending_request.request_id == resource.request_id:
                    pending_request.request_timed_out(None)

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
                            thread.daemon = True
                            thread.start()
                        
                        if self.destination.proof_strategy == RNS.Destination.PROVE_ALL:
                            packet.prove()

                        elif self.destination.proof_strategy == RNS.Destination.PROVE_APP:
                            if self.destination.callbacks.proof_requested:
                                try:
                                    self.destination.callbacks.proof_requested(packet)
                                except Exception as e:
                                    RNS.log("Error while executing proof request callback from "+str(self)+". The contained exception was: "+str(e), RNS.LOG_ERROR)

                    elif packet.context == RNS.Packet.LINKIDENTIFY:
                        plaintext = self.decrypt(packet.data)

                        if not self.initiator and len(plaintext) == RNS.Identity.KEYSIZE//8 + RNS.Identity.SIGLENGTH//8:
                            public_key   = plaintext[:RNS.Identity.KEYSIZE//8]
                            signed_data  = self.link_id+public_key
                            signature    = plaintext[RNS.Identity.KEYSIZE//8:RNS.Identity.KEYSIZE//8+RNS.Identity.SIGLENGTH//8]
                            identity     = RNS.Identity(create_keys=False)
                            identity.load_public_key(public_key)

                            if identity.validate(signature, signed_data):
                                self.__remote_identity = identity
                                if self.callbacks.remote_identified != None:
                                    try:
                                        self.callbacks.remote_identified(self, self.__remote_identity)
                                    except Exception as e:
                                        RNS.log("Error while executing remote identified callback from "+str(self)+". The contained exception was: "+str(e), RNS.LOG_ERROR)

                    elif packet.context == RNS.Packet.REQUEST:
                        try:
                            request_id = packet.getTruncatedHash()
                            packed_request = self.decrypt(packet.data)
                            unpacked_request = umsgpack.unpackb(packed_request)
                            self.handle_request(request_id, unpacked_request)
                        except Exception as e:
                            RNS.log("Error occurred while handling request. The contained exception was: "+str(e), RNS.LOG_ERROR)

                    elif packet.context == RNS.Packet.RESPONSE:
                        try:
                            packed_response = self.decrypt(packet.data)
                            unpacked_response = umsgpack.unpackb(packed_response)
                            request_id = unpacked_response[0]
                            response_data = unpacked_response[1]
                            transfer_size = len(umsgpack.packb(response_data))-2
                            self.handle_response(request_id, response_data, transfer_size, transfer_size)
                        except Exception as e:
                            RNS.log("Error occurred while handling response. The contained exception was: "+str(e), RNS.LOG_ERROR)

                    elif packet.context == RNS.Packet.LRRTT:
                        if not self.initiator:
                            self.rtt_packet(packet)

                    elif packet.context == RNS.Packet.LINKCLOSE:
                        self.teardown_packet(packet)

                    elif packet.context == RNS.Packet.RESOURCE_ADV:
                        packet.plaintext = self.decrypt(packet.data)

                        if RNS.ResourceAdvertisement.is_request(packet):
                            RNS.Resource.accept(packet, callback=self.request_resource_concluded)
                        elif RNS.ResourceAdvertisement.is_response(packet):
                            request_id = RNS.ResourceAdvertisement.read_request_id(packet)
                            for pending_request in self.pending_requests:
                                if pending_request.request_id == request_id:
                                    RNS.Resource.accept(packet, callback=self.response_resource_concluded, progress_callback=pending_request.response_resource_progress, request_id = request_id)
                                    pending_request.response_size = RNS.ResourceAdvertisement.read_size(packet)
                                    pending_request.response_transfer_size = RNS.ResourceAdvertisement.read_transfer_size(packet)
                                    pending_request.started_at = time.time()
                        elif self.resource_strategy == Link.ACCEPT_NONE:
                            pass
                        elif self.resource_strategy == Link.ACCEPT_APP:
                            if self.callbacks.resource != None:
                                try:
                                    resource_advertisement = RNS.ResourceAdvertisement.unpack(packet.plaintext)
                                    resource_advertisement.link = self
                                    if self.callbacks.resource(resource_advertisement):
                                        RNS.Resource.accept(packet, self.callbacks.resource_concluded)
                                except Exception as e:
                                    RNS.log("Error while executing resource accept callback from "+str(self)+". The contained exception was: "+str(e), RNS.LOG_ERROR)
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
                                # We need to check that this request has not been
                                # received before in order to avoid sequencing errors.
                                if not packet.packet_hash in resource.req_hashlist:
                                    resource.req_hashlist.append(packet.packet_hash)
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
        try:
            if not self.fernet:
                try:
                    self.fernet = Fernet(self.derived_key)
                except Exception as e:
                    RNS.log("Could not "+str(self)+" instantiate Fernet while performin encryption on link. The contained exception was: "+str(e), RNS.LOG_ERROR)
                    raise e

            return self.fernet.encrypt(plaintext)

        except Exception as e:
            RNS.log("Encryption on link "+str(self)+" failed. The contained exception was: "+str(e), RNS.LOG_ERROR)
            raise e


    def decrypt(self, ciphertext):
        try:
            if not self.fernet:
                self.fernet = Fernet(self.derived_key)
                
            return self.fernet.decrypt(ciphertext)

        except Exception as e:
            RNS.log("Decryption failed on link "+str(self)+". The contained exception was: "+str(e), RNS.LOG_ERROR)


    def sign(self, message):
        return self.sig_prv.sign(message)

    def validate(self, signature, message):
        try:
            self.peer_sig_pub.verify(signature, message)
            return True
        except Exception as e:
            return False

    def set_link_established_callback(self, callback):
        self.callbacks.link_established = callback

    def set_link_closed_callback(self, callback):
        """
        Registers a function to be called when a link has been
        torn down.

        :param callback: A function or method with the signature *callback(link)* to be called.
        """
        self.callbacks.link_closed = callback

    def set_packet_callback(self, callback):
        """
        Registers a function to be called when a packet has been
        received over this link.

        :param callback: A function or method with the signature *callback(message, packet)* to be called.
        """
        self.callbacks.packet = callback

    def set_resource_callback(self, callback):
        """
        Registers a function to be called when a resource has been
        advertised over this link. If the function returns *True*
        the resource will be accepted. If it returns *False* it will
        be ignored.

        :param callback: A function or method with the signature *callback(resource)* to be called. Please note that only the basic information of the resource is available at this time, such as *get_transfer_size()*, *get_data_size()*, *get_parts()* and *is_compressed()*.
        """
        self.callbacks.resource = callback

    def set_resource_started_callback(self, callback):
        """
        Registers a function to be called when a resource has begun
        transferring over this link.

        :param callback: A function or method with the signature *callback(resource)* to be called.
        """
        self.callbacks.resource_started = callback

    def set_resource_concluded_callback(self, callback):
        """
        Registers a function to be called when a resource has concluded
        transferring over this link.

        :param callback: A function or method with the signature *callback(resource)* to be called.
        """
        self.callbacks.resource_concluded = callback

    def set_remote_identified_callback(self, callback):
        """
        Registers a function to be called when an initiating peer has
        identified over this link.

        :param callback: A function or method with the signature *callback(link, identity)* to be called.
        """
        self.callbacks.remote_identified = callback

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

    def has_incoming_resource(self, resource):
        for incoming_resource in self.incoming_resources:
            if incoming_resource.hash == resource.hash:
                return True

        return False

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

    def __str__(self):
        return RNS.prettyhexrep(self.link_id)


class RequestReceipt():
    """
    An instance of this class is returned by the ``request`` method of ``RNS.Link``
    instances. It should never be instantiated manually. It provides methods to
    check status, response time and response data when the request concludes.
    """

    FAILED    = 0x00
    SENT      = 0x01
    DELIVERED = 0x02
    RECEIVING = 0x03
    READY     = 0x04

    def __init__(self, link, packet_receipt = None, resource = None, response_callback = None, failed_callback = None, progress_callback = None, timeout = None, request_size = None):
        self.packet_receipt = packet_receipt
        self.resource = resource
        self.started_at = None

        if self.packet_receipt != None:
            self.hash = packet_receipt.truncated_hash
            self.packet_receipt.set_timeout_callback(self.request_timed_out)
            self.started_at = time.time()

        elif self.resource != None:
            self.hash = resource.request_id
            resource.set_callback(self.request_resource_concluded)
        
        self.link                   = link
        self.request_id             = self.hash
        self.request_size           = request_size

        self.response               = None
        self.response_transfer_size = None
        self.response_size          = None
        self.status                 = RequestReceipt.SENT
        self.sent_at                = time.time()
        self.progress               = 0
        self.concluded_at           = None
        self.response_concluded_at  = None

        if timeout != None:
            self.timeout        = timeout
        else:
            raise ValueError("No timeout specified for request receipt")

        self.callbacks          = RequestReceiptCallbacks()
        self.callbacks.response = response_callback
        self.callbacks.failed   = failed_callback
        self.callbacks.progress = progress_callback

        self.link.pending_requests.append(self)


    def request_resource_concluded(self, resource):
        if resource.status == RNS.Resource.COMPLETE:
            RNS.log("Request "+RNS.prettyhexrep(self.request_id)+" successfully sent as resource.", RNS.LOG_DEBUG)
            self.started_at = time.time()
            self.status = RequestReceipt.DELIVERED
            self.__resource_response_timeout = time.time()+self.timeout
            response_timeout_thread = threading.Thread(target=self.__response_timeout_job)
            response_timeout_thread.daemon = True
            response_timeout_thread.start()
        else:
            RNS.log("Sending request "+RNS.prettyhexrep(self.request_id)+" as resource failed with status: "+RNS.hexrep([resource.status]), RNS.LOG_DEBUG)
            self.status = RequestReceipt.FAILED
            self.concluded_at = time.time()
            self.link.pending_requests.remove(self)

            if self.callbacks.failed != None:
                try:
                    self.callbacks.failed(self)
                except Exception as e:
                    RNS.log("Error while executing request failed callback from "+str(self)+". The contained exception was: "+str(e), RNS.LOG_ERROR)


    def __response_timeout_job(self):
        while self.status == RequestReceipt.DELIVERED:
            now = time.time()
            if now > self.__resource_response_timeout:
                self.request_timed_out(None)

            time.sleep(0.1)


    def request_timed_out(self, packet_receipt):
        self.status = RequestReceipt.FAILED
        self.concluded_at = time.time()
        self.link.pending_requests.remove(self)

        if self.callbacks.failed != None:
            try:
                self.callbacks.failed(self)
            except Exception as e:
                RNS.log("Error while executing request timed out callback from "+str(self)+". The contained exception was: "+str(e), RNS.LOG_ERROR)


    def response_resource_progress(self, resource):
        if not self.status == RequestReceipt.FAILED:
            self.status = RequestReceipt.RECEIVING
            if self.packet_receipt != None:
                self.packet_receipt.status = RNS.PacketReceipt.DELIVERED
                self.packet_receipt.proved = True
                self.packet_receipt.concluded_at = time.time()
                if self.packet_receipt.callbacks.delivery != None:
                    self.packet_receipt.callbacks.delivery(self.packet_receipt)

            self.progress = resource.get_progress()
            
            if self.callbacks.progress != None:
                try:
                    self.callbacks.progress(self)
                except Exception as e:
                    RNS.log("Error while executing response progress callback from "+str(self)+". The contained exception was: "+str(e), RNS.LOG_ERROR)
        else:
            resource.cancel()

    
    def response_received(self, response):
        if not self.status == RequestReceipt.FAILED:
            self.progress = 1.0
            self.response = response
            self.status = RequestReceipt.READY
            self.response_concluded_at = time.time()

            if self.packet_receipt != None:
                self.packet_receipt.status = RNS.PacketReceipt.DELIVERED
                self.packet_receipt.proved = True
                self.packet_receipt.concluded_at = time.time()
                if self.packet_receipt.callbacks.delivery != None:
                    self.packet_receipt.callbacks.delivery(self.packet_receipt)

            if self.callbacks.progress != None:
                try:
                    self.callbacks.progress(self)
                except Exception as e:
                    RNS.log("Error while executing response progress callback from "+str(self)+". The contained exception was: "+str(e), RNS.LOG_ERROR)

            if self.callbacks.response != None:
                try:
                    self.callbacks.response(self)
                except Exception as e:
                    RNS.log("Error while executing response received callback from "+str(self)+". The contained exception was: "+str(e), RNS.LOG_ERROR)

    def get_request_id(self):
        """
        :returns: The request ID as *bytes*.
        """
        return self.request_id

    def get_status(self):
        """
        :returns: The current status of the request, one of ``RNS.RequestReceipt.FAILED``, ``RNS.RequestReceipt.SENT``, ``RNS.RequestReceipt.DELIVERED``, ``RNS.RequestReceipt.READY``.
        """
        return self.status

    def get_progress(self):
        """
        :returns: The progress of a response being received as a *float* between 0.0 and 1.0.
        """
        return self.progress

    def get_response(self):
        """
        :returns: The response as *bytes* if it is ready, otherwise *None*.
        """
        if self.status == RequestReceipt.READY:
            return self.response
        else:
            return None

    def get_response_time(self):
        """
        :returns: The response time of the request in seconds.
        """
        if self.status == RequestReceipt.READY:
            return self.response_concluded_at - self.started_at
        else:
            return None



class RequestReceiptCallbacks:
    def __init__(self):
        self.response = None
        self.failed   = None
        self.progress = None
