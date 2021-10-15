import base64
import math
import time
import RNS

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

class Callbacks:
    def __init__(self):
        self.link_established = None
        self.packet = None
        self.proof_requested = None

class Destination:
    """
    A class used to describe endpoints in a Reticulum Network. Destination
    instances are used both to create outgoing and incoming endpoints. The
    destination type will decide if encryption, and what type, is used in
    communication with the endpoint. A destination can also announce its
    presence on the network, which will also distribute necessary keys for
    encrypted communication with it.

    :param identity: An instance of :ref:`RNS.Identity<api-identity>`. Can hold only public keys for an outgoing destination, or holding private keys for an ingoing.
    :param direction: ``RNS.Destination.IN`` or ``RNS.Destination.OUT``.
    :param type: ``RNS.Destination.SINGLE``, ``RNS.Destination.GROUP`` or ``RNS.Destination.PLAIN``.
    :param app_name: A string specifying the app name.
    :param \*aspects: Any non-zero number of string arguments.
    """

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

    ALLOW_NONE = 0x00
    ALLOW_ALL  = 0x01
    ALLOW_LIST = 0x02
    request_policies = [ALLOW_NONE, ALLOW_ALL, ALLOW_LIST]

    IN         = 0x11;
    OUT        = 0x12;
    directions = [IN, OUT]

    @staticmethod
    def full_name(app_name, *aspects):
        """
        :returns: A string containing the full human-readable name of the destination, for an app_name and a number of aspects.
        """

        # Check input values and build name string
        if "." in app_name: raise ValueError("Dots can't be used in app names")

        name = app_name
        for aspect in aspects:
            if "." in aspect: raise ValueError("Dots can't be used in aspects")
            name = name + "." + aspect

        return name


    @staticmethod
    def hash(app_name, *aspects):
        """
        :returns: A destination name in adressable hash form, for an app_name and a number of aspects.
        """
        name = Destination.full_name(app_name, *aspects)

        # Create a digest for the destination
        digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
        digest.update(name.encode("UTF-8"))

        return digest.finalize()[:10]

    @staticmethod
    def app_and_aspects_from_name(full_name):
        """
        :returns: A tuple containing the app name and a list of aspects, for a full-name string.
        """
        components = full_name.split(".")
        return (components[0], components[1:])

    @staticmethod
    def hash_from_name_and_identity(full_name, identity):
        """
        :returns: A destination name in adressable hash form, for a full name string and Identity instance.
        """
        app_name, aspects = Destination.app_and_aspects_from_name(full_name)
        aspects.append(identity.hexhash)
        return Destination.hash(app_name, *aspects)

    def __init__(self, identity, direction, type, app_name, *aspects):
        # Check input values and build name string
        if "." in app_name: raise ValueError("Dots can't be used in app names") 
        if not type in Destination.types: raise ValueError("Unknown destination type")
        if not direction in Destination.directions: raise ValueError("Unknown destination direction")
        self.callbacks = Callbacks()
        self.request_handlers = {}
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

        self.name = Destination.full_name(app_name, *aspects)      
        self.hash = Destination.hash(app_name, *aspects)
        self.hexhash = self.hash.hex()
        self.default_app_data = None

        self.callback = None
        self.proofcallback = None

        RNS.Transport.register_destination(self)


    def __str__(self):
        """
        :returns: A human-readable representation of the destination including addressable hash and full name.
        """
        return "<"+self.name+"/"+self.hexhash+">"


    def announce(self, app_data=None, path_response=False):
        """
        Creates an announce packet for this destination and broadcasts it on all
        relevant interfaces. Application specific data can be added to the announce.

        :param app_data: *bytes* containing the app_data.
        :param path_response: Internal flag used by :ref:`RNS.Transport<api-transport>`. Ignore.
        """
        destination_hash = self.hash
        random_hash = RNS.Identity.get_random_hash()[0:5]+int(time.time()).to_bytes(5, "big")

        if app_data == None and self.default_app_data != None:
            if isinstance(self.default_app_data, bytes):
                app_data = self.default_app_data
            elif callable(self.default_app_data):
                returned_app_data = self.default_app_data()
                if isinstance(returned_app_data, bytes):
                    app_data = returned_app_data
        
        signed_data = self.hash+self.identity.get_public_key()+random_hash
        if app_data != None:
            signed_data += app_data

        signature = self.identity.sign(signed_data)

        announce_data = self.identity.get_public_key()+random_hash+signature

        if app_data != None:
            announce_data += app_data

        if path_response:
            announce_context = RNS.Packet.PATH_RESPONSE
        else:
            announce_context = RNS.Packet.NONE

        RNS.Packet(self, announce_data, RNS.Packet.ANNOUNCE, context = announce_context).send()


    def set_link_established_callback(self, callback):
        """
        Registers a function to be called when a link has been established to
        this destination.

        :param callback: A function or method to be called.
        """
        self.callbacks.link_established = callback

    def set_packet_callback(self, callback):
        """
        Registers a function to be called when a packet has been received by
        this destination.

        :param callback: A function or method to be called.
        """
        self.callbacks.packet = callback

    def set_proof_requested_callback(self, callback):
        """
        Registers a function to be called when a proof has been requested for
        a packet sent to this destination. Allows control over when and if
        proofs should be returned for received packets.

        :param callback: A function or method to be called. The callback must return one of True or False. If the callback returns True, a proof will be sent. If it returns False, a proof will not be sent.
        """
        self.callbacks.proof_requested = callback

    def set_proof_strategy(self, proof_strategy):
        """
        Sets the destinations proof strategy.

        :param proof_strategy: One of ``RNS.Destination.PROVE_NONE``, ``RNS.Destination.PROVE_ALL`` or ``RNS.Destination.PROVE_APP``. If ``RNS.Destination.PROVE_APP`` is set, the `proof_requested_callback` will be called to determine whether a proof should be sent or not.
        """
        if not proof_strategy in Destination.proof_strategies:
            raise TypeError("Unsupported proof strategy")
        else:
            self.proof_strategy = proof_strategy


    def register_request_handler(self, path, response_generator = None, allow = ALLOW_NONE, allowed_list = None):
        """
        Registers a request handler.

        :param path: The path for the request handler to be registered.
        :param response_generator: A function or method with the signature *response_generator(path, data, request_id, remote_identity, requested_at)* to be called. Whatever this funcion returns will be sent as a response to the requester. If the function returns ``None``, no response will be sent.
        :param allow: One of ``RNS.Destination.ALLOW_NONE``, ``RNS.Destination.ALLOW_ALL`` or ``RNS.Destination.ALLOW_LIST``. If ``RNS.Destination.ALLOW_LIST`` is set, the request handler will only respond to requests for identified peers in the supplied list.
        :param allowed_list: A list of *bytes-like* :ref:`RNS.Identity<api-identity>` hashes.
        :raises: ``ValueError`` if any of the supplied arguments are invalid.
        """
        if path == None or path == "":
            raise ValueError("Invalid path specified")
        elif not callable(response_generator):
            raise ValueError("Invalid response generator specified")
        elif not allow in Destination.request_policies:
            raise ValueError("Invalid request policy")
        else:
            path_hash = RNS.Identity.truncated_hash(path.encode("utf-8"))
            request_handler = [path, response_generator, allow, allowed_list]
            self.request_handlers[path_hash] = request_handler


    def deregister_request_handler(self, path):
        """
        Deregisters a request handler.

        :param path: The path for the request handler to be deregistered.
        :returns: True if the handler was deregistered, otherwise False.
        """
        path_hash = RNS.Identity.truncated_hash(path.encode("utf-8"))
        if path_hash in self.request_handlers:
            self.request_handlers.pop(path_hash)
            return True
        else:
            return False

        

    def receive(self, packet):
        if packet.packet_type == RNS.Packet.LINKREQUEST:
            plaintext = packet.data
            self.incoming_link_request(plaintext, packet)
        else:
            plaintext = self.decrypt(packet.data)
            if plaintext != None:
                if packet.packet_type == RNS.Packet.DATA:
                    if self.callbacks.packet != None:
                        try:
                            self.callbacks.packet(plaintext, packet)
                        except Exception as e:
                            RNS.log("Error while executing receive callback from "+str(self)+". The contained exception was: "+str(e), RNS.LOG_ERROR)


    def incoming_link_request(self, data, packet):
        link = RNS.Link.validate_request(self, data, packet)
        if link != None:
            self.links.append(link)

    def create_keys(self):
        """
        For a ``RNS.Destination.GROUP`` type destination, creates a new symmetric key.

        :raises: ``TypeError`` if called on an incompatible type of destination.
        """
        if self.type == Destination.PLAIN:
            raise TypeError("A plain destination does not hold any keys")

        if self.type == Destination.SINGLE:
            raise TypeError("A single destination holds keys through an Identity instance")

        if self.type == Destination.GROUP:
            self.prv_bytes = base64.urlsafe_b64decode(Fernet.generate_key())
            self.prv = Fernet(base64.urlsafe_b64encode(self.prv_bytes))


    def get_private_key(self):
        """
        For a ``RNS.Destination.GROUP`` type destination, returns the symmetric private key.

        :raises: ``TypeError`` if called on an incompatible type of destination.
        """
        if self.type == Destination.PLAIN:
            raise TypeError("A plain destination does not hold any keys")
        elif self.type == Destination.SINGLE:
            raise TypeError("A single destination holds keys through an Identity instance")
        else:
            return self.prv_bytes


    def load_private_key(self, key):
        """
        For a ``RNS.Destination.GROUP`` type destination, loads a symmetric private key.

        :param key: A *bytes-like* containing the symmetric key.
        :raises: ``TypeError`` if called on an incompatible type of destination.
        """
        if self.type == Destination.PLAIN:
            raise TypeError("A plain destination does not hold any keys")

        if self.type == Destination.SINGLE:
            raise TypeError("A single destination holds keys through an Identity instance")

        if self.type == Destination.GROUP:
            self.prv_bytes = key
            self.prv = Fernet(base64.urlsafe_b64encode(self.prv_bytes))

    def load_public_key(self, key):
        if self.type != Destination.SINGLE:
            raise TypeError("Only the \"single\" destination type can hold a public key")
        else:
            raise TypeError("A single destination holds keys through an Identity instance")


    def encrypt(self, plaintext):
        """
        Encrypts information for ``RNS.Destination.SINGLE`` or ``RNS.Destination.GROUP`` type destination.

        :param plaintext: A *bytes-like* containing the plaintext to be encrypted.
        :raises: ``ValueError`` if destination does not hold a necessary key for encryption.
        """
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
        """
        Decrypts information for ``RNS.Destination.SINGLE`` or ``RNS.Destination.GROUP`` type destination.

        :param ciphertext: *Bytes* containing the ciphertext to be decrypted.
        :raises: ``ValueError`` if destination does not hold a necessary key for decryption.
        """
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
        """
        Signs information for ``RNS.Destination.SINGLE`` type destination.

        :param message: *Bytes* containing the message to be signed.
        :returns: A *bytes-like* containing the message signature, or *None* if the destination could not sign the message.
        """
        if self.type == Destination.SINGLE and self.identity != None:
            return self.identity.sign(message)
        else:
            return None

    def set_default_app_data(self, app_data=None):
        """
        Sets the default app_data for the destination. If set, the default
        app_data will be included in every announce sent by the destination,
        unless other app_data is specified in the *announce* method.

        :param app_data: A *bytes-like* containing the default app_data, or a *callable* returning a *bytes-like* containing the app_data.
        """
        self.default_app_data = app_data

    def clear_default_app_data(self):
        """
        Clears default app_data previously set for the destination.
        """
        self.set_default_app_data(app_data=None)