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
   #KEYSIZE     = 1536
    KEYSIZE     = 1024
    DERKEYSIZE  = KEYSIZE+272

    # Non-configurable constants
    PADDINGSIZE = 336       # In bits
    HASHLENGTH  = 256       # In bits
    SIGLENGTH   = KEYSIZE

    ENCRYPT_CHUNKSIZE = (KEYSIZE-PADDINGSIZE)//8
    DECRYPT_CHUNKSIZE = KEYSIZE//8

    TRUNCATED_HASHLENGTH = 80 # In bits

    # Storage
    known_destinations = {}

    @staticmethod
    def remember(packet_hash, destination_hash, public_key, app_data = None):
        Identity.known_destinations[destination_hash] = [time.time(), packet_hash, public_key, app_data]


    @staticmethod
    def recall(destination_hash):
        RNS.log("Searching for "+RNS.prettyhexrep(destination_hash)+"...", RNS.LOG_EXTREME)
        if destination_hash in Identity.known_destinations:
            identity_data = Identity.known_destinations[destination_hash]
            identity = Identity(public_only=True)
            identity.loadPublicKey(identity_data[2])
            identity.app_data = identity_data[3]
            RNS.log("Found "+RNS.prettyhexrep(destination_hash)+" in known destinations", RNS.LOG_EXTREME)
            return identity
        else:
            RNS.log("Could not find "+RNS.prettyhexrep(destination_hash)+" in known destinations", RNS.LOG_EXTREME)
            return None

    @staticmethod
    def recall_app_data(destination_hash):
        RNS.log("Searching for app_data for "+RNS.prettyhexrep(destination_hash)+"...", RNS.LOG_EXTREME)
        if destination_hash in Identity.known_destinations:
            app_data = Identity.known_destinations[destination_hash][3]
            RNS.log("Found "+RNS.prettyhexrep(destination_hash)+" app_data in known destinations", RNS.LOG_EXTREME)
            return app_data
        else:
            RNS.log("Could not find "+RNS.prettyhexrep(destination_hash)+" app_data in known destinations", RNS.LOG_EXTREME)
            return None

    @staticmethod
    def saveKnownDestinations():
        RNS.log("Saving known destinations to storage...", RNS.LOG_VERBOSE)
        file = open(RNS.Reticulum.storagepath+"/known_destinations","wb")
        umsgpack.dump(Identity.known_destinations, file)
        file.close()
        RNS.log("Done saving known destinations to storage", RNS.LOG_VERBOSE)

    @staticmethod
    def loadKnownDestinations():
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
    def fullHash(data):
        digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
        digest.update(data)

        return digest.finalize()

    @staticmethod
    def truncatedHash(data):
        return Identity.fullHash(data)[:(Identity.TRUNCATED_HASHLENGTH//8)]

    @staticmethod
    def getRandomHash():
        return Identity.truncatedHash(os.urandom(10))

    @staticmethod
    def validateAnnounce(packet):
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
            announced_identity.loadPublicKey(public_key)

            if announced_identity.pub != None and announced_identity.validate(signature, signed_data):
                RNS.Identity.remember(packet.getHash(), destination_hash, public_key, app_data)
                RNS.log("Stored valid announce from "+RNS.prettyhexrep(destination_hash), RNS.LOG_DEBUG)
                del announced_identity
                return True
            else:
                RNS.log("Received invalid announce", RNS.LOG_DEBUG)
                del announced_identity
                return False

    @staticmethod
    def exitHandler():
        Identity.saveKnownDestinations()


    @staticmethod
    def from_file(path):
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
            self.createKeys()

    def createKeys(self):
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

        self.updateHashes()

        RNS.log("Identity keys created for "+RNS.prettyhexrep(self.hash), RNS.LOG_VERBOSE)

    def getPrivateKey(self):
        return self.prv_bytes

    def getPublicKey(self):
        return self.pub_bytes

    def loadPrivateKey(self, prv_bytes):
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
            self.updateHashes()

            return True

        except Exception as e:
            RNS.log("Failed to load identity key", RNS.LOG_ERROR)
            RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)
            return False

    def loadPublicKey(self, key):
        try:
            self.pub_bytes = key
            self.pub = load_der_public_key(self.pub_bytes, backend=default_backend())
            self.updateHashes()
        except Exception as e:
            RNS.log("Error while loading public key, the contained exception was: "+str(e), RNS.LOG_ERROR)

    def updateHashes(self):
        self.hash = Identity.truncatedHash(self.pub_bytes)
        self.hexhash = self.hash.hex()

    def save(self, path):
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
                return self.loadPrivateKey(prv_bytes)
            return False
        except Exception as e:
            RNS.log("Error while loading identity from "+str(path), RNS.LOG_ERROR)
            RNS.log("The contained exception was: "+str(e))

    def encrypt(self, plaintext):
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
            destination = packet.generateProofDestination()

        proof = RNS.Packet(destination, proof_data, RNS.Packet.PROOF, attached_interface = packet.receiving_interface)
        proof.send()

    def __str__(self):
        return RNS.prettyhexrep(self.hash)
