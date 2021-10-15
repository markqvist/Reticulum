import threading
import struct
import math
import time
import RNS

class Packet:
    """
    The Packet class is used to create packet instances that can be sent
    over a Reticulum network. Packets to will automatically be encrypted if
    they are adressed to a ``RNS.Destination.SINGLE`` destination,
    ``RNS.Destination.GROUP`` destination or a :ref:`RNS.Link<api-link>`.

    For ``RNS.Destination.GROUP`` destinations, Reticulum will use the
    pre-shared key configured for the destination.

    For ``RNS.Destination.SINGLE`` destinations and :ref:`RNS.Link<api-link>`
    destinations, reticulum will use ephemeral keys, and offers **Forward Secrecy**.

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
    HEADER_3     = 0x02     # Reserved
    HEADER_4     = 0x03     # Reserved
    header_types = [HEADER_1, HEADER_2, HEADER_3, HEADER_4]

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
    KEEPALIVE      = 0xFA   # Packet is a keepalive packet
    LINKIDENTIFY   = 0xFB   # Packet is a link peer identification proof
    LINKCLOSE      = 0xFC   # Packet is a link close message
    LINKPROOF      = 0xFD   # Packet is a link packet proof
    LRRTT          = 0xFE   # Packet is a link request round-trip time measurement
    LRPROOF        = 0xFF   # Packet is a link request proof

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

    # This value is set at a reasonable
    # level for a 1 Kb/s channel.
    TIMEOUT_PER_HOP = 5

    def __init__(self, destination, data, packet_type = DATA, context = NONE, transport_type = RNS.Transport.BROADCAST, header_type = HEADER_1, transport_id = None, attached_interface = None, create_receipt = True):
        if destination != None:
            if transport_type == None:
                transport_type = RNS.Transport.BROADCAST

            self.header_type    = header_type
            self.packet_type    = packet_type
            self.transport_type = transport_type
            self.context        = context

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

        self.attached_interface = attached_interface
        self.receiving_interface = None
        self.rssi = None
        self.snr = None

    def get_packed_flags(self):
        if self.context == Packet.LRPROOF:
            packed_flags = (self.header_type << 6) | (self.transport_type << 4) | RNS.Destination.LINK | self.packet_type
        else:
            packed_flags = (self.header_type << 6) | (self.transport_type << 4) | (self.destination.type << 2) | self.packet_type
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
                    # A resource takes care of symmetric
                    # encryption by itself
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

            if self.header_type == Packet.HEADER_2:
                if self.transport_id != None:
                    self.header += self.transport_id
                    self.header += self.destination.hash

                    if self.packet_type == Packet.ANNOUNCE:
                        # Announce packets are not encrypted
                        self.ciphertext = self.data
                else:
                    raise IOError("Packet with header type 2 must have a transport ID")


        self.header += bytes([self.context])
        self.raw = self.header + self.ciphertext

        if len(self.raw) > self.MTU:
            raise IOError("Packet size of "+str(len(self.raw))+" exceeds MTU of "+str(self.MTU)+" bytes")

        self.packed = True
        self.update_hash()


    def unpack(self):
        self.flags = self.raw[0]
        self.hops  = self.raw[1]

        self.header_type      = (self.flags & 0b11000000) >> 6
        self.transport_type   = (self.flags & 0b00110000) >> 4
        self.destination_type = (self.flags & 0b00001100) >> 2
        self.packet_type      = (self.flags & 0b00000011)

        if self.header_type == Packet.HEADER_2:
            self.transport_id = self.raw[2:12]
            self.destination_hash = self.raw[12:22]
            self.context = ord(self.raw[22:23])
            self.data = self.raw[23:]
        else:
            self.transport_id = None
            self.destination_hash = self.raw[2:12]
            self.context = ord(self.raw[12:13])
            self.data = self.raw[13:]

        self.packed = False
        self.update_hash()

    def send(self):
        """
        Sends the packet.
        
        :returns: A :ref:`RNS.PacketReceipt<api-packetreceipt>` instance if *create_receipt* was set to *True* when the packet was instantiated, if not returns *None*. If the packet could not be sent *False* is returned.
        """
        if not self.sent:
            if self.destination.type == RNS.Destination.LINK:
                if self.destination.status == RNS.Link.CLOSED:
                    raise IOError("Attempt to transmit over a closed link")
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
            raise IOError("Packet was already sent")

    def resend(self):
        """
        Re-sends the packet.
        
        :returns: A :ref:`RNS.PacketReceipt<api-packetreceipt>` instance if *create_receipt* was set to *True* when the packet was instantiated, if not returns *None*. If the packet could not be sent *False* is returned.
        """
        if self.sent:
            if RNS.Transport.outbound(self):
                return self.receipt
            else:
                RNS.log("No interfaces could process the outbound packet", RNS.LOG_ERROR)
                self.sent = False
                self.receipt = None
                return False
        else:
            raise IOError("Packet was not sent yet")

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
            hashable_part += self.raw[12:]
        else:
            hashable_part += self.raw[2:]

        return hashable_part

class ProofDestination:
    def __init__(self, packet):
        self.hash = packet.get_hash()[:10];
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
            self.timeout    = packet.destination.rtt * packet.destination.traffic_timeout_factor
        else:
            self.timeout    = Packet.TIMEOUT_PER_HOP * RNS.Transport.hops_to(self.destination.hash)


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

                    if self.callbacks.delivery != None:
                        self.callbacks.delivery(self)
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
            if proof_hash == self.hash:
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
                            RNS.log("Error while executing proof validated callback. The contained exception was: "+str(e), RNS.LOG_ERROR)

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
                            RNS.log("Error while executing proof validated callback. The contained exception was: "+str(e), RNS.LOG_ERROR)
                            
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
                thread.setDaemon(True)
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