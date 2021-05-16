import base64
import math
import os
import RNS
import time
import atexit
from .vendor import umsgpack as umsgpack
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import load_der_public_key
from cryptography.hazmat.primitives.serialization import load_der_private_key
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric import padding

class Identity:
    """
    This class is used to manage identities in Reticulum. It provides methods
    for encryption, decryption, signatures and verification, and is the basis
    for all encrypted communication over Reticulum networks.

    :param public_only: Specifies whether this destination only holds a public key.
    """
    KEYSIZE     = 1024
    """
    RSA key size in bits.
    """
    DERKEYSIZE  = KEYSIZE+272

    # Non-configurable constants
    PADDINGSIZE = 336       # In bits
    HASHLENGTH  = 256       # In bits
    SIGLENGTH   = KEYSIZE

    ENCRYPT_CHUNKSIZE = (KEYSIZE-PADDINGSIZE)//8
    DECRYPT_CHUNKSIZE = KEYSIZE//8

    TRUNCATED_HASHLENGTH = 80 # In bits
    """
    Constant specifying the truncated hash length (in bits) used by Reticulum
    for addressable hashes. Non-configurable.
    """

    # Storage
    known_destinations = {}

    @staticmethod
    def remember(packet_hash, destination_hash, public_key, app_data = None):
        Identity.known_destinations[destination_hash] = [time.time(), packet_hash, public_key, app_data]


    @staticmethod
    def recall(destination_hash):
        """
        Recall identity for a destination hash.

        :param destination_hash: Destination hash as *bytes*.
        :returns: An :ref:`RNS.Identity<api-identity>` instance that can be used to create an outgoing :ref:`RNS.Destination<api-destination>`, or *None* if the destination is unknown.
        """
        RNS.log("Searching for "+RNS.prettyhexrep(destination_hash)+"...", RNS.LOG_EXTREME)
        if destination_hash in Identity.known_destinations:
            identity_data = Identity.known_destinations[destination_hash]
            identity = Identity(public_only=True)
            identity.load_public_key(identity_data[2])
            identity.app_data = identity_data[3]
            RNS.log("Found "+RNS.prettyhexrep(destination_hash)+" in known destinations", RNS.LOG_EXTREME)
            return identity
        else:
            RNS.log("Could not find "+RNS.prettyhexrep(destination_hash)+" in known destinations", RNS.LOG_EXTREME)
            return None

    @staticmethod
    def recall_app_data(destination_hash):
        """
        Recall last heard app_data for a destination hash.

        :param destination_hash: Destination hash as *bytes*.
        :returns: *Bytes* containing app_data, or *None* if the destination is unknown.
        """
        RNS.log("Searching for app_data for "+RNS.prettyhexrep(destination_hash)+"...", RNS.LOG_EXTREME)
        if destination_hash in Identity.known_destinations:
            app_data = Identity.known_destinations[destination_hash][3]
            RNS.log("Found "+RNS.prettyhexrep(destination_hash)+" app_data in known destinations", RNS.LOG_EXTREME)
            return app_data
        else:
            RNS.log("Could not find "+RNS.prettyhexrep(destination_hash)+" app_data in known destinations", RNS.LOG_EXTREME)
            return None

    @staticmethod
    def save_known_destinations():
        RNS.log("Saving known destinations to storage...", RNS.LOG_VERBOSE)
        file = open(RNS.Reticulum.storagepath+"/known_destinations","wb")
        umsgpack.dump(Identity.known_destinations, file)
        file.close()
        RNS.log("Done saving known destinations to storage", RNS.LOG_VERBOSE)

    @staticmethod
    def load_known_destinations():
        if os.path.isfile(RNS.Reticulum.storagepath+"/known_destinations"):
            try:
                file = open(RNS.Reticulum.storagepath+"/known_destinations","rb")
                Identity.known_destinations = umsgpack.load(file)
                file.close()
                RNS.log("Loaded "+str(len(Identity.known_destinations))+" known destination from storage", RNS.LOG_VERBOSE)
            except:
                RNS.log("Error loading known destinations from disk, file will be recreated on exit", RNS.LOG_ERROR)
        else:
            RNS.log("Destinations file does not exist, so no known destinations loaded", RNS.LOG_VERBOSE)

    @staticmethod
    def full_hash(data):
        """
        Get a SHA-256 hash of passed data.

        :param data: Data to be hashed as *bytes*.
        :returns: SHA-256 hash as *bytes*
        """
        digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
        digest.update(data)

        return digest.finalize()

    @staticmethod
    def truncated_hash(data):
        """
        Get a truncated SHA-256 hash of passed data.

        :param data: Data to be hashed as *bytes*.
        :returns: Truncated SHA-256 hash as *bytes*
        """
        return Identity.full_hash(data)[:(Identity.TRUNCATED_HASHLENGTH//8)]

    @staticmethod
    def get_random_hash():
        """
        Get a random SHA-256 hash.

        :param data: Data to be hashed as *bytes*.
        :returns: Truncated SHA-256 hash of random data as *bytes*
        """
        return Identity.truncated_hash(os.urandom(10))

    @staticmethod
    def validate_announce(packet):
        if packet.packet_type == RNS.Packet.ANNOUNCE:
            RNS.log("Validating announce from "+RNS.prettyhexrep(packet.destination_hash), RNS.LOG_DEBUG)
            destination_hash = packet.destination_hash
            public_key = packet.data[10:Identity.DERKEYSIZE//8+10]
            random_hash = packet.data[Identity.DERKEYSIZE//8+10:Identity.DERKEYSIZE//8+20]
            signature = packet.data[Identity.DERKEYSIZE//8+20:Identity.DERKEYSIZE//8+20+Identity.KEYSIZE//8]
            app_data = b""
            if len(packet.data) > Identity.DERKEYSIZE//8+20+Identity.KEYSIZE//8:
                app_data = packet.data[Identity.DERKEYSIZE//8+20+Identity.KEYSIZE//8:]

            signed_data = destination_hash+public_key+random_hash+app_data

            if not len(packet.data) > Identity.DERKEYSIZE//8+20+Identity.KEYSIZE//8:
                app_data = None

            announced_identity = Identity(public_only=True)
            announced_identity.load_public_key(public_key)

            if announced_identity.pub != None and announced_identity.validate(signature, signed_data):
                RNS.Identity.remember(packet.get_hash(), destination_hash, public_key, app_data)
                RNS.log("Stored valid announce from "+RNS.prettyhexrep(destination_hash), RNS.LOG_DEBUG)
                del announced_identity
                return True
            else:
                RNS.log("Received invalid announce", RNS.LOG_DEBUG)
                del announced_identity
                return False

    @staticmethod
    def exit_handler():
        Identity.save_known_destinations()


    @staticmethod
    def from_file(path):
        """
        Create a new :ref:`RNS.Identity<api-identity>` instance from a file.
        Can be used to load previously created and saved identities into Reticulum.

        :param path: The full path to the saved :ref:`RNS.Identity<api-identity>` data
        :returns: A :ref:`RNS.Identity<api-identity>` instance, or *None* if the loaded data was invalid.
        """
        identity = Identity(public_only=True)
        if identity.load(path):
            return identity
        else:
            return None


    def __init__(self,public_only=False):
        # Initialize keys to none
        self.prv = None
        self.pub = None
        self.prv_bytes = None
        self.pub_bytes = None
        self.hash = None
        self.hexhash = None

        if not public_only:
            self.create_keys()

    def create_keys(self):
        self.prv = rsa.generate_private_key(
            public_exponent=65537,
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

        self.update_hashes()

        RNS.log("Identity keys created for "+RNS.prettyhexrep(self.hash), RNS.LOG_VERBOSE)

    def get_private_key(self):
        """
        :returns: The private key as *bytes*
        """
        return self.prv_bytes

    def get_public_key(self):
        """
        :returns: The public key as *bytes*
        """
        return self.pub_bytes

    def load_private_key(self, prv_bytes):
        """
        Load a private key into the instance.

        :param prv_bytes: The private key as *bytes*.
        :returns: True if the key was loaded, otherwise False.
        """
        try:
            self.prv_bytes = prv_bytes
            self.prv = serialization.load_der_private_key(
                self.prv_bytes,
                password=None,
                backend=default_backend()
            )
            self.pub = self.prv.public_key()
            self.pub_bytes = self.pub.public_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            self.update_hashes()

            return True

        except Exception as e:
            RNS.log("Failed to load identity key", RNS.LOG_ERROR)
            RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)
            return False

    def load_public_key(self, key):
        """
        Load a public key into the instance.

        :param prv_bytes: The public key as *bytes*.
        :returns: True if the key was loaded, otherwise False.
        """
        try:
            self.pub_bytes = key
            self.pub = load_der_public_key(self.pub_bytes, backend=default_backend())
            self.update_hashes()
        except Exception as e:
            RNS.log("Error while loading public key, the contained exception was: "+str(e), RNS.LOG_ERROR)

    def update_hashes(self):
        self.hash = Identity.truncated_hash(self.pub_bytes)
        self.hexhash = self.hash.hex()

    def to_file(self, path):
        """
        Saves the identity to a file. This will write the private key to disk,
        and anyone with access to this file will be able to decrypt all
        communication for the identity. Be very careful with this method.

        :param path: The full path specifying where to save the identity.
        :returns: True if the file was saved, otherwise False.
        """
        try:
            with open(path, "wb") as key_file:
                key_file.write(self.prv_bytes)
                return True
            return False
        except Exception as e:
            RNS.log("Error while saving identity to "+str(path), RNS.LOG_ERROR)
            RNS.log("The contained exception was: "+str(e))

    def load(self, path):
        try:
            with open(path, "rb") as key_file:
                prv_bytes = key_file.read()
                return self.load_private_key(prv_bytes)
            return False
        except Exception as e:
            RNS.log("Error while loading identity from "+str(path), RNS.LOG_ERROR)
            RNS.log("The contained exception was: "+str(e))

    def encrypt(self, plaintext):
        """
        Encrypts information for the identity.

        :param plaintext: The plaintext to be encrypted as *bytes*.
        :returns: Ciphertext as *bytes*.
        :raises: *KeyError* if the instance does not hold a public key
        """
        if self.pub != None:
            chunksize = Identity.ENCRYPT_CHUNKSIZE
            chunks = int(math.ceil(len(plaintext)/(float(chunksize))))

            ciphertext = b"";
            for chunk in range(chunks):
                start = chunk*chunksize
                end = (chunk+1)*chunksize
                if (chunk+1)*chunksize > len(plaintext):
                    end = len(plaintext)
                
                ciphertext += self.pub.encrypt(
                    plaintext[start:end],
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA1()),
                        algorithm=hashes.SHA1(),
                        label=None
                    )
                )
            return ciphertext
        else:
            raise KeyError("Encryption failed because identity does not hold a public key")


    def decrypt(self, ciphertext):
        """
        Decrypts information for the identity.

        :param ciphertext: The ciphertext to be decrypted as *bytes*.
        :returns: Plaintext as *bytes*, or *None* if decryption fails.
        :raises: *KeyError* if the instance does not hold a private key
        """
        if self.prv != None:
            plaintext = None
            try:
                chunksize = Identity.DECRYPT_CHUNKSIZE
                chunks = int(math.ceil(len(ciphertext)/(float(chunksize))))

                plaintext = b"";
                for chunk in range(chunks):
                    start = chunk*chunksize
                    end = (chunk+1)*chunksize
                    if (chunk+1)*chunksize > len(ciphertext):
                        end = len(ciphertext)

                    plaintext += self.prv.decrypt(
                        ciphertext[start:end],
                        padding.OAEP(
                            mgf=padding.MGF1(algorithm=hashes.SHA1()),
                            algorithm=hashes.SHA1(),
                            label=None
                        )
                    )
            except:
                RNS.log("Decryption by "+RNS.prettyhexrep(self.hash)+" failed", RNS.LOG_VERBOSE)
                
            return plaintext;
        else:
            raise KeyError("Decryption failed because identity does not hold a private key")


    def sign(self, message):
        """
        Signs information by the identity.

        :param message: The message to be signed as *bytes*.
        :returns: Signature as *bytes*.
        :raises: *KeyError* if the instance does not hold a private key
        """
        if self.prv != None:
            signature = self.prv.sign(
                message,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return signature
        else:
            raise KeyError("Signing failed because identity does not hold a private key")

    def validate(self, signature, message):
        """
        Validates the signature of a signed message.

        :param signature: The signature to be validated as *bytes*.
        :param message: The message to be validated as *bytes*.
        :returns: True if the signature is valid, otherwise False.
        :raises: *KeyError* if the instance does not hold a public key
        """
        if self.pub != None:
            try:
                self.pub.verify(
                    signature,
                    message,
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH
                    ),
                    hashes.SHA256()
                )
                return True
            except Exception as e:
                return False
        else:
            raise KeyError("Signature validation failed because identity does not hold a public key")

    def prove(self, packet, destination=None):
        signature = self.sign(packet.packet_hash)
        if RNS.Reticulum.should_use_implicit_proof():
            proof_data = signature
        else:
            proof_data = packet.packet_hash + signature
        
        if destination == None:
            destination = packet.generate_proof_destination()

        proof = RNS.Packet(destination, proof_data, RNS.Packet.PROOF, attached_interface = packet.receiving_interface)
        proof.send()

    def __str__(self):
        return RNS.prettyhexrep(self.hash)
