# MIT License
#
# Copyright (c) 2016-2024 Mark Qvist / unsigned.io and contributors.
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

import threading
import struct
import math
import time
import RNS

class Packet:
    """
    The Packet class is used to create packet instances that can be sent
    over a Reticulum network. Packets will automatically be encrypted if
    they are addressed to a ``RNS.Destination.SINGLE`` destination,
    ``RNS.Destination.GROUP`` destination or a :ref:`RNS.Link<api-link>`.

    For ``RNS.Destination.GROUP`` destinations, Reticulum will use the
    pre-shared key configured for the destination. All packets to group
    destinations are encrypted with the same AES-128 key.

    For ``RNS.Destination.SINGLE`` destinations, Reticulum will use a newly
    derived ephemeral AES-128 key for every packet.

    For :ref:`RNS.Link<api-link>` destinations, Reticulum will use per-link
    ephemeral keys, and offers **Forward Secrecy**.

    :param destination: A :ref:`RNS.Destination<api-destination>` instance to which the packet will be sent.
    :param data: The data payload to be included in the packet as *bytes*.
    :param create_receipt: Specifies whether a :ref:`RNS.PacketReceipt<api-packetreceipt>` should be created when instantiating the packet.
    """

    # Packet types
    DATA         = 0x00     # Data packets
    ANNOUNCE     = 0x01     # Announces
    LINKREQUEST  = 0x02     # Link requests
    PROOF        = 0x03     # Proofs
    types        = [DATA, ANNOUNCE, LINKREQUEST, PROOF]

    # Header types
    HEADER_1     = 0x00     # Normal header format
    HEADER_2     = 0x01     # Header format used for packets in transport
    header_types = [HEADER_1, HEADER_2]

    # Packet context types
    NONE           = 0x00   # Generic data packet
    RESOURCE       = 0x01   # Packet is part of a resource
    RESOURCE_ADV   = 0x02   # Packet is a resource advertisement
    RESOURCE_REQ   = 0x03   # Packet is a resource part request
    RESOURCE_HMU   = 0x04   # Packet is a resource hashmap update
    RESOURCE_PRF   = 0x05   # Packet is a resource proof
    RESOURCE_ICL   = 0x06   # Packet is a resource initiator cancel message
    RESOURCE_RCL   = 0x07   # Packet is a resource receiver cancel message
    CACHE_REQUEST  = 0x08   # Packet is a cache request
    REQUEST        = 0x09   # Packet is a request
    RESPONSE       = 0x0A   # Packet is a response to a request
    PATH_RESPONSE  = 0x0B   # Packet is a response to a path request
    COMMAND        = 0x0C   # Packet is a command
    COMMAND_STATUS = 0x0D   # Packet is a status of an executed command
    CHANNEL        = 0x0E   # Packet contains link channel data
    KEEPALIVE      = 0xFA   # Packet is a keepalive packet
    LINKIDENTIFY   = 0xFB   # Packet is a link peer identification proof
    LINKCLOSE      = 0xFC   # Packet is a link close message
    LINKPROOF      = 0xFD   # Packet is a link packet proof
    LRRTT          = 0xFE   # Packet is a link request round-trip time measurement
    LRPROOF        = 0xFF   # Packet is a link request proof

    # Context flag values
    FLAG_SET       = 0x01
    FLAG_UNSET     = 0x00

    # This is used to calculate allowable
    # payload sizes
    HEADER_MAXSIZE = RNS.Reticulum.HEADER_MAXSIZE
    MDU            = RNS.Reticulum.MDU

    # With an MTU of 500, the maximum of data we can
    # send in a single encrypted packet is given by
    # the below calculation; 383 bytes.
    ENCRYPTED_MDU  = math.floor((RNS.Reticulum.MDU-RNS.Identity.FERNET_OVERHEAD-RNS.Identity.KEYSIZE//16)/RNS.Identity.AES128_BLOCKSIZE)*RNS.Identity.AES128_BLOCKSIZE - 1
    """
    The maximum size of the payload data in a single encrypted packet 
    """
    PLAIN_MDU      = MDU
    """
    The maximum size of the payload data in a single unencrypted packet
    """

    TIMEOUT_PER_HOP = RNS.Reticulum.DEFAULT_PER_HOP_TIMEOUT

    def __init__(self, destination, data, packet_type = DATA, context = NONE, transport_type = RNS.Transport.BROADCAST,
                 header_type = HEADER_1, transport_id = None, attached_interface = None, create_receipt = True, context_flag=FLAG_UNSET):

        if destination != None:
            if transport_type == None:
                transport_type = RNS.Transport.BROADCAST

            self.header_type    = header_type
            self.packet_type    = packet_type
            self.transport_type = transport_type
            self.context        = context
            self.context_flag   = context_flag

            self.hops           = 0;
            self.destination    = destination
            self.transport_id   = transport_id
            self.data           = data
            self.flags          = self.get_packed_flags()

            self.raw            = None
            self.packed         = False
            self.sent           = False
            self.create_receipt = create_receipt
            self.receipt        = None
            self.fromPacked     = False
        else:
            self.raw            = data
            self.packed         = True
            self.fromPacked     = True
            self.create_receipt = False

        self.MTU         = RNS.Reticulum.MTU
        self.sent_at     = None
        self.packet_hash = None
        self.ratchet_id  = None

        self.attached_interface = attached_interface
        self.receiving_interface = None
        self.rssi = None
        self.snr = None
        self.q = None

    def get_packed_flags(self):
        if self.context == Packet.LRPROOF:
            packed_flags = (self.header_type << 6) | (self.context_flag << 5) | (self.transport_type << 4) | (RNS.Destination.LINK << 2) | self.packet_type
        else:
            packed_flags = (self.header_type << 6) | (self.context_flag << 5) | (self.transport_type << 4) | (self.destination.type << 2) | self.packet_type

        return packed_flags

    def pack(self):
        self.destination_hash = self.destination.hash
        self.header = b""
        self.header += struct.pack("!B", self.flags)
        self.header += struct.pack("!B", self.hops)

        if self.context == Packet.LRPROOF:
            self.header += self.destination.link_id
            self.ciphertext = self.data
        else:
            if self.header_type == Packet.HEADER_1:
                self.header += self.destination.hash

                if self.packet_type == Packet.ANNOUNCE:
                    # Announce packets are not encrypted
                    self.ciphertext = self.data
                elif self.packet_type == Packet.LINKREQUEST:
                    # Link request packets are not encrypted
                    self.ciphertext = self.data
                elif self.packet_type == Packet.PROOF and self.context == Packet.RESOURCE_PRF:
                    # Resource proofs are not encrypted
                    self.ciphertext = self.data
                elif self.packet_type == Packet.PROOF and self.destination.type == RNS.Destination.LINK:
                    # Packet proofs over links are not encrypted
                    self.ciphertext = self.data
                elif self.context == Packet.RESOURCE:
                    # A resource takes care of encryption
                    # by itself
                    self.ciphertext = self.data
                elif self.context == Packet.KEEPALIVE:
                    # Keepalive packets contain no actual
                    # data
                    self.ciphertext = self.data
                elif self.context == Packet.CACHE_REQUEST:
                    # Cache-requests are not encrypted
                    self.ciphertext = self.data
                else:
                    # In all other cases, we encrypt the packet
                    # with the destination's encryption method
                    self.ciphertext = self.destination.encrypt(self.data)
                    if hasattr(self.destination, "latest_ratchet_id"):
                        self.ratchet_id = self.destination.latest_ratchet_id

            if self.header_type == Packet.HEADER_2:
                if self.transport_id != None:
                    self.header += self.transport_id
                    self.header += self.destination.hash

                    if self.packet_type == Packet.ANNOUNCE:
                        # Announce packets are not encrypted
                        self.ciphertext = self.data
                else:
                    raise OSError("Packet with header type 2 must have a transport ID")


        self.header += bytes([self.context])
        self.raw = self.header + self.ciphertext

        if len(self.raw) > self.MTU:
            raise OSError(f"Packet size of {len(self.raw)} exceeds MTU of {self.MTU} bytes")

        self.packed = True
        self.update_hash()


    def unpack(self):
        try:
            self.flags = self.raw[0]
            self.hops  = self.raw[1]

            self.header_type      = (self.flags & 0b01000000) >> 6
            self.context_flag     = (self.flags & 0b00100000) >> 5
            self.transport_type   = (self.flags & 0b00010000) >> 4
            self.destination_type = (self.flags & 0b00001100) >> 2
            self.packet_type      = (self.flags & 0b00000011)

            DST_LEN = RNS.Reticulum.TRUNCATED_HASHLENGTH//8

            if self.header_type == Packet.HEADER_2:
                self.transport_id = self.raw[2:DST_LEN+2]
                self.destination_hash = self.raw[DST_LEN+2:2*DST_LEN+2]
                self.context = ord(self.raw[2*DST_LEN+2:2*DST_LEN+3])
                self.data = self.raw[2*DST_LEN+3:]
            else:
                self.transport_id = None
                self.destination_hash = self.raw[2:DST_LEN+2]
                self.context = ord(self.raw[DST_LEN+2:DST_LEN+3])
                self.data = self.raw[DST_LEN+3:]

            self.packed = False
            self.update_hash()
            return True

        except Exception as e:
            RNS.log(f"Received malformed packet, dropping it. The contained exception was: {e}", RNS.LOG_EXTREME)
            return False

    def send(self):
        """
        Sends the packet.
        
        :returns: A :ref:`RNS.PacketReceipt<api-packetreceipt>` instance if *create_receipt* was set to *True* when the packet was instantiated, if not returns *None*. If the packet could not be sent *False* is returned.
        """
        if not self.sent:
            if self.destination.type == RNS.Destination.LINK:
                if self.destination.status == RNS.Link.CLOSED:
                    raise OSError("Attempt to transmit over a closed link")
                else:
                    self.destination.last_outbound = time.time()
                    self.destination.tx += 1
                    self.destination.txbytes += len(self.data)

            if not self.packed:
                self.pack()

            if RNS.Transport.outbound(self):
                return self.receipt
            else:
                RNS.log("No interfaces could process the outbound packet", RNS.LOG_ERROR)
                self.sent = False
                self.receipt = None
                return False
                
        else:
            raise OSError("Packet was already sent")

    def resend(self):
        """
        Re-sends the packet.
        
        :returns: A :ref:`RNS.PacketReceipt<api-packetreceipt>` instance if *create_receipt* was set to *True* when the packet was instantiated, if not returns *None*. If the packet could not be sent *False* is returned.
        """
        if self.sent:
            # Re-pack the packet to obtain new ciphertext for
            # encrypted destinations
            self.pack()
            
            if RNS.Transport.outbound(self):
                return self.receipt
            else:
                RNS.log("No interfaces could process the outbound packet", RNS.LOG_ERROR)
                self.sent = False
                self.receipt = None
                return False
        else:
            raise OSError("Packet was not sent yet")

    def prove(self, destination=None):
        if self.fromPacked and hasattr(self, "destination") and self.destination:
            if self.destination.identity and self.destination.identity.prv:
                self.destination.identity.prove(self, destination)
        elif self.fromPacked and hasattr(self, "link") and self.link:
            self.link.prove_packet(self)
        else:
            RNS.log("Could not prove packet associated with neither a destination nor a link", RNS.LOG_ERROR)

    # Generates a special destination that allows Reticulum
    # to direct the proof back to the proved packet's sender
    def generate_proof_destination(self):
        return ProofDestination(self)

    def validate_proof_packet(self, proof_packet):
        return self.receipt.validate_proof_packet(proof_packet)

    def validate_proof(self, proof):
        return self.receipt.validate_proof(proof)

    def update_hash(self):
        self.packet_hash = self.get_hash()

    def get_hash(self):
        return RNS.Identity.full_hash(self.get_hashable_part())

    def getTruncatedHash(self):
        return RNS.Identity.truncated_hash(self.get_hashable_part())

    def get_hashable_part(self):
        hashable_part = bytes([self.raw[0] & 0b00001111])
        if self.header_type == Packet.HEADER_2:
            hashable_part += self.raw[(RNS.Identity.TRUNCATED_HASHLENGTH//8)+2:]
        else:
            hashable_part += self.raw[2:]

        return hashable_part

class ProofDestination:
    def __init__(self, packet):
        self.hash = packet.get_hash()[:RNS.Reticulum.TRUNCATED_HASHLENGTH//8];
        self.type = RNS.Destination.SINGLE

    def encrypt(self, plaintext):
        return plaintext


class PacketReceipt:
    """
    The PacketReceipt class is used to receive notifications about
    :ref:`RNS.Packet<api-packet>` instances sent over the network. Instances
    of this class are never created manually, but always returned from
    the *send()* method of a :ref:`RNS.Packet<api-packet>` instance.
    """
    # Receipt status constants
    FAILED    = 0x00
    SENT      = 0x01
    DELIVERED = 0x02
    CULLED    = 0xFF


    EXPL_LENGTH = RNS.Identity.HASHLENGTH//8+RNS.Identity.SIGLENGTH//8
    IMPL_LENGTH = RNS.Identity.SIGLENGTH//8

    # Creates a new packet receipt from a sent packet
    def __init__(self, packet):
        self.hash           = packet.get_hash()
        self.truncated_hash = packet.getTruncatedHash()
        self.sent           = True
        self.sent_at        = time.time()
        self.proved         = False
        self.status         = PacketReceipt.SENT
        self.destination    = packet.destination
        self.callbacks      = PacketReceiptCallbacks()
        self.concluded_at   = None
        self.proof_packet   = None

        if packet.destination.type == RNS.Destination.LINK:
            self.timeout    = max(packet.destination.rtt * packet.destination.traffic_timeout_factor, RNS.Link.TRAFFIC_TIMEOUT_MIN_MS/1000)
        else:
            self.timeout    = RNS.Reticulum.get_instance().get_first_hop_timeout(self.destination.hash)
            self.timeout   += Packet.TIMEOUT_PER_HOP * RNS.Transport.hops_to(self.destination.hash)

    def get_status(self):
        """
        :returns: The status of the associated :ref:`RNS.Packet<api-packet>` instance. Can be one of ``RNS.PacketReceipt.SENT``, ``RNS.PacketReceipt.DELIVERED``, ``RNS.PacketReceipt.FAILED`` or ``RNS.PacketReceipt.CULLED``. 
        """
        return self.status

    # Validate a proof packet
    def validate_proof_packet(self, proof_packet):
        if hasattr(proof_packet, "link") and proof_packet.link:
            return self.validate_link_proof(proof_packet.data, proof_packet.link, proof_packet)
        else:
            return self.validate_proof(proof_packet.data, proof_packet)

    # Validate a raw proof for a link
    def validate_link_proof(self, proof, link, proof_packet=None):
        # TODO: Hardcoded as explicit proofs for now
        if True or len(proof) == PacketReceipt.EXPL_LENGTH:
            # This is an explicit proof
            proof_hash = proof[:RNS.Identity.HASHLENGTH//8]
            signature = proof[RNS.Identity.HASHLENGTH//8:RNS.Identity.HASHLENGTH//8+RNS.Identity.SIGLENGTH//8]
            if proof_hash == self.hash:
                proof_valid = link.validate(signature, self.hash)
                if proof_valid:
                    self.status = PacketReceipt.DELIVERED
                    self.proved = True
                    self.concluded_at = time.time()
                    self.proof_packet = proof_packet
                    link.last_proof = self.concluded_at

                    if self.callbacks.delivery != None:
                        try:
                            self.callbacks.delivery(self)
                        except Exception as e:
                            RNS.log(f"An error occurred while evaluating external delivery callback for {link}", RNS.LOG_ERROR)
                            RNS.log(f"The contained exception was: {e}", RNS.LOG_ERROR)
                            RNS.trace_exception(e)
                            
                    return True
                else:
                    return False
            else:
                return False
        elif len(proof) == PacketReceipt.IMPL_LENGTH:
            pass
            # TODO: Why is this disabled?
            # signature = proof[:RNS.Identity.SIGLENGTH//8]
            # proof_valid = self.link.validate(signature, self.hash)
            # if proof_valid:
            #       self.status = PacketReceipt.DELIVERED
            #       self.proved = True
            #       self.concluded_at = time.time()
            #       if self.callbacks.delivery != None:
            #           self.callbacks.delivery(self)
            #       RNS.log("valid")
            #       return True
            # else:
            #   RNS.log("invalid")
            #   return False
        else:
            return False

    # Validate a raw proof
    def validate_proof(self, proof, proof_packet=None):
        if len(proof) == PacketReceipt.EXPL_LENGTH:
            # This is an explicit proof
            proof_hash = proof[:RNS.Identity.HASHLENGTH//8]
            signature = proof[RNS.Identity.HASHLENGTH//8:RNS.Identity.HASHLENGTH//8+RNS.Identity.SIGLENGTH//8]
            if proof_hash == self.hash and hasattr(self.destination, "identity") and self.destination.identity != None:
                proof_valid = self.destination.identity.validate(signature, self.hash)
                if proof_valid:
                    self.status = PacketReceipt.DELIVERED
                    self.proved = True
                    self.concluded_at = time.time()
                    self.proof_packet = proof_packet

                    if self.callbacks.delivery != None:
                        try:
                            self.callbacks.delivery(self)
                        except Exception as e:
                            RNS.log(f"Error while executing proof validated callback. The contained exception was: {e}", RNS.LOG_ERROR)

                    return True
                else:
                    return False
            else:
                return False
        elif len(proof) == PacketReceipt.IMPL_LENGTH:
            # This is an implicit proof
            if self.destination.identity == None:
                return False

            signature = proof[:RNS.Identity.SIGLENGTH//8]
            proof_valid = self.destination.identity.validate(signature, self.hash)
            if proof_valid:
                    self.status = PacketReceipt.DELIVERED
                    self.proved = True
                    self.concluded_at = time.time()
                    self.proof_packet = proof_packet

                    if self.callbacks.delivery != None:
                        try:
                            self.callbacks.delivery(self)
                        except Exception as e:
                            RNS.log(f"Error while executing proof validated callback. The contained exception was: {e}", RNS.LOG_ERROR)
                            
                    return True
            else:
                return False
        else:
            return False

    def get_rtt(self):
        """
        :returns: The round-trip-time in seconds
        """
        return self.concluded_at - self.sent_at

    def is_timed_out(self):
        return (self.sent_at+self.timeout < time.time())

    def check_timeout(self):
        if self.status == PacketReceipt.SENT and self.is_timed_out():
            if self.timeout == -1:
                self.status = PacketReceipt.CULLED
            else:
                self.status = PacketReceipt.FAILED

            self.concluded_at = time.time()

            if self.callbacks.timeout:
                thread = threading.Thread(target=self.callbacks.timeout, args=(self,))
                thread.daemon = True
                thread.start()


    def set_timeout(self, timeout):
        """
        Sets a timeout in seconds
        
        :param timeout: The timeout in seconds.
        """
        self.timeout = float(timeout)

    def set_delivery_callback(self, callback):
        """
        Sets a function that gets called if a successfull delivery has been proven.

        :param callback: A *callable* with the signature *callback(packet_receipt)*
        """
        self.callbacks.delivery = callback

    # Set a function that gets called if the
    # delivery times out
    def set_timeout_callback(self, callback):
        """
        Sets a function that gets called if the delivery times out.

        :param callback: A *callable* with the signature *callback(packet_receipt)*
        """
        self.callbacks.timeout = callback

class PacketReceiptCallbacks:
    def __init__(self):
        self.delivery = None
        self.timeout  = None