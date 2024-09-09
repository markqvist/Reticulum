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

import math
import os
import RNS
import time
import atexit
import hashlib
import threading

from .vendor import umsgpack as umsgpack

from RNS.Cryptography import X25519PrivateKey, X25519PublicKey, Ed25519PrivateKey, Ed25519PublicKey
from RNS.Cryptography import Fernet


class Identity:
    """
    This class is used to manage identities in Reticulum. It provides methods
    for encryption, decryption, signatures and verification, and is the basis
    for all encrypted communication over Reticulum networks.

    :param create_keys: Specifies whether new encryption and signing keys should be generated.
    """

    CURVE = "Curve25519"
    """
    The curve used for Elliptic Curve DH key exchanges
    """

    KEYSIZE     = 256*2
    """
    X.25519 key size in bits. A complete key is the concatenation of a 256 bit encryption key, and a 256 bit signing key.
    """

    RATCHETSIZE = 256
    """
    X.25519 ratchet key size in bits.
    """

    RATCHET_EXPIRY = 60*60*24*30
    """
    The expiry time for received ratchets in seconds, defaults to 30 days. Reticulum will always use the most recently
    announced ratchet, and remember it for up to ``RATCHET_EXPIRY`` since receiving it, after which it will be discarded.
    If a newer ratchet is announced in the meantime, it will be replace the already known ratchet.
    """

    # Non-configurable constants
    FERNET_OVERHEAD           = RNS.Cryptography.Fernet.FERNET_OVERHEAD
    AES128_BLOCKSIZE          = 16          # In bytes
    HASHLENGTH                = 256         # In bits
    SIGLENGTH                 = KEYSIZE     # In bits

    NAME_HASH_LENGTH     = 80
    TRUNCATED_HASHLENGTH = RNS.Reticulum.TRUNCATED_HASHLENGTH
    """
    Constant specifying the truncated hash length (in bits) used by Reticulum
    for addressable hashes and other purposes. Non-configurable.
    """

    # Storage
    known_destinations = {}
    known_ratchets = {}

    ratchet_persist_lock = threading.Lock()

    @staticmethod
    def remember(packet_hash, destination_hash, public_key, app_data = None):
        if len(public_key) != Identity.KEYSIZE//8:
            raise TypeError("Can't remember "+RNS.prettyhexrep(destination_hash)+", the public key size of "+str(len(public_key))+" is not valid.", RNS.LOG_ERROR)
        else:
            Identity.known_destinations[destination_hash] = [time.time(), packet_hash, public_key, app_data]


    @staticmethod
    def recall(destination_hash):
        """
        Recall identity for a destination hash.

        :param destination_hash: Destination hash as *bytes*.
        :returns: An :ref:`RNS.Identity<api-identity>` instance that can be used to create an outgoing :ref:`RNS.Destination<api-destination>`, or *None* if the destination is unknown.
        """
        if destination_hash in Identity.known_destinations:
            identity_data = Identity.known_destinations[destination_hash]
            identity = Identity(create_keys=False)
            identity.load_public_key(identity_data[2])
            identity.app_data = identity_data[3]
            return identity
        else:
            for registered_destination in RNS.Transport.destinations:
                if destination_hash == registered_destination.hash:
                    identity = Identity(create_keys=False)
                    identity.load_public_key(registered_destination.identity.get_public_key())
                    identity.app_data = None
                    return identity

            return None

    @staticmethod
    def recall_app_data(destination_hash):
        """
        Recall last heard app_data for a destination hash.

        :param destination_hash: Destination hash as *bytes*.
        :returns: *Bytes* containing app_data, or *None* if the destination is unknown.
        """
        if destination_hash in Identity.known_destinations:
            app_data = Identity.known_destinations[destination_hash][3]
            return app_data
        else:
            return None

    @staticmethod
    def save_known_destinations():
        # TODO: Improve the storage method so we don't have to
        # deserialize and serialize the entire table on every
        # save, but the only changes. It might be possible to
        # simply overwrite on exit now that every local client
        # disconnect triggers a data persist.
        
        try:
            if hasattr(Identity, "saving_known_destinations"):
                wait_interval = 0.2
                wait_timeout = 5
                wait_start = time.time()
                while Identity.saving_known_destinations:
                    time.sleep(wait_interval)
                    if time.time() > wait_start+wait_timeout:
                        RNS.log("Could not save known destinations to storage, waiting for previous save operation timed out.", RNS.LOG_ERROR)
                        return False

            Identity.saving_known_destinations = True
            save_start = time.time()

            storage_known_destinations = {}
            if os.path.isfile(RNS.Reticulum.storagepath+"/known_destinations"):
                try:
                    file = open(RNS.Reticulum.storagepath+"/known_destinations","rb")
                    storage_known_destinations = umsgpack.load(file)
                    file.close()
                except:
                    pass

            try:
                for destination_hash in storage_known_destinations:
                    if not destination_hash in Identity.known_destinations:
                        Identity.known_destinations[destination_hash] = storage_known_destinations[destination_hash]
            except Exception as e:
                RNS.log("Skipped recombining known destinations from disk, since an error occurred: "+str(e), RNS.LOG_WARNING)

            RNS.log("Saving "+str(len(Identity.known_destinations))+" known destinations to storage...", RNS.LOG_DEBUG)
            file = open(RNS.Reticulum.storagepath+"/known_destinations","wb")
            umsgpack.dump(Identity.known_destinations, file)
            file.close()

            save_time = time.time() - save_start
            if save_time < 1:
                time_str = str(round(save_time*1000,2))+"ms"
            else:
                time_str = str(round(save_time,2))+"s"

            RNS.log("Saved known destinations to storage in "+time_str, RNS.LOG_DEBUG)

        except Exception as e:
            RNS.log("Error while saving known destinations to disk, the contained exception was: "+str(e), RNS.LOG_ERROR)
            RNS.trace_exception(e)

        Identity.saving_known_destinations = False

    @staticmethod
    def load_known_destinations():
        if os.path.isfile(RNS.Reticulum.storagepath+"/known_destinations"):
            try:
                file = open(RNS.Reticulum.storagepath+"/known_destinations","rb")
                loaded_known_destinations = umsgpack.load(file)
                file.close()

                Identity.known_destinations = {}
                for known_destination in loaded_known_destinations:
                    if len(known_destination) == RNS.Reticulum.TRUNCATED_HASHLENGTH//8:
                        Identity.known_destinations[known_destination] = loaded_known_destinations[known_destination]

                RNS.log("Loaded "+str(len(Identity.known_destinations))+" known destination from storage", RNS.LOG_VERBOSE)

            except Exception as e:
                RNS.log("Error loading known destinations from disk, file will be recreated on exit", RNS.LOG_ERROR)
        else:
            RNS.log("Destinations file does not exist, no known destinations loaded", RNS.LOG_VERBOSE)

    @staticmethod
    def full_hash(data):
        """
        Get a SHA-256 hash of passed data.

        :param data: Data to be hashed as *bytes*.
        :returns: SHA-256 hash as *bytes*.
        """
        return RNS.Cryptography.sha256(data)

    @staticmethod
    def truncated_hash(data):
        """
        Get a truncated SHA-256 hash of passed data.

        :param data: Data to be hashed as *bytes*.
        :returns: Truncated SHA-256 hash as *bytes*.
        """
        return Identity.full_hash(data)[:(Identity.TRUNCATED_HASHLENGTH//8)]

    @staticmethod
    def get_random_hash():
        """
        Get a random SHA-256 hash.

        :param data: Data to be hashed as *bytes*.
        :returns: Truncated SHA-256 hash of random data as *bytes*.
        """
        return Identity.truncated_hash(os.urandom(Identity.TRUNCATED_HASHLENGTH//8))

    @staticmethod
    def current_ratchet_id(destination_hash):
        """
        Get the ID of the currently used ratchet key for a given destination hash

        :param destination_hash: A destination hash as *bytes*.
        :returns: A ratchet ID as *bytes* or *None*.
        """
        ratchet = Identity.get_ratchet(destination_hash)
        if ratchet == None:
            return None
        else:
            return Identity._get_ratchet_id(ratchet)

    @staticmethod
    def _get_ratchet_id(ratchet_pub_bytes):
        return Identity.full_hash(ratchet_pub_bytes)[:Identity.NAME_HASH_LENGTH//8]

    @staticmethod
    def _ratchet_public_bytes(ratchet):
        return X25519PrivateKey.from_private_bytes(ratchet).public_key().public_bytes()

    @staticmethod
    def _generate_ratchet():
        ratchet_prv = X25519PrivateKey.generate()
        ratchet_pub = ratchet_prv.public_key()
        return ratchet_prv.private_bytes()

    @staticmethod
    def _remember_ratchet(destination_hash, ratchet):
        # TODO: Remove at some point, and only log new ratchets
        RNS.log(f"Remembering ratchet {RNS.prettyhexrep(Identity._get_ratchet_id(ratchet))} for {RNS.prettyhexrep(destination_hash)}", RNS.LOG_EXTREME)
        try:
            Identity.known_ratchets[destination_hash] = ratchet

            if not RNS.Transport.owner.is_connected_to_shared_instance:
                def persist_job():
                    with Identity.ratchet_persist_lock:
                        hexhash = RNS.hexrep(destination_hash, delimit=False)
                        ratchet_data = {"ratchet": ratchet, "received": time.time()}

                        ratchetdir = RNS.Reticulum.storagepath+"/ratchets"
                        
                        if not os.path.isdir(ratchetdir):
                            os.makedirs(ratchetdir)

                        outpath   = f"{ratchetdir}/{hexhash}.out"
                        finalpath = f"{ratchetdir}/{hexhash}"
                        ratchet_file = open(outpath, "wb")
                        ratchet_file.write(umsgpack.packb(ratchet_data))
                        ratchet_file.close()
                        os.replace(outpath, finalpath)

                
                threading.Thread(target=persist_job, daemon=True).start()

        except Exception as e:
            RNS.log(f"Could not persist ratchet for {RNS.prettyhexrep(destination_hash)} to storage.", RNS.LOG_ERROR)
            RNS.log(f"The contained exception was: {e}")
            RNS.trace_exception(e)

    @staticmethod
    def _clean_ratchets():
        RNS.log("Cleaning ratchets...", RNS.LOG_DEBUG)
        try:
            now = time.time()
            ratchetdir = RNS.Reticulum.storagepath+"/ratchets"
            if os.path.isdir(ratchetdir):
                for filename in os.listdir(ratchetdir):
                    try:
                        expired = False
                        with open(f"{ratchetdir}/{filename}", "rb") as rf:
                            ratchet_data = umsgpack.unpackb(rf.read())
                            if now > ratchet_data["received"]+Identity.RATCHET_EXPIRY:
                                expired = True

                        if expired:
                            os.unlink(f"{ratchetdir}/{filename}")

                    except Exception as e:
                        RNS.log(f"An error occurred while cleaning ratchets, in the processing of {ratchetdir}/{filename}.", RNS.LOG_ERROR)
                        RNS.log(f"The contained exception was: {e}", RNS.LOG_ERROR)

        except Exception as e:
            RNS.log(f"An error occurred while cleaning ratchets. The contained exception was: {e}", RNS.LOG_ERROR)

    @staticmethod
    def get_ratchet(destination_hash):
        if not destination_hash in Identity.known_ratchets:
            ratchetdir = RNS.Reticulum.storagepath+"/ratchets"
            hexhash = RNS.hexrep(destination_hash, delimit=False)
            ratchet_path = f"{ratchetdir}/{hexhash}"
            if os.path.isfile(ratchet_path):
                try:
                    ratchet_file = open(ratchet_path, "rb")
                    ratchet_data = umsgpack.unpackb(ratchet_file.read())
                    if time.time() < ratchet_data["received"]+Identity.RATCHET_EXPIRY and len(ratchet_data["ratchet"]) == Identity.RATCHETSIZE//8:
                        Identity.known_ratchets[destination_hash] = ratchet_data["ratchet"]
                    else:
                        return None
                
                except Exception as e:
                    RNS.log(f"An error occurred while loading ratchet data for {RNS.prettyhexrep(destination_hash)} from storage.", RNS.LOG_ERROR)
                    RNS.log(f"The contained exception was: {e}", RNS.LOG_ERROR)
                    return None

        if destination_hash in Identity.known_ratchets:
            return Identity.known_ratchets[destination_hash]
        else:
            RNS.log(f"Could not load ratchet for {RNS.prettyhexrep(destination_hash)}", RNS.LOG_DEBUG)
            return None

    @staticmethod
    def validate_announce(packet, only_validate_signature=False):
        try:
            if packet.packet_type == RNS.Packet.ANNOUNCE:
                keysize       = Identity.KEYSIZE//8
                ratchetsize   = Identity.RATCHETSIZE//8
                name_hash_len = Identity.NAME_HASH_LENGTH//8
                sig_len       = Identity.SIGLENGTH//8
                destination_hash = packet.destination_hash

                # Get public key bytes from announce
                public_key = packet.data[:keysize]

                # If the packet context flag is set,
                # this announce contains a new ratchet
                if packet.context_flag == RNS.Packet.FLAG_SET:
                    name_hash   = packet.data[keysize:keysize+name_hash_len ]
                    random_hash = packet.data[keysize+name_hash_len:keysize+name_hash_len+10]
                    ratchet     = packet.data[keysize+name_hash_len+10:keysize+name_hash_len+10+ratchetsize]
                    signature   = packet.data[keysize+name_hash_len+10+ratchetsize:keysize+name_hash_len+10+ratchetsize+sig_len]
                    app_data    = b""
                    if len(packet.data) > keysize+name_hash_len+10+sig_len+ratchetsize:
                        app_data = packet.data[keysize+name_hash_len+10+sig_len+ratchetsize:]

                # If the packet context flag is not set,
                # this announce does not contain a ratchet
                else:
                    ratchet     = b""
                    name_hash   = packet.data[keysize:keysize+name_hash_len]
                    random_hash = packet.data[keysize+name_hash_len:keysize+name_hash_len+10]
                    signature   = packet.data[keysize+name_hash_len+10:keysize+name_hash_len+10+sig_len]
                    app_data    = b""
                    if len(packet.data) > keysize+name_hash_len+10+sig_len:
                        app_data = packet.data[keysize+name_hash_len+10+sig_len:]

                signed_data = destination_hash+public_key+name_hash+random_hash+ratchet+app_data

                if not len(packet.data) > Identity.KEYSIZE//8+Identity.NAME_HASH_LENGTH//8+10+Identity.SIGLENGTH//8:
                    app_data = None

                announced_identity = Identity(create_keys=False)
                announced_identity.load_public_key(public_key)

                if announced_identity.pub != None and announced_identity.validate(signature, signed_data):
                    if only_validate_signature:
                        del announced_identity
                        return True

                    hash_material = name_hash+announced_identity.hash
                    expected_hash = RNS.Identity.full_hash(hash_material)[:RNS.Reticulum.TRUNCATED_HASHLENGTH//8]

                    if destination_hash == expected_hash:
                        # Check if we already have a public key for this destination
                        # and make sure the public key is not different.
                        if destination_hash in Identity.known_destinations:
                            if public_key != Identity.known_destinations[destination_hash][2]:
                                # In reality, this should never occur, but in the odd case
                                # that someone manages a hash collision, we reject the announce.
                                RNS.log("Received announce with valid signature and destination hash, but announced public key does not match already known public key.", RNS.LOG_CRITICAL)
                                RNS.log("This may indicate an attempt to modify network paths, or a random hash collision. The announce was rejected.", RNS.LOG_CRITICAL)
                                return False

                        RNS.Identity.remember(packet.get_hash(), destination_hash, public_key, app_data)
                        del announced_identity

                        if packet.rssi != None or packet.snr != None:
                            signal_str = " ["
                            if packet.rssi != None:
                                signal_str += "RSSI "+str(packet.rssi)+"dBm"
                                if packet.snr != None:
                                    signal_str += ", "
                            if packet.snr != None:
                                signal_str += "SNR "+str(packet.snr)+"dB"
                            signal_str += "]"
                        else:
                            signal_str = ""

                        if hasattr(packet, "transport_id") and packet.transport_id != None:
                            RNS.log("Valid announce for "+RNS.prettyhexrep(destination_hash)+" "+str(packet.hops)+" hops away, received via "+RNS.prettyhexrep(packet.transport_id)+" on "+str(packet.receiving_interface)+signal_str, RNS.LOG_EXTREME)
                        else:
                            RNS.log("Valid announce for "+RNS.prettyhexrep(destination_hash)+" "+str(packet.hops)+" hops away, received on "+str(packet.receiving_interface)+signal_str, RNS.LOG_EXTREME)

                        if ratchet:
                            Identity._remember_ratchet(destination_hash, ratchet)

                        return True

                    else:
                        RNS.log("Received invalid announce for "+RNS.prettyhexrep(destination_hash)+": Destination mismatch.", RNS.LOG_DEBUG)
                        return False

                else:
                    RNS.log("Received invalid announce for "+RNS.prettyhexrep(destination_hash)+": Invalid signature.", RNS.LOG_DEBUG)
                    del announced_identity
                    return False
        
        except Exception as e:
            RNS.log("Error occurred while validating announce. The contained exception was: "+str(e), RNS.LOG_ERROR)
            return False

    @staticmethod
    def persist_data():
        if not RNS.Transport.owner.is_connected_to_shared_instance:
            Identity.save_known_destinations()

    @staticmethod
    def exit_handler():
        Identity.persist_data()


    @staticmethod
    def from_bytes(prv_bytes):
        """
        Create a new :ref:`RNS.Identity<api-identity>` instance from *bytes* of private key.
        Can be used to load previously created and saved identities into Reticulum.

        :param prv_bytes: The *bytes* of private a saved private key. **HAZARD!** Never use this to generate a new key by feeding random data in prv_bytes.
        :returns: A :ref:`RNS.Identity<api-identity>` instance, or *None* if the *bytes* data was invalid.
        """
        identity = Identity(create_keys=False)
        if identity.load_private_key(prv_bytes):
            return identity
        else:
            return None


    @staticmethod
    def from_file(path):
        """
        Create a new :ref:`RNS.Identity<api-identity>` instance from a file.
        Can be used to load previously created and saved identities into Reticulum.

        :param path: The full path to the saved :ref:`RNS.Identity<api-identity>` data
        :returns: A :ref:`RNS.Identity<api-identity>` instance, or *None* if the loaded data was invalid.
        """
        identity = Identity(create_keys=False)
        if identity.load(path):
            return identity
        else:
            return None

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
                key_file.write(self.get_private_key())
                return True
            return False
        except Exception as e:
            RNS.log("Error while saving identity to "+str(path), RNS.LOG_ERROR)
            RNS.log("The contained exception was: "+str(e))

    def __init__(self,create_keys=True):
        # Initialize keys to none
        self.prv           = None
        self.prv_bytes     = None
        self.sig_prv       = None
        self.sig_prv_bytes = None

        self.pub           = None
        self.pub_bytes     = None
        self.sig_pub       = None
        self.sig_pub_bytes = None

        self.hash          = None
        self.hexhash       = None

        if create_keys:
            self.create_keys()

    def create_keys(self):
        self.prv           = X25519PrivateKey.generate()
        self.prv_bytes     = self.prv.private_bytes()

        self.sig_prv       = Ed25519PrivateKey.generate()
        self.sig_prv_bytes = self.sig_prv.private_bytes()

        self.pub           = self.prv.public_key()
        self.pub_bytes     = self.pub.public_bytes()

        self.sig_pub       = self.sig_prv.public_key()
        self.sig_pub_bytes = self.sig_pub.public_bytes()

        self.update_hashes()

        RNS.log("Identity keys created for "+RNS.prettyhexrep(self.hash), RNS.LOG_VERBOSE)

    def get_private_key(self):
        """
        :returns: The private key as *bytes*
        """
        return self.prv_bytes+self.sig_prv_bytes

    def get_public_key(self):
        """
        :returns: The public key as *bytes*
        """
        return self.pub_bytes+self.sig_pub_bytes

    def load_private_key(self, prv_bytes):
        """
        Load a private key into the instance.

        :param prv_bytes: The private key as *bytes*.
        :returns: True if the key was loaded, otherwise False.
        """
        try:
            self.prv_bytes     = prv_bytes[:Identity.KEYSIZE//8//2]
            self.prv           = X25519PrivateKey.from_private_bytes(self.prv_bytes)
            self.sig_prv_bytes = prv_bytes[Identity.KEYSIZE//8//2:]
            self.sig_prv       = Ed25519PrivateKey.from_private_bytes(self.sig_prv_bytes)
            
            self.pub           = self.prv.public_key()
            self.pub_bytes     = self.pub.public_bytes()

            self.sig_pub       = self.sig_prv.public_key()
            self.sig_pub_bytes = self.sig_pub.public_bytes()

            self.update_hashes()

            return True

        except Exception as e:
            raise e
            RNS.log("Failed to load identity key", RNS.LOG_ERROR)
            RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)
            return False

    def load_public_key(self, pub_bytes):
        """
        Load a public key into the instance.

        :param pub_bytes: The public key as *bytes*.
        :returns: True if the key was loaded, otherwise False.
        """
        try:
            self.pub_bytes     = pub_bytes[:Identity.KEYSIZE//8//2]
            self.sig_pub_bytes = pub_bytes[Identity.KEYSIZE//8//2:]

            self.pub           = X25519PublicKey.from_public_bytes(self.pub_bytes)
            self.sig_pub       = Ed25519PublicKey.from_public_bytes(self.sig_pub_bytes)

            self.update_hashes()
        except Exception as e:
            RNS.log("Error while loading public key, the contained exception was: "+str(e), RNS.LOG_ERROR)

    def update_hashes(self):
        self.hash = Identity.truncated_hash(self.get_public_key())
        self.hexhash = self.hash.hex()

    def load(self, path):
        try:
            with open(path, "rb") as key_file:
                prv_bytes = key_file.read()
                return self.load_private_key(prv_bytes)
            return False
        except Exception as e:
            RNS.log("Error while loading identity from "+str(path), RNS.LOG_ERROR)
            RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)

    def get_salt(self):
        return self.hash

    def get_context(self):
        return None

    def encrypt(self, plaintext, ratchet=None):
        """
        Encrypts information for the identity.

        :param plaintext: The plaintext to be encrypted as *bytes*.
        :returns: Ciphertext token as *bytes*.
        :raises: *KeyError* if the instance does not hold a public key.
        """
        if self.pub != None:
            ephemeral_key = X25519PrivateKey.generate()
            ephemeral_pub_bytes = ephemeral_key.public_key().public_bytes()

            if ratchet != None:
                target_public_key = X25519PublicKey.from_public_bytes(ratchet)
            else:
                target_public_key = self.pub

            shared_key = ephemeral_key.exchange(target_public_key)
            
            derived_key = RNS.Cryptography.hkdf(
                length=32,
                derive_from=shared_key,
                salt=self.get_salt(),
                context=self.get_context(),
            )

            fernet = Fernet(derived_key)
            ciphertext = fernet.encrypt(plaintext)
            token = ephemeral_pub_bytes+ciphertext

            return token
        else:
            raise KeyError("Encryption failed because identity does not hold a public key")


    def decrypt(self, ciphertext_token, ratchets=None, enforce_ratchets=False, ratchet_id_receiver=None):
        """
        Decrypts information for the identity.

        :param ciphertext: The ciphertext to be decrypted as *bytes*.
        :returns: Plaintext as *bytes*, or *None* if decryption fails.
        :raises: *KeyError* if the instance does not hold a private key.
        """
        if self.prv != None:
            if len(ciphertext_token) > Identity.KEYSIZE//8//2:
                plaintext = None
                try:
                    peer_pub_bytes = ciphertext_token[:Identity.KEYSIZE//8//2]
                    peer_pub = X25519PublicKey.from_public_bytes(peer_pub_bytes)
                    ciphertext = ciphertext_token[Identity.KEYSIZE//8//2:]

                    if ratchets:
                        for ratchet in ratchets:
                            try:
                                ratchet_prv = X25519PrivateKey.from_private_bytes(ratchet)
                                ratchet_id = Identity._get_ratchet_id(ratchet_prv.public_key().public_bytes())
                                shared_key = ratchet_prv.exchange(peer_pub)
                                derived_key = RNS.Cryptography.hkdf(
                                    length=32,
                                    derive_from=shared_key,
                                    salt=self.get_salt(),
                                    context=self.get_context(),
                                )

                                fernet = Fernet(derived_key)
                                plaintext = fernet.decrypt(ciphertext)
                                if ratchet_id_receiver:
                                    ratchet_id_receiver.latest_ratchet_id = ratchet_id
                                
                                break
                            
                            except Exception as e:
                                pass

                    if enforce_ratchets and plaintext == None:
                        RNS.log("Decryption with ratchet enforcement by "+RNS.prettyhexrep(self.hash)+" failed. Dropping packet.", RNS.LOG_DEBUG)
                        if ratchet_id_receiver:
                            ratchet_id_receiver.latest_ratchet_id = None
                        return None

                    if plaintext == None:
                        shared_key = self.prv.exchange(peer_pub)
                        derived_key = RNS.Cryptography.hkdf(
                            length=32,
                            derive_from=shared_key,
                            salt=self.get_salt(),
                            context=self.get_context(),
                        )

                        fernet = Fernet(derived_key)
                        plaintext = fernet.decrypt(ciphertext)
                        if ratchet_id_receiver:
                            ratchet_id_receiver.latest_ratchet_id = None

                except Exception as e:
                    RNS.log("Decryption by "+RNS.prettyhexrep(self.hash)+" failed: "+str(e), RNS.LOG_DEBUG)
                    if ratchet_id_receiver:
                        ratchet_id_receiver.latest_ratchet_id = None
                    
                return plaintext;
            else:
                RNS.log("Decryption failed because the token size was invalid.", RNS.LOG_DEBUG)
                return None
        else:
            raise KeyError("Decryption failed because identity does not hold a private key")


    def sign(self, message):
        """
        Signs information by the identity.

        :param message: The message to be signed as *bytes*.
        :returns: Signature as *bytes*.
        :raises: *KeyError* if the instance does not hold a private key.
        """
        if self.sig_prv != None:
            try:
                return self.sig_prv.sign(message)    
            except Exception as e:
                RNS.log("The identity "+str(self)+" could not sign the requested message. The contained exception was: "+str(e), RNS.LOG_ERROR)
                raise e
        else:
            raise KeyError("Signing failed because identity does not hold a private key")

    def validate(self, signature, message):
        """
        Validates the signature of a signed message.

        :param signature: The signature to be validated as *bytes*.
        :param message: The message to be validated as *bytes*.
        :returns: True if the signature is valid, otherwise False.
        :raises: *KeyError* if the instance does not hold a public key.
        """
        if self.pub != None:
            try:
                self.sig_pub.verify(signature, message)
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
