# Reticulum License
#
# Copyright (c) 2016-2026 Mark Qvist
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# - The Software shall not be used in any kind of system which includes amongst
#   its functions the ability to purposefully do harm to human beings.
#
# - The Software shall not be used, directly or indirectly, in the creation of
#   an artificial intelligence, machine learning or language model training
#   dataset, including but not limited to any use that contributes to the
#   training or development of such a model or algorithm.
#
# - The above copyright notice and this permission notice shall be included in
#   all copies or substantial portions of the Software.
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
from RNS.Cryptography import Token
from RNS.Storage import KnownDestinationsStore
from RNS.Stamps import stamp_workblock, stamp_valid, stamp_value, generate_stamped_key
from RNS.Stamps import cost_from_bytes, quantize_cost


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
    TOKEN_OVERHEAD            = RNS.Cryptography.Token.TOKEN_OVERHEAD
    AES128_BLOCKSIZE          = 16          # In bytes
    AES256_BLOCKSIZE          = 16          # In bytes
    HASHLENGTH                = 256         # In bits
    NAME_HASH_LENGTH          = 80          # In bits
    SIGLENGTH                 = KEYSIZE     # In bits
    STAMPLENGTH               = 14          # In bytes
    EXTHEADERLENGTH           = 2           # In bytes
    LRCOSTLENGTH              = 2           # In bytes
    EXTPAYLOADLENGTH          = EXTHEADERLENGTH+STAMPLENGTH+LRCOSTLENGTH
    EXTPAYLOADMARKER          = 0xC1 # Never used at msgpack object boundaries

    TRUNCATED_HASHLENGTH      = RNS.Reticulum.TRUNCATED_HASHLENGTH
    """
    Constant specifying the truncated hash length (in bits) used by Reticulum
    for addressable hashes and other purposes. Non-configurable.
    """

    DERIVED_KEY_LENGTH        = 512//8

    # Storage
    known_destinations = {}
    known_destinations_store = None
    known_ratchets = {}

    ratchet_persist_lock = threading.Lock()
    known_destinations_lock = threading.Lock()

    @staticmethod
    def remember(packet_hash, destination_hash, public_key, app_data=None, stamp=None, stamp_value=0, lr_cost=None):
        if stamp_value == None: stamp_value = 0
        if len(public_key) != Identity.KEYSIZE//8: raise TypeError(f"Can't remember {RNS.prettyhexrep(destination_hash)}, the public key size of {len(public_key)} is not valid.", RNS.LOG_ERROR)
        else:
            with Identity.known_destinations_lock:
                if not destination_hash in Identity.known_destinations:
                    Identity.known_destinations[destination_hash] = [time.time(), packet_hash, public_key, app_data, 0, stamp, stamp_value, lr_cost]
                else:
                    entry = Identity.known_destinations[destination_hash]
                    entry[0] = time.time()
                    entry[1] = packet_hash
                    entry[2] = public_key
                    entry[3] = app_data
                    entry[5] = stamp
                    entry[6] = stamp_value
                    entry[7] = lr_cost

                Identity._kd_mark_dirty(destination_hash)

    @staticmethod
    def recall(target_hash, from_identity_hash=False, _no_use=False):
        """
        Recall identity for a destination or identity hash. By default, this function
        will return the identity associated with a given *destination* hash. As an
        example, if you know the ``lxmf.delivery`` destination hash of an endpoint,
        this function will return the associated underlying identity. You can also
        search for an identity from a known *identity hash*, by setting the
        ``from_identity_hash`` argument.

        :param target_hash: Destination or identity hash as *bytes*.
        :param from_identity_hash: Whether to search based on identity hash instead of destination hash as *bool*.
        :returns: An :ref:`RNS.Identity<api-identity>` instance that can be used to create an outgoing :ref:`RNS.Destination<api-destination>`, or *None* if the destination is unknown.
        """
        if from_identity_hash:
            with Identity.known_destinations_lock: destination_hashes = list(Identity.known_destinations.keys())
            for destination_hash in destination_hashes:
                entry = Identity.known_destinations.get(destination_hash)
                if not entry: continue
                if target_hash == Identity.truncated_hash(entry[2]):
                    if not _no_use: RNS.Reticulum.get_instance()._used_destination_data(destination_hash)
                    identity = Identity(create_keys=False)
                    identity.load_public_key(entry[2])
                    identity.app_data = entry[3]
                    return identity

            return None

        else:
            if target_hash in Identity.known_destinations:
                if not _no_use: RNS.Reticulum.get_instance()._used_destination_data(target_hash)
                identity_data = Identity.known_destinations[target_hash]
                identity = Identity(create_keys=False)
                identity.load_public_key(identity_data[2])
                identity.app_data = identity_data[3]
                return identity
            else:
                for registered_destination in RNS.Transport.destinations:
                    if target_hash == registered_destination.hash:
                        identity = Identity(create_keys=False)
                        identity.load_public_key(registered_destination.identity.get_public_key())
                        identity.app_data = None
                        return identity

                return None

    @staticmethod
    def recall_app_data(destination_hash, _no_use=False):
        """
        Recall last heard app_data for a destination hash.

        :param destination_hash: Destination hash as *bytes*.
        :returns: *Bytes* containing app_data, or *None* if the destination is unknown.
        """
        if destination_hash in Identity.known_destinations:
            if not _no_use: RNS.Reticulum.get_instance()._used_destination_data(destination_hash)
            app_data = Identity.known_destinations[destination_hash][3]
            return app_data
        
        else: return None

    @staticmethod
    def recall_stamp_value(destination_hash):
        """
        Recall last heard announce stamp value for a destination hash.

        :param destination_hash: Destination hash as *bytes*.
        :returns: *Float*, or *None* if the destination is unknown.
        """
        known_destination = Identity.known_destinations.get(destination_hash)
        if not known_destination: return None
        else:                     return known_destination[6]

    @staticmethod
    def recall_link_cost(destination_hash):
        """
        Recall the link request stamp cost announced by a destination.

        :param destination_hash: Destination hash as *bytes*.
        :returns: *Float*, or *None* if the destination is unknown or has not announced a cost.
        """
        known_destination = Identity.known_destinations.get(destination_hash)
        if not known_destination: return None
        else:                     return known_destination[7]

    @staticmethod
    def save_known_destinations(background=False, recombine=False):
        if recombine: RNS.log(f"Recombining known destinations from disk cache on persist is deprecated, argument ignored", RNS.LOG_WARNING)
        if RNS.Transport.owner.is_connected_to_shared_instance: return

        if Identity.known_destinations_store != None: Identity.flush_known_destinations()
        else: Identity.save_known_destinations_legacy(background=background)

    @staticmethod
    def save_known_destinations_legacy(background=False):
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
            RNS.log("Saving "+str(len(Identity.known_destinations))+" known destinations to storage...", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None

            temp_file = RNS.Reticulum.storagepath+f"/known_destinations.tmp.{time.time()}"
            try:
                with open(temp_file,"wb") as file: umsgpack.dump(Identity.known_destinations.copy(), file)
                os.replace(temp_file, RNS.Reticulum.storagepath+f"/known_destinations")

            except Exception as e:
                RNS.log(f"Error while serializing and writing known destinations: {e}", RNS.LOG_ERROR)
                try: os.unlink(temp_file)
                except Exception as exc: RNS.log(f"Could not clean up temporary file {temp_file}: {exc}", RNS.LOG_WARNING)
                raise e

            RNS.log(f"Saved known destinations to storage in {RNS.prettyshorttime(time.time()-save_start)}", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None

        except Exception as e:
            RNS.log("Error while saving known destinations to disk, the contained exception was: "+str(e), RNS.LOG_ERROR)
            RNS.trace_exception(e)

        finally: Identity.saving_known_destinations = False

    @staticmethod
    def load_known_destinations():
        if RNS.Reticulum.get_instance().is_connected_to_shared_instance:
            try:
                store = KnownDestinationsStore(RNS.Reticulum.storagepath+"/known_destinations.db", hash_width=RNS.Reticulum.TRUNCATED_HASHLENGTH//8, read_only=True)
                count = 0
                with Identity.known_destinations_lock:
                    for destination_hash, entry in store.load_all():
                        Identity.known_destinations[destination_hash] = entry
                        count += 1

                store.close()
                RNS.log(f"Loaded {count} known destinations from shared instance database", RNS.LOG_VERBOSE)

            except Exception as e:
                with Identity.known_destinations_lock: Identity.known_destinations = {}
                RNS.log("Could not load known destinations from shared instance database, continuing with an empty table. The contained exception was: "+str(e), RNS.LOG_ERROR)

            return

        store = None
        try: store = KnownDestinationsStore(RNS.Reticulum.storagepath+"/known_destinations.db", hash_width=RNS.Reticulum.TRUNCATED_HASHLENGTH//8)
        except Exception as e:
            RNS.log("Could not initialise known destinations database, falling back to legacy snapshot persistence. The contained exception was: "+str(e), RNS.LOG_ERROR)
            Identity.known_destinations_store = None

        if store != None:
            Identity.known_destinations_store = store

            legacy_path = RNS.Reticulum.storagepath+"/known_destinations"
            if os.path.isfile(legacy_path):
                try:
                    imported = store.import_legacy(legacy_path)
                    os.rename(legacy_path, legacy_path+".imported")
                    RNS.log(f"Imported {imported} known destinations from legacy storage into the known destinations database", RNS.LOG_VERBOSE)

                except Exception as e:
                    RNS.log("Could not import legacy known destinations file into the known destinations database. The contained exception was: "+str(e), RNS.LOG_ERROR)
                    RNS.trace_exception(e)

            st = time.time()
            try:
                count = 0
                with Identity.known_destinations_lock:
                    for destination_hash, entry in store.load_all():
                        Identity.known_destinations[destination_hash] = entry
                        count += 1

                RNS.log(f"Loaded {count} known destinations from storage in {RNS.prettyshorttime(time.time()-st)}", RNS.LOG_VERBOSE)

            except Exception as e:
                RNS.log("Error loading known destinations from storage, continuing with an empty table", RNS.LOG_ERROR)
                RNS.trace_exception(e)

            ratchetdir = RNS.Reticulum.storagepath+"/ratchets"
            if os.path.isdir(ratchetdir) and len(os.listdir(ratchetdir)) > 0:
                try:
                    imported = store.import_legacy_ratchets(ratchetdir, time.time()-Identity.RATCHET_EXPIRY, Identity.known_destinations)
                    RNS.log(f"Imported {imported} ratchets from legacy file storage", RNS.LOG_VERBOSE)

                except Exception as e:
                    RNS.log(f"Could not import legacy ratchet files into the known destinations database. The contained exception was: {e}", RNS.LOG_ERROR)
                    RNS.trace_exception(e)

        else: Identity.load_known_destinations_legacy()

    @staticmethod
    def load_known_destinations_legacy():
        if os.path.isfile(RNS.Reticulum.storagepath+"/known_destinations"):
            st = time.time()
            try:
                with open(RNS.Reticulum.storagepath+"/known_destinations","rb") as file:
                    loaded_known_destinations = umsgpack.load(file)

                Identity.known_destinations = {}
                for known_destination in loaded_known_destinations:
                    if len(known_destination) == RNS.Reticulum.TRUNCATED_HASHLENGTH//8:
                        if len(loaded_known_destinations[known_destination]) < 5:
                            e = loaded_known_destinations[known_destination]
                            loaded_known_destinations[known_destination] = [e[0], e[1], e[2], e[3], 0, None, 0, None]
                        elif len(loaded_known_destinations[known_destination]) < 8:
                            e = loaded_known_destinations[known_destination]
                            while len(e) < 8: e.append(None if len(e) in (5, 7) else 0)
                            loaded_known_destinations[known_destination] = e

                        with Identity.known_destinations_lock:
                            Identity.known_destinations[known_destination] = loaded_known_destinations[known_destination]

                RNS.log(f"Loaded {len(Identity.known_destinations)} known destination from storage in {RNS.prettyshorttime(time.time()-st)}", RNS.LOG_VERBOSE)

            except Exception as e:
                RNS.log("Error loading known destinations from disk, file will be recreated on exit", RNS.LOG_ERROR)
                RNS.trace_exception(e)
        else:
            RNS.log("Destinations file does not exist, no known destinations loaded", RNS.LOG_VERBOSE)

    @staticmethod
    def _used_destination_data(destination_hash):
        with Identity.known_destinations_lock:
            if destination_hash in Identity.known_destinations:
                if not Identity.known_destinations[destination_hash][4] < 0:
                    Identity.known_destinations[destination_hash][4] = time.time()
                    Identity._kd_mark_dirty(destination_hash)
                    return True

        return False

    @staticmethod
    def _retain_destination_data(destination_hash):
        with Identity.known_destinations_lock:
            if destination_hash in Identity.known_destinations:
                Identity.known_destinations[destination_hash][4] = -1
                Identity._kd_mark_dirty(destination_hash)
                return True

        return False

    @staticmethod
    def _unretain_destination_data(destination_hash):
        with Identity.known_destinations_lock:
            if destination_hash in Identity.known_destinations:
                Identity.known_destinations[destination_hash][4] = time.time()
                Identity._kd_mark_dirty(destination_hash)
                return True

        return False

    @staticmethod
    def _retain_identity(identity_hash):
        try:
            retained = False
            with Identity.known_destinations_lock: destination_hashes = list(Identity.known_destinations.keys())
            for destination_hash in destination_hashes:
                entry = Identity.known_destinations.get(destination_hash)
                if not entry: continue
                if identity_hash == Identity.truncated_hash(entry[2]):
                    if Identity._retain_destination_data(destination_hash): retained = True

            return retained

        except Exception as e: RNS.log(f"Error while retaining identity {RNS.prettyhexrep(identity_hash)}: {e}", RNS.LOG_ERROR)
    
    @staticmethod
    def clean_known_destinations(background=False):
        now        = time.time()
        st         = now
        total      = len(Identity.known_destinations)
        stale      = []
        no_path    = 0
        retained   = 0
        never_used = 0
        ratchetdir = RNS.Reticulum.storagepath+"/ratchets"

        RNS.log(f"Cleaning known destinations{' at background priority' if background else ''}...", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None

        with Identity.known_destinations_lock: destination_hashes = list(Identity.known_destinations.keys())
        for destination_hash in destination_hashes:
            try:
                if background: time.sleep(0.001) # Low priority, yield thread
                RNS.Transport.destinations_last_cleaned = time.time()
                if RNS.Transport.has_path(destination_hash): has_path = True
                else:
                    has_path = False
                    no_path += 1

                with Identity.known_destinations_lock:
                    if destination_hash in Identity.known_destinations:
                        last_announce =  Identity.known_destinations[destination_hash][0]
                        last_use = 0
                        was_used = False
                        is_retained = False

                        if Identity.known_destinations[destination_hash][4] > 0:
                            was_used = True
                            last_use = Identity.known_destinations[destination_hash][4]

                        elif Identity.known_destinations[destination_hash][4] == 0:
                            was_used = False
                            never_used += 1

                        elif Identity.known_destinations[destination_hash][4] == -1:
                            is_retained = True
                            retained += 1

                        unused_for = time.time() - Identity.known_destinations[destination_hash][4]

                        if not is_retained and not has_path:
                            if not was_used and now - last_announce > RNS.Transport.UNUSED_DESTINATION_LINGER: stale.append(destination_hash)
                            elif unused_for > RNS.Transport.PATH_TIMEOUT*1.25:                                 stale.append(destination_hash)

            except Exception as e: RNS.log(f"Faulty entry for {RNS.prettyhexrep(destination_hash)} while cleaning known destinations: {e}", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None

        removed = 0
        for destination_hash in stale:
            with Identity.known_destinations_lock:
                if destination_hash in Identity.known_destinations:
                    Identity.known_destinations.pop(destination_hash)
                    Identity._kd_mark_deleted(destination_hash)
                    if destination_hash in Identity.known_ratchets: Identity.known_ratchets.pop(destination_hash)
                    removed += 1

            if not Identity.known_destinations_store:
                try:
                    hexhash = RNS.hexrep(destination_hash, delimit=False)
                    ratchet_path = f"{ratchetdir}/{hexhash}"
                    if os.path.isfile(ratchet_path): os.unlink(ratchet_path)
                except Exception as e: RNS.log(f"Could not clean stale ratchets for {RNS.prettyhexrep(destination_hash)}: {e}", RNS.LOG_WARNING)

        if Identity.known_destinations_store != None:
            expired_ratchets = Identity.known_destinations_store.expire_ratchets(time.time()-Identity.RATCHET_EXPIRY)
            if len(expired_ratchets) > 0:
                for destination_hash in expired_ratchets:
                    with Identity.known_destinations_lock:
                        if destination_hash in Identity.known_ratchets: Identity.known_ratchets.pop(destination_hash)

        RNS.log(f"Cleaned known destinations in {RNS.prettyshorttime(time.time()-st)}", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
        RNS.log(f"Total: {total}, stale: {len(stale)}, removed: {removed}, no path: {no_path}, never used: {never_used}, with path: {total-no_path}, used: {total-never_used}, retained: {retained}", RNS.LOG_PATHING) if RNS.sl(RNS.LOG_PATHING) else None
        if not RNS.Transport.owner.is_connected_to_shared_instance: Identity.save_known_destinations(recombine=False)

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
        try:
            # Don't re-insert existing ratchet
            if Identity.known_ratchets.get(destination_hash) == ratchet: return

            store = Identity.known_destinations_store
            if store != None:
                # Persist to store, only update in-memory cache if this
                # destination already exists there.
                store.remember_ratchet(destination_hash, ratchet, time.time())
                if destination_hash in Identity.known_ratchets:
                    Identity.known_ratchets[destination_hash] = ratchet

            # Legacy store: Use file system
            # Shared instance client: Just keep in memory cache
            else:
                ratchet_exists = destination_hash in Identity.known_ratchets and Identity.known_ratchets[destination_hash] == ratchet
                if not ratchet_exists:
                    RNS.log(f"Remembering ratchet {RNS.prettyhexrep(Identity._get_ratchet_id(ratchet))} for {RNS.prettyhexrep(destination_hash)}", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
                    Identity.known_ratchets[destination_hash] = ratchet
                    if not RNS.Transport.owner.is_connected_to_shared_instance:
                        def persist_job():
                            with Identity.ratchet_persist_lock:
                                hexhash = RNS.hexrep(destination_hash, delimit=False)
                                ratchet_data = {"ratchet": ratchet, "received": time.time()}

                                ratchetdir = RNS.Reticulum.storagepath+"/ratchets"

                                if not os.path.isdir(ratchetdir): os.makedirs(ratchetdir)

                                outpath   = f"{ratchetdir}/{hexhash}.out"
                                finalpath = f"{ratchetdir}/{hexhash}"
                                with open(outpath, "wb") as ratchet_file: ratchet_file.write(umsgpack.packb(ratchet_data))
                                os.replace(outpath, finalpath)

                        threading.Thread(target=persist_job, daemon=True).start()

        except Exception as e:
            RNS.log(f"Could not persist ratchet for {RNS.prettyhexrep(destination_hash)} to storage.", RNS.LOG_ERROR)
            RNS.log(f"The contained exception was: {e}")
            RNS.trace_exception(e)

    @staticmethod
    def _clean_ratchets():
        if Identity.known_destinations_store != None: return
        RNS.log("Cleaning ratchets...", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
        try:
            count = 0
            removed = 0
            not_known = 0
            now = time.time()
            ratchetdir = RNS.Reticulum.storagepath+"/ratchets"
            if os.path.isdir(ratchetdir):
                for filename in os.listdir(ratchetdir):
                    count += 1
                    try:
                        expired = False
                        corrupted = False
                        with open(f"{ratchetdir}/{filename}", "rb") as rf:
                            try:
                                ratchet_data = umsgpack.unpackb(rf.read())
                                if now > ratchet_data["received"]+Identity.RATCHET_EXPIRY: expired = True

                            except Exception as e:
                                RNS.log(f"Corrupted ratchet data while reading {ratchetdir}/{filename}, removing file", RNS.LOG_ERROR)
                                corrupted = True

                        destination_hash = bytes.fromhex(filename)
                        if not destination_hash in RNS.Identity.known_destinations: unknown = True; not_known += 1
                        else:                                                       unknown = False

                        if expired or corrupted or unknown:
                            os.unlink(f"{ratchetdir}/{filename}")
                            removed += 1

                    except Exception as e:
                        RNS.log(f"An error occurred while cleaning ratchets, in the processing of {ratchetdir}/{filename}.", RNS.LOG_ERROR)
                        RNS.log(f"The contained exception was: {e}", RNS.LOG_ERROR)

        except Exception as e: RNS.log(f"An error occurred while cleaning ratchets. The contained exception was: {e}", RNS.LOG_ERROR)
        RNS.log(f"Processed {count} ratchets in {RNS.prettytime(time.time()-now)}, not in use {not_known}, removed {removed}", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None

    @staticmethod
    def get_ratchet(destination_hash):
        if destination_hash in Identity.known_ratchets: return Identity.known_ratchets[destination_hash]

        store = Identity.known_destinations_store
        if store != None:
            ratchet_data = store.fetch_ratchet(destination_hash)
            if ratchet_data != None:
                ratchet, received = ratchet_data
                if time.time() < received+Identity.RATCHET_EXPIRY:
                    Identity.known_ratchets[destination_hash] = ratchet
                    return ratchet

                else: return None

            else:
                RNS.log(f"Could not load ratchet for {RNS.prettyhexrep(destination_hash)}", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
                return None

        elif RNS.Reticulum.get_instance().is_connected_to_shared_instance:
            try:
                # TODO: Ideally, refactor this to an RPC method instead
                store = KnownDestinationsStore(RNS.Reticulum.storagepath+"/known_destinations.db", hash_width=RNS.Reticulum.TRUNCATED_HASHLENGTH//8, read_only=True)
                ratchet_data = store.fetch_ratchet(destination_hash)
                store.close()

                if ratchet_data != None:
                    ratchet, received = ratchet_data
                    if time.time() < received+Identity.RATCHET_EXPIRY:
                        Identity.known_ratchets[destination_hash] = ratchet
                        return ratchet

            except Exception as e: RNS.log(f"Could not fetch ratchet for {RNS.prettyhexrep(destination_hash)} from shared instance database. The contained exception was: {e}", RNS.LOG_ERROR)

            return None

        else:
            if not os.path.isfile(RNS.Reticulum.storagepath+"/ratchets/"+RNS.hexrep(destination_hash, delimit=False)): return None

            ratchetdir = RNS.Reticulum.storagepath+"/ratchets"
            hexhash = RNS.hexrep(destination_hash, delimit=False)
            ratchet_path = f"{ratchetdir}/{hexhash}"
            if os.path.isfile(ratchet_path):
                try:
                    with open(ratchet_path, "rb") as ratchet_file:
                        ratchet_data = umsgpack.unpackb(ratchet_file.read())
                        if time.time() < ratchet_data["received"]+Identity.RATCHET_EXPIRY and len(ratchet_data["ratchet"]) == Identity.RATCHETSIZE//8:
                            Identity.known_ratchets[destination_hash] = ratchet_data["ratchet"]
                        else: return None

                except Exception as e:
                    RNS.log(f"An error occurred while loading ratchet data for {RNS.prettyhexrep(destination_hash)} from storage.", RNS.LOG_ERROR)
                    RNS.log(f"The contained exception was: {e}", RNS.LOG_ERROR)
                    return None

        if destination_hash in Identity.known_ratchets: return Identity.known_ratchets[destination_hash]
        else:
            RNS.log(f"Could not load ratchet for {RNS.prettyhexrep(destination_hash)}", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
            return None

    @staticmethod
    def _reset_validation_caches():
        Identity.announce_valid_cache   = {}
        Identity.announce_invalid_cache = {}

    __valid_cache_count = 0
    __valid_cache_max   = 128
    @staticmethod
    def __cache_valid_announce(result):
        Identity.__valid_cache_count += 1
        result["id"] = Identity.__valid_cache_count
        packet_hash = result["packet_hash"]
        if packet_hash and not packet_hash in Identity.announce_valid_cache:
            Identity.announce_valid_cache[packet_hash] = result

        Identity.announce_invalid_cache.pop(packet_hash, None)

        try:
            while len(Identity.announce_valid_cache) > Identity.__valid_cache_max:
                Identity.announce_valid_cache.pop(next(iter(Identity.announce_valid_cache)))
        except Exception as e: RNS.log(f"Error while culling announce validation cache: {e}", RNS.LOG_DEBUG)

        return True

    __invalid_cache_count = 0
    __invalid_cache_max   = 128
    @staticmethod
    def __cache_invalid_announce(packet, signal=None, stamp_value=None):
        Identity.__invalid_cache_count += 1
        result = (signal or False, stamp_value)
        if packet.packet_hash: Identity.announce_invalid_cache[packet.packet_hash] = result

        try:
            while len(Identity.announce_invalid_cache) > Identity.__invalid_cache_max:
                Identity.announce_invalid_cache.pop(next(iter(Identity.announce_invalid_cache)))
        except Exception as e: RNS.log(f"Error while culling announce invalidation cache: {e}", RNS.LOG_DEBUG)

        return result[0]

    @staticmethod
    def __finalize_av(r, cache_hit=False):
        # We are also re-persisting here on cache hit in the edge (but very possible) case
        # that a path was culled (for example because of interface teardown), and its
        # associated destination data was removed. Known destinations must always cover
        # what is in the path table, anything else is state inconsintency.
        if not cache_hit or not r["destination_hash"] in Identity.known_destinations:
            RNS.Identity.remember(r["packet_hash"], r["destination_hash"], r["public_key"], app_data=r["app_data"],
                                  stamp=r["stamp"], stamp_value=r["stamp_value"], lr_cost=r["lr_cost"])

            if r["ratchet"]: Identity._remember_ratchet(r["destination_hash"], r["ratchet"])

        valid_announce_loglevel = RNS.LOG_EXTREME # TODO: Reset to LOG_EXTREME
        if RNS.sl(valid_announce_loglevel):
            if r["rssi"] != None or r["snr"] != None:
                signal_str = " ["
                if r["rssi"] != None:
                    signal_str += "RSSI "+str(r["rssi"])+"dBm"
                    if r["snr"] != None: signal_str += ", "
                if r["snr"] != None: signal_str += "SNR "+str(r["snr"])+"dB"
                signal_str += "]"
            else: signal_str = ""

            via_str = f" via {RNS.prettyhexrep(r['transport_id'])}" if r["transport_id"] else ""
            val_str = f" (v:{RNS.prettycost(r['stamp_value'])})"
            RNS.log(f"Valid announce for {RNS.prettyhexrep(r['destination_hash'])}{val_str} {r['hops']} hops away, received{via_str} on {r['receiving_interface']}{signal_str}", valid_announce_loglevel)

        return True

    announce_valid_cache   = {}
    announce_invalid_cache = {}

    @staticmethod
    def validate_announce(packet, only_validate_signature=False, signal_blackholed=False, signal_stamp=False, required_value=None):
        # Check cached announce invalidations
        cached_invalidation = Identity.announce_invalid_cache.get(packet.packet_hash, None)
        if cached_invalidation:
            try:
                if cached_invalidation[0] != "invalid_stamp":
                    if   cached_invalidation[0] == "no_stamp":   return cached_invalidation[0] if signal_stamp else False
                    elif cached_invalidation[0] == "blackholed": return cached_invalidation[0] if signal_blackholed else False
                    else:                                        return False
                elif cached_invalidation[1] != None:
                    rcvd_value = quantize_cost(cached_invalidation[1])
                    if packet.receiving_interface: cost_target = packet.receiving_interface.destination_cost
                    else:                          cost_target = RNS.Transport.DESTINATION_COST
                    if quantize_cost(cost_target) > quantize_cost(rcvd_value): return "invalid_stamp" if signal_stamp else False
                    else: pass # Stamp value above target for this interface, allow re-validation
                else:
                    RNS.log(f"Incoherent state in cached announce invalidation, rejecting announce", RNS.LOG_WARNING)
                    return False

            except Exception as e:
                RNS.log(f"Error while processing cached invalid announce: {e}", RNS.LOG_DEBUG)
                return False

        # Check cached announce validations
        cached_validation = Identity.announce_valid_cache.get(packet.packet_hash, None)
        if cached_validation:
            try:
                if RNS.Transport.STAMPS_ENABLED and RNS.Transport.STAMPS_ENFORCED:
                    if required_value == None:
                        if packet.receiving_interface: cost_target = packet.receiving_interface.destination_cost
                        else:                          cost_target = RNS.Transport.DESTINATION_COST
                    else: cost_target = required_value

                    cached_stamp_value = cached_validation.get("stamp_value", None)
                    if cached_stamp_value == None: return "no_stamp" if signal_stamp else False
                    elif quantize_cost(cost_target) > quantize_cost(cached_stamp_value):
                        return "invalid_stamp" if signal_stamp else False

            except Exception as e:
                RNS.log(f"Error while processing cached valid announce: {e}", RNS.LOG_DEBUG)
                return False

            return Identity.__finalize_av(cached_validation, cache_hit=True)

        if required_value == None:
            if packet.receiving_interface: required_value = packet.receiving_interface.destination_cost
            else:                          required_value = RNS.Transport.DESTINATION_COST

        try:
            if packet.packet_type == RNS.Packet.ANNOUNCE:
                keysize       = Identity.KEYSIZE//8
                ratchetsize   = Identity.RATCHETSIZE//8
                name_hash_len = Identity.NAME_HASH_LENGTH//8
                sig_len       = Identity.SIGLENGTH//8
                destination_hash = packet.destination_hash

                # Get public key bytes from announce
                public_key = packet.data[:keysize]

                # Shared format structure
                ratchet     = b""
                name_hash   = packet.data[keysize:keysize+name_hash_len]
                random_hash = packet.data[keysize+name_hash_len:keysize+name_hash_len+10]

                # If the packet context flag is set,
                # this announce contains a new ratchet
                if packet.context_flag == RNS.Packet.FLAG_SET:
                    ratchet     = packet.data[keysize+name_hash_len+10:keysize+name_hash_len+10+ratchetsize]
                    signature   = packet.data[keysize+name_hash_len+10+ratchetsize:keysize+name_hash_len+10+ratchetsize+sig_len]
                    app_data    = b""
                    if len(packet.data) > keysize+name_hash_len+10+sig_len+ratchetsize:
                        app_data = packet.data[keysize+name_hash_len+10+sig_len+ratchetsize:]

                # If the packet context flag is not set,
                # this announce does not contain a ratchet
                else:
                    signature   = packet.data[keysize+name_hash_len+10:keysize+name_hash_len+10+sig_len]
                    app_data    = b""
                    if len(packet.data) > keysize+name_hash_len+10+sig_len:
                        app_data = packet.data[keysize+name_hash_len+10+sig_len:]

                signed_data = destination_hash+public_key+name_hash+random_hash+ratchet+app_data

                if not len(packet.data) > Identity.KEYSIZE//8+Identity.NAME_HASH_LENGTH//8+10+Identity.SIGLENGTH//8:
                    app_data = None

                stamp           = None
                dst_stamped     = None
                dst_value       = None
                stamp_validated = None
                dst_lr_cost     = None
                if RNS.Transport.STAMPS_ENABLED and app_data and len(app_data) >= Identity.EXTPAYLOADLENGTH:
                    ext_payload = app_data[-Identity.EXTPAYLOADLENGTH:]
                    ext_header  = ext_payload[:Identity.EXTHEADERLENGTH]
                    ext_flags   = ext_header[1] # Reserved for future extensions
                    ext_anchor  = ext_payload[-1]

                    # The ext_anchor carries the lr_cost integer part, and a
                    # reserved flag in the MSB. The fractional part of the
                    # lr_cost is stored in the immediately preceding byte.
                    ext_extended  = (ext_anchor & 0x80) != 0
                    ext_lr_cost_i = ext_anchor & 0x7F
                    ext_lr_cost_m = ext_payload[-2]
                    cost_bytes    = bytes([ext_lr_cost_i, ext_lr_cost_m])
                    ext_lr_cost   = cost_from_bytes(cost_bytes)
                    known_format  = (not ext_extended) and (ext_lr_cost <= RNS.Transport.STAMP_COST_CAP)

                    if (not ext_header[0] == Identity.EXTPAYLOADMARKER) or (not known_format): dst_stamped = False
                    else:
                        # RNS.log(f"Checking potential stamp in announce with app_data len {len(app_data)} for {RNS.prettyhexrep(destination_hash)}", RNS.LOG_DEBUG) # TODO: Remove after 1.6.1
                        dst_stamped = True
                        try:
                            stamp     = ext_payload[Identity.EXTHEADERLENGTH:Identity.EXTHEADERLENGTH+Identity.STAMPLENGTH]
                            material  = destination_hash+public_key+name_hash
                            wb        = stamp_workblock(material, expand_rounds=0)
                            valid     = stamp_valid(stamp, required_value, wb)
                            dst_value = stamp_value(wb, stamp)

                            if valid:
                                app_data = app_data[:-Identity.EXTPAYLOADLENGTH]
                                if not len(app_data): app_data = None
                                stamp_validated = True
                                dst_lr_cost     = ext_lr_cost

                        except Exception as e: RNS.log(f"Announce stamp parsing failed: {e}", RNS.LOG_ERROR)

                # TODO: Initial debug only, remove ######
                # if RNS.sl(RNS.LOG_DEBUG):
                #     if not dst_stamped: RNS.log(f"No stamp on announce from {RNS.prettyhexrep(destination_hash)}", RNS.LOG_DEBUG)
                #     else:
                #         if not stamp_validated: RNS.log(f"Invalid or insufficient-value stamp for {RNS.prettyhexrep(destination_hash)}", RNS.LOG_DEBUG)
                #         else:                   RNS.log(f"Valid stamp with value {dst_value} for {RNS.prettyhexrep(destination_hash)}", RNS.LOG_DEBUG)
                #########################################

                if RNS.Transport.STAMPS_ENABLED and RNS.Transport.STAMPS_ENFORCED:
                    if not dst_stamped:
                        if signal_stamp: return Identity.__cache_invalid_announce(packet, "no_stamp")
                        else:            return Identity.__cache_invalid_announce(packet)
                    elif not stamp_validated:
                        if signal_stamp: return Identity.__cache_invalid_announce(packet, "invalid_stamp", dst_value)
                        else:            return Identity.__cache_invalid_announce(packet)

                announced_identity = Identity(create_keys=False)
                announced_identity.load_public_key(public_key)

                if len(RNS.Transport.blackholed_identities) > 0:
                    if announced_identity.hash in RNS.Transport.blackholed_identities:
                        RNS.log(f"Invalidated and dropped announce from blackholed identity {RNS.prettyhexrep(announced_identity.hash)}", RNS.LOG_EXTREME) if RNS.sl(RNS.LOG_EXTREME) else None
                        if signal_blackholed: return Identity.__cache_invalid_announce(packet, "blackholed")
                        else:                 return Identity.__cache_invalid_announce(packet)

                if announced_identity.pub != None and (packet.announce_signature_validated or announced_identity.validate(signature, signed_data)):
                    packet.announce_signature_validated = True
                    if only_validate_signature:
                        del announced_identity
                        return True

                    hash_material = name_hash+announced_identity.hash
                    expected_hash = RNS.Identity.full_hash(hash_material)[:RNS.Reticulum.TRUNCATED_HASHLENGTH//8]
                    del announced_identity

                    if destination_hash == expected_hash:
                        # Check if we already have a public key for this destination
                        # and make sure the public key is not different.
                        if destination_hash in Identity.known_destinations:
                            if public_key != Identity.known_destinations[destination_hash][2]:
                                # In reality, this should never occur, but in the odd case
                                # that someone manages a hash collision, we reject the announce.
                                RNS.log("Received announce with valid signature and destination hash, but announced public key does not match already known public key.", RNS.LOG_CRITICAL)
                                RNS.log("This may indicate an attempt to modify network paths, or a random hash collision. The announce was rejected.", RNS.LOG_CRITICAL)
                                return Identity.__cache_invalid_announce(packet)

                        validation_result = { "packet_hash": packet.packet_hash, "destination_hash": destination_hash,
                                              "public_key": public_key, "ratchet": ratchet, "app_data": app_data, "stamp": stamp,
                                              "stamp_value": dst_value, "lr_cost": dst_lr_cost, "transport_id": packet.transport_id,
                                              "hops": packet.hops, "receiving_interface": str(packet.receiving_interface),
                                              "rssi": packet.rssi, "snr": packet.snr, "q": packet.q }

                        Identity.__finalize_av(validation_result)
                        return Identity.__cache_valid_announce(validation_result)

                    else:
                        RNS.log("Received invalid announce for "+RNS.prettyhexrep(destination_hash)+": Destination mismatch.", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
                        return Identity.__cache_invalid_announce(packet)

                else:
                    RNS.log("Received invalid announce for "+RNS.prettyhexrep(destination_hash)+": Invalid signature.", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
                    del announced_identity
                    return Identity.__cache_invalid_announce(packet)
        
        except Exception as e:
            RNS.log("Error occurred while validating announce. The contained exception was: "+str(e), RNS.LOG_ERROR)
            RNS.trace_exception(e) # TODO: Remove debug
            return False

    @staticmethod
    def persist_data(background=False):
        if not RNS.Transport.owner.is_connected_to_shared_instance:
            if Identity.known_destinations_store != None: Identity.flush_known_destinations()
            else: Identity.save_known_destinations_legacy(background=background)

    @staticmethod
    def flush_known_destinations():
        store = Identity.known_destinations_store
        if store == None: return False

        with Identity.known_destinations_lock: upserts, deletes, ratchet_upserts, ratchet_deletes = store.take_pending()

        try: return store.apply(upserts, deletes, ratchet_upserts, ratchet_deletes, Identity.known_destinations)
        except Exception as e:
            RNS.log(f"Could not flush known destinations to storage. The contained exception was: {e}", RNS.LOG_ERROR)
            return False

    @staticmethod
    def _kd_mark_dirty(destination_hash):
        store = Identity.known_destinations_store
        if store != None: store.mark_dirty(destination_hash)

    @staticmethod
    def _kd_mark_deleted(destination_hash):
        store = Identity.known_destinations_store
        if store != None:
            store.mark_deleted(destination_hash)
            store.mark_ratchet_deleted(destination_hash)

    @staticmethod
    def exit_handler(): Identity.persist_data()

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

    def pub_to_file(self, path):
        """
        Saves the public identity to a file.

        :param path: The full path specifying where to save the identity.
        :returns: True if the file was saved, otherwise False.
        """
        try:
            with open(path, "wb") as key_file:
                key_file.write(self.get_public_key())
                return True
            return False
        except Exception as e:
            RNS.log("Error while saving identity to "+str(path), RNS.LOG_ERROR)
            RNS.log("The contained exception was: "+str(e))

    def __init__(self, create_keys=True, value=None):
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
            self.create_keys(value=value)

    def create_keys(self, value=None):
        self.sig_prv       = Ed25519PrivateKey.generate()
        self.sig_pub       = self.sig_prv.public_key()
        self.sig_prv_bytes = self.sig_prv.private_bytes()
        self.sig_pub_bytes = self.sig_pub.public_bytes()

        if not value:
            self.prv       = X25519PrivateKey.generate()
            self.prv_bytes = self.prv.private_bytes()

        else:
            stamped_key, v = generate_stamped_key(material=self.sig_pub_bytes, stamp_cost=value)
            if not stamped_key: raise RuntimeError("Stamped identity key generation failed or was cancelled")

            stamped_prv    = stamped_key[0]
            self.prv       = X25519PrivateKey.from_private_bytes(stamped_prv)
            self.prv_bytes = self.prv.private_bytes()

            assert self.prv_bytes == stamped_prv
            assert self.prv.public_key().public_bytes() == stamped_key[1]

        self.pub           = self.prv.public_key()
        self.pub_bytes     = self.pub.public_bytes()

        self.update_hashes()

        RNS.log("Identity keys created for "+RNS.prettyhexrep(self.hash), RNS.LOG_VERBOSE)

    def get_value(self):
        """
        :returns: The stamp value of this identity as a *float*
        """
        if not self.get_public_key(): return None
        else:                         return stamp_value(self.sig_pub_bytes, self.pub_bytes)

    def get_private_key(self):
        """
        :returns: The private key as *bytes*
        """
        if self.prv_bytes and self.sig_prv_bytes: return self.prv_bytes+self.sig_prv_bytes
        else:                                     return None

    def get_public_key(self):
        """
        :returns: The public key as *bytes*
        """
        if self.pub_bytes and self.sig_pub_bytes: return self.pub_bytes+self.sig_pub_bytes
        else:                                     return None

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
            RNS.log(f"Failed to load identity key, the contained exception was: {e}", RNS.LOG_ERROR)
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

            return True

        except Exception as e:
            RNS.log(f"Error while loading public key, the contained exception was: {e}", RNS.LOG_ERROR)
            return False

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
                length=Identity.DERIVED_KEY_LENGTH,
                derive_from=shared_key,
                salt=self.get_salt(),
                context=self.get_context(),
            )

            token = Token(derived_key)
            ciphertext = token.encrypt(plaintext)
            token = ephemeral_pub_bytes+ciphertext

            return token
        else:
            raise KeyError("Encryption failed because identity does not hold a public key")

    def __decrypt(self, shared_key, ciphertext):
        derived_key = RNS.Cryptography.hkdf(
            length=Identity.DERIVED_KEY_LENGTH,
            derive_from=shared_key,
            salt=self.get_salt(),
            context=self.get_context())

        token = Token(derived_key)
        plaintext = token.decrypt(ciphertext)
        return plaintext

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
                                plaintext = self.__decrypt(shared_key, ciphertext)
                                if ratchet_id_receiver:
                                    ratchet_id_receiver.latest_ratchet_id = ratchet_id
                                
                                break
                            
                            except Exception as e:
                                pass

                    if enforce_ratchets and plaintext == None:
                        RNS.log("Decryption with ratchet enforcement by "+RNS.prettyhexrep(self.hash)+" failed. Dropping packet.", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
                        if ratchet_id_receiver:
                            ratchet_id_receiver.latest_ratchet_id = None
                        return None

                    if plaintext == None:
                        shared_key = self.prv.exchange(peer_pub)
                        plaintext = self.__decrypt(shared_key, ciphertext)

                        if ratchet_id_receiver:
                            ratchet_id_receiver.latest_ratchet_id = None

                except Exception as e:
                    RNS.log("Decryption by "+RNS.prettyhexrep(self.hash)+" failed: "+str(e), RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
                    if ratchet_id_receiver:
                        ratchet_id_receiver.latest_ratchet_id = None
                    
                return plaintext
            
            else:
                RNS.log("Decryption failed because the token size was invalid.", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
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
