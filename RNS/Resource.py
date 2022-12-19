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

import RNS
import os
import bz2
import math
import time
import threading
from .vendor import umsgpack as umsgpack
from time import sleep

class Resource:
    """
    The Resource class allows transferring arbitrary amounts
    of data over a link. It will automatically handle sequencing,
    compression, coordination and checksumming.

    :param data: The data to be transferred. Can be *bytes* or an open *file handle*. See the :ref:`Filetransfer Example<example-filetransfer>` for details.
    :param link: The :ref:`RNS.Link<api-link>` instance on which to transfer the data.
    :param advertise: Optional. Whether to automatically advertise the resource. Can be *True* or *False*.
    :param auto_compress: Optional. Whether to auto-compress the resource. Can be *True* or *False*.
    :param callback: An optional *callable* with the signature *callback(resource)*. Will be called when the resource transfer concludes.
    :param progress_callback: An optional *callable* with the signature *callback(resource)*. Will be called whenever the resource transfer progress is updated.
    """

    # The initial window size at beginning of transfer
    WINDOW               = 4

    # Absolute minimum window size during transfer
    WINDOW_MIN           = 1

    # The maximum window size for transfers on slow links
    WINDOW_MAX_SLOW      = 10

    # The maximum window size for transfers on fast links
    WINDOW_MAX_FAST      = 75
    
    # For calculating maps and guard segments, this
    # must be set to the global maximum window.
    WINDOW_MAX           = WINDOW_MAX_FAST
    
    # If the fast rate is sustained for this many request
    # rounds, the fast link window size will be allowed.
    FAST_RATE_THRESHOLD  = WINDOW_MAX_SLOW - WINDOW - 2

    # If the RTT rate is higher than this value,
    # the max window size for fast links will be used.
    # The default is 50 Kbps (the value is stored in
    # bytes per second, hence the "/ 8").
    RATE_FAST            = (50*1000) / 8

    # The minimum allowed flexibility of the window size.
    # The difference between window_max and window_min
    # will never be smaller than this value.
    WINDOW_FLEXIBILITY   = 4

    # Number of bytes in a map hash
    MAPHASH_LEN          = 4
    SDU                  = RNS.Packet.MDU
    RANDOM_HASH_SIZE     = 4

    # This is an indication of what the
    # maximum size a resource should be, if
    # it is to be handled within reasonable
    # time constraint, even on small systems.
    #
    # A small system in this regard is
    # defined as a Raspberry Pi, which should
    # be able to compress, encrypt and hash-map
    # the resource in about 10 seconds.
    #
    # This constant will be used when determining
    # how to sequence the sending of large resources.
    #
    # Capped at 16777215 (0xFFFFFF) per segment to
    # fit in 3 bytes in resource advertisements.
    MAX_EFFICIENT_SIZE      = 16 * 1024 * 1024 - 1
    RESPONSE_MAX_GRACE_TIME = 10
    
    # The maximum size to auto-compress with
    # bz2 before sending.
    AUTO_COMPRESS_MAX_SIZE = MAX_EFFICIENT_SIZE

    PART_TIMEOUT_FACTOR           = 4
    PART_TIMEOUT_FACTOR_AFTER_RTT = 2
    MAX_RETRIES                   = 8
    MAX_ADV_RETRIES               = 4
    SENDER_GRACE_TIME             = 10
    RETRY_GRACE_TIME              = 0.25
    PER_RETRY_DELAY               = 0.5

    WATCHDOG_MAX_SLEEP            = 1

    HASHMAP_IS_NOT_EXHAUSTED = 0x00
    HASHMAP_IS_EXHAUSTED = 0xFF

    # Status constants
    NONE            = 0x00
    QUEUED          = 0x01
    ADVERTISED      = 0x02
    TRANSFERRING    = 0x03
    AWAITING_PROOF  = 0x04
    ASSEMBLING      = 0x05
    COMPLETE        = 0x06
    FAILED          = 0x07
    CORRUPT         = 0x08

    @staticmethod
    def accept(advertisement_packet, callback=None, progress_callback = None, request_id = None):
        try:
            adv = ResourceAdvertisement.unpack(advertisement_packet.plaintext)

            resource = Resource(None, advertisement_packet.link, request_id = request_id)
            resource.status = Resource.TRANSFERRING

            resource.flags               = adv.f
            resource.size                = adv.t
            resource.total_size          = adv.d
            resource.uncompressed_size   = adv.d
            resource.hash                = adv.h
            resource.original_hash       = adv.o
            resource.random_hash         = adv.r
            resource.hashmap_raw         = adv.m
            resource.encrypted           = True if resource.flags & 0x01 else False
            resource.compressed          = True if resource.flags >> 1 & 0x01 else False
            resource.initiator           = False
            resource.callback             = callback
            resource.__progress_callback = progress_callback
            resource.total_parts         = int(math.ceil(resource.size/float(Resource.SDU)))
            resource.received_count      = 0
            resource.outstanding_parts   = 0
            resource.parts                 = [None] * resource.total_parts
            resource.window              = Resource.WINDOW
            resource.window_max          = Resource.WINDOW_MAX_SLOW
            resource.window_min          = Resource.WINDOW_MIN
            resource.window_flexibility  = Resource.WINDOW_FLEXIBILITY
            resource.last_activity       = time.time()

            resource.storagepath         = RNS.Reticulum.resourcepath+"/"+resource.original_hash.hex()
            resource.segment_index       = adv.i
            resource.total_segments      = adv.l
            if adv.l > 1:
                resource.split = True
            else:
                resource.split = False

            resource.hashmap = [None] * resource.total_parts
            resource.hashmap_height = 0
            resource.waiting_for_hmu = False

            resource.receiving_part = False

            resource.consecutive_completed_height = 0
            
            if not resource.link.has_incoming_resource(resource):
                resource.link.register_incoming_resource(resource)

                RNS.log("Accepting resource advertisement for "+RNS.prettyhexrep(resource.hash), RNS.LOG_DEBUG)
                if resource.link.callbacks.resource_started != None:
                    try:
                        resource.link.callbacks.resource_started(resource)
                    except Exception as e:
                        RNS.log("Error while executing resource started callback from "+str(resource)+". The contained exception was: "+str(e), RNS.LOG_ERROR)

                resource.hashmap_update(0, resource.hashmap_raw)

                resource.watchdog_job()

                return resource

            else:
                RNS.log("Ignoring resource advertisement for "+RNS.prettyhexrep(resource.hash)+", resource already transferring", RNS.LOG_DEBUG)
                return None

        except Exception as e:
            RNS.log("Could not decode resource advertisement, dropping resource", RNS.LOG_DEBUG)
            return None

    # Create a resource for transmission to a remote destination
    # The data passed can be either a bytes-array or a file opened
    # in binary read mode.
    def __init__(self, data, link, advertise=True, auto_compress=True, callback=None, progress_callback=None, timeout = None, segment_index = 1, original_hash = None, request_id = None, is_response = False):
        data_size = None
        resource_data = None
        self.assembly_lock = False

        if hasattr(data, "read"):
            data_size = os.stat(data.name).st_size
            self.total_size  = data_size
            self.grand_total_parts = math.ceil(data_size/Resource.SDU)

            if data_size <= Resource.MAX_EFFICIENT_SIZE:
                self.total_segments = 1
                self.segment_index  = 1
                self.split          = False
                resource_data = data.read()
                data.close()
            else:
                self.total_segments = ((data_size-1)//Resource.MAX_EFFICIENT_SIZE)+1
                self.segment_index  = segment_index
                self.split          = True
                seek_index          = segment_index-1
                seek_position       = seek_index*Resource.MAX_EFFICIENT_SIZE

                data.seek(seek_position)
                resource_data = data.read(Resource.MAX_EFFICIENT_SIZE)
                self.input_file = data

        elif isinstance(data, bytes):
            data_size = len(data)
            self.grand_total_parts = math.ceil(data_size/Resource.SDU)
            self.total_size  = data_size
            
            resource_data = data
            self.total_segments = 1
            self.segment_index  = 1
            self.split          = False

        elif data == None:
            pass

        else:
            raise TypeError("Invalid data instance type passed to resource initialisation")

        data = resource_data

        self.status = Resource.NONE
        self.link = link
        self.max_retries = Resource.MAX_RETRIES
        self.max_adv_retries = Resource.MAX_ADV_RETRIES
        self.retries_left = self.max_retries
        self.timeout_factor = self.link.traffic_timeout_factor
        self.part_timeout_factor = Resource.PART_TIMEOUT_FACTOR
        self.sender_grace_time = Resource.SENDER_GRACE_TIME
        self.hmu_retry_ok = False
        self.watchdog_lock = False
        self.__watchdog_job_id = 0
        self.__progress_callback = progress_callback
        self.rtt = None
        self.rtt_rxd_bytes = 0
        self.req_sent = 0
        self.req_resp_rtt_rate = 0
        self.rtt_rxd_bytes_at_part_req = 0
        self.fast_rate_rounds = 0
        self.request_id = request_id
        self.is_response = is_response

        self.req_hashlist = []
        self.receiver_min_consecutive_height = 0

        if timeout != None:
            self.timeout = timeout
        else:
            self.timeout = self.link.rtt * self.link.traffic_timeout_factor

        if data != None:
            self.initiator         = True
            self.callback          = callback
            self.uncompressed_data = data

            compression_began = time.time()
            if (auto_compress and len(self.uncompressed_data) < Resource.AUTO_COMPRESS_MAX_SIZE):
                RNS.log("Compressing resource data...", RNS.LOG_DEBUG)
                self.compressed_data   = bz2.compress(self.uncompressed_data)
                RNS.log("Compression completed in "+str(round(time.time()-compression_began, 3))+" seconds", RNS.LOG_DEBUG)
            else:
                self.compressed_data   = self.uncompressed_data

            self.uncompressed_size = len(self.uncompressed_data)
            self.compressed_size   = len(self.compressed_data)

            if (self.compressed_size < self.uncompressed_size and auto_compress):
                saved_bytes = len(self.uncompressed_data) - len(self.compressed_data)
                RNS.log("Compression saved "+str(saved_bytes)+" bytes, sending compressed", RNS.LOG_DEBUG)

                self.data  = b""
                self.data += RNS.Identity.get_random_hash()[:Resource.RANDOM_HASH_SIZE]
                self.data += self.compressed_data
                
                self.compressed = True
                self.uncompressed_data = None

            else:
                self.data  = b""
                self.data += RNS.Identity.get_random_hash()[:Resource.RANDOM_HASH_SIZE]
                self.data += self.uncompressed_data
                self.uncompressed_data = self.data

                self.compressed = False
                self.compressed_data = None
                if auto_compress:
                    RNS.log("Compression did not decrease size, sending uncompressed", RNS.LOG_DEBUG)

            # Resources handle encryption directly to
            # make optimal use of packet MTU on an entire
            # encrypted stream. The Resource instance will
            # use it's underlying link directly to encrypt.
            self.data = self.link.encrypt(self.data)
            self.encrypted = True

            self.size = len(self.data)
            self.sent_parts = 0
            hashmap_entries = int(math.ceil(self.size/float(Resource.SDU)))
                
            hashmap_ok = False
            while not hashmap_ok:
                hashmap_computation_began = time.time()
                RNS.log("Starting resource hashmap computation with "+str(hashmap_entries)+" entries...", RNS.LOG_DEBUG)

                self.random_hash       = RNS.Identity.get_random_hash()[:Resource.RANDOM_HASH_SIZE]
                self.hash = RNS.Identity.full_hash(data+self.random_hash)
                self.truncated_hash = RNS.Identity.truncated_hash(data+self.random_hash)
                self.expected_proof = RNS.Identity.full_hash(data+self.hash)

                if original_hash == None:
                    self.original_hash = self.hash
                else:
                    self.original_hash = original_hash

                self.parts  = []
                self.hashmap = b""
                collision_guard_list = []
                for i in range(0,hashmap_entries):
                    data = self.data[i*Resource.SDU:(i+1)*Resource.SDU]
                    map_hash = self.get_map_hash(data)

                    if map_hash in collision_guard_list:
                        RNS.log("Found hash collision in resource map, remapping...", RNS.LOG_VERBOSE)
                        hashmap_ok = False
                        break
                    else:
                        hashmap_ok = True
                        collision_guard_list.append(map_hash)
                        if len(collision_guard_list) > ResourceAdvertisement.COLLISION_GUARD_SIZE:
                            collision_guard_list.pop(0)

                        part = RNS.Packet(link, data, context=RNS.Packet.RESOURCE)
                        part.pack()
                        part.map_hash = map_hash

                        self.hashmap += part.map_hash
                        self.parts.append(part)

                RNS.log("Hashmap computation concluded in "+str(round(time.time()-hashmap_computation_began, 3))+" seconds", RNS.LOG_DEBUG)
                
            if advertise:
                self.advertise()
        else:
            pass

    def hashmap_update_packet(self, plaintext):
        if not self.status == Resource.FAILED:
            self.last_activity = time.time()
            self.retries_left = self.max_retries

            update = umsgpack.unpackb(plaintext[RNS.Identity.HASHLENGTH//8:])
            self.hashmap_update(update[0], update[1])


    def hashmap_update(self, segment, hashmap):
        if not self.status == Resource.FAILED:
            self.status = Resource.TRANSFERRING
            seg_len = ResourceAdvertisement.HASHMAP_MAX_LEN
            hashes = len(hashmap)//Resource.MAPHASH_LEN
            for i in range(0,hashes):
                if self.hashmap[i+segment*seg_len] == None:
                    self.hashmap_height += 1
                self.hashmap[i+segment*seg_len] = hashmap[i*Resource.MAPHASH_LEN:(i+1)*Resource.MAPHASH_LEN]

            self.waiting_for_hmu = False
            self.request_next()

    def get_map_hash(self, data):
        return RNS.Identity.full_hash(data+self.random_hash)[:Resource.MAPHASH_LEN]

    def advertise(self):
        """
        Advertise the resource. If the other end of the link accepts
        the resource advertisement it will begin transferring.
        """
        thread = threading.Thread(target=self.__advertise_job)
        thread.daemon = True
        thread.start()

    def __advertise_job(self):
        self.advertisement_packet = RNS.Packet(self.link, ResourceAdvertisement(self).pack(), context=RNS.Packet.RESOURCE_ADV)
        while not self.link.ready_for_new_resource():
            self.status = Resource.QUEUED
            sleep(0.25)

        try:
            self.advertisement_packet.send()
            self.last_activity = time.time()
            self.adv_sent = self.last_activity
            self.rtt = None
            self.status = Resource.ADVERTISED
            self.retries_left = self.max_adv_retries
            self.link.register_outgoing_resource(self)
            RNS.log("Sent resource advertisement for "+RNS.prettyhexrep(self.hash), RNS.LOG_DEBUG)
        except Exception as e:
            RNS.log("Could not advertise resource, the contained exception was: "+str(e), RNS.LOG_ERROR)
            self.cancel()
            return

        self.watchdog_job()

    def watchdog_job(self):
        thread = threading.Thread(target=self.__watchdog_job)
        thread.daemon = True
        thread.start()

    def __watchdog_job(self):
        self.__watchdog_job_id += 1
        this_job_id = self.__watchdog_job_id

        while self.status < Resource.ASSEMBLING and this_job_id == self.__watchdog_job_id:
            while self.watchdog_lock:
                sleep(0.025)

            sleep_time = None

            if self.status == Resource.ADVERTISED:
                sleep_time = (self.adv_sent+self.timeout)-time.time()
                if sleep_time < 0:
                    if self.retries_left <= 0:
                        RNS.log("Resource transfer timeout after sending advertisement", RNS.LOG_DEBUG)
                        self.cancel()
                        sleep_time = 0.001
                    else:
                        try:
                            RNS.log("No part requests received, retrying resource advertisement...", RNS.LOG_DEBUG)
                            self.retries_left -= 1
                            self.advertisement_packet = RNS.Packet(self.link, ResourceAdvertisement(self).pack(), context=RNS.Packet.RESOURCE_ADV)
                            self.advertisement_packet.send()
                            self.last_activity = time.time()
                            self.adv_sent = self.last_activity
                            sleep_time = 0.001
                        except Exception as e:
                            RNS.log("Could not resend advertisement packet, cancelling resource", RNS.LOG_VERBOSE)
                            self.cancel()
                    

            elif self.status == Resource.TRANSFERRING:
                if not self.initiator:

                    if self.rtt == None:
                        rtt = self.link.rtt
                    else:
                        rtt = self.rtt

                    window_remaining = self.outstanding_parts

                    retries_used = self.max_retries - self.retries_left
                    extra_wait = retries_used * Resource.PER_RETRY_DELAY
                    sleep_time = self.last_activity + (rtt*(self.part_timeout_factor+window_remaining)) + Resource.RETRY_GRACE_TIME + extra_wait - time.time()
                    
                    if sleep_time < 0:
                        if self.retries_left > 0:
                            RNS.log("Timed out waiting for parts, requesting retry", RNS.LOG_DEBUG)
                            if self.window > self.window_min:
                                self.window -= 1
                                if self.window_max > self.window_min:
                                    self.window_max -= 1
                                    if (self.window_max - self.window) > (self.window_flexibility-1):
                                        self.window_max -= 1

                            sleep_time = 0.001
                            self.retries_left -= 1
                            self.waiting_for_hmu = False
                            self.request_next()
                        else:
                            self.cancel()
                            sleep_time = 0.001
                else:
                    max_extra_wait = sum([(r+1) * Resource.PER_RETRY_DELAY for r in range(self.MAX_RETRIES)])
                    max_wait = self.rtt * self.timeout_factor * self.max_retries + self.sender_grace_time + max_extra_wait
                    sleep_time = self.last_activity + max_wait - time.time()
                    if sleep_time < 0:
                        RNS.log("Resource timed out waiting for part requests", RNS.LOG_DEBUG)
                        self.cancel()
                        sleep_time = 0.001

            elif self.status == Resource.AWAITING_PROOF:
                sleep_time = self.last_part_sent + (self.rtt*self.timeout_factor+self.sender_grace_time) - time.time()
                if sleep_time < 0:
                    if self.retries_left <= 0:
                        RNS.log("Resource timed out waiting for proof", RNS.LOG_DEBUG)
                        self.cancel()
                        sleep_time = 0.001
                    else:
                        RNS.log("All parts sent, but no resource proof received, querying network cache...", RNS.LOG_DEBUG)
                        self.retries_left -= 1
                        expected_data = self.hash + self.expected_proof
                        expected_proof_packet = RNS.Packet(self.link, expected_data, packet_type=RNS.Packet.PROOF, context=RNS.Packet.RESOURCE_PRF)
                        expected_proof_packet.pack()
                        RNS.Transport.cache_request(expected_proof_packet.packet_hash, self.link)
                        self.last_part_sent = time.time()
                        sleep_time = 0.001

            if sleep_time == 0:
                RNS.log("Warning! Link watchdog sleep time of 0!", RNS.LOG_WARNING)
            if sleep_time == None or sleep_time < 0:
                RNS.log("Timing error, cancelling resource transfer.", RNS.LOG_ERROR)
                self.cancel()
            
            if sleep_time != None:
                sleep(min(sleep_time, Resource.WATCHDOG_MAX_SLEEP))

    def assemble(self):
        if not self.status == Resource.FAILED:
            try:
                self.status = Resource.ASSEMBLING
                stream = b"".join(self.parts)

                if self.encrypted:
                    data = self.link.decrypt(stream)
                else:
                    data = stream

                # Strip off random hash
                data = data[Resource.RANDOM_HASH_SIZE:]

                if self.compressed:
                    self.data = bz2.decompress(data)
                else:
                    self.data = data

                calculated_hash = RNS.Identity.full_hash(self.data+self.random_hash)

                if calculated_hash == self.hash:
                    self.file = open(self.storagepath, "ab")
                    self.file.write(self.data)
                    self.file.close()
                    self.status = Resource.COMPLETE
                    self.prove()
                else:
                    self.status = Resource.CORRUPT


            except Exception as e:
                RNS.log("Error while assembling received resource.", RNS.LOG_ERROR)
                RNS.log("The contained exception was: "+str(e), RNS.LOG_ERROR)
                self.status = Resource.CORRUPT

            self.link.resource_concluded(self)

            if self.segment_index == self.total_segments:
                if self.callback != None:
                    self.data = open(self.storagepath, "rb")
                    try:
                        self.callback(self)
                    except Exception as e:
                        RNS.log("Error while executing resource assembled callback from "+str(self)+". The contained exception was: "+str(e), RNS.LOG_ERROR)

                try:
                    if hasattr(self.data, "close") and callable(self.data.close):
                        self.data.close()

                    os.unlink(self.storagepath)

                except Exception as e:
                    RNS.log("Error while cleaning up resource files, the contained exception was:", RNS.LOG_ERROR)
                    RNS.log(str(e))
            else:
                RNS.log("Resource segment "+str(self.segment_index)+" of "+str(self.total_segments)+" received, waiting for next segment to be announced", RNS.LOG_DEBUG)


    def prove(self):
        if not self.status == Resource.FAILED:
            try:
                proof = RNS.Identity.full_hash(self.data+self.hash)
                proof_data = self.hash+proof
                proof_packet = RNS.Packet(self.link, proof_data, packet_type=RNS.Packet.PROOF, context=RNS.Packet.RESOURCE_PRF)
                proof_packet.send()
            except Exception as e:
                RNS.log("Could not send proof packet, cancelling resource", RNS.LOG_DEBUG)
                RNS.log("The contained exception was: "+str(e), RNS.LOG_DEBUG)
                self.cancel()

    def validate_proof(self, proof_data):
        if not self.status == Resource.FAILED:
            if len(proof_data) == RNS.Identity.HASHLENGTH//8*2:
                if proof_data[RNS.Identity.HASHLENGTH//8:] == self.expected_proof:
                    self.status = Resource.COMPLETE
                    self.link.resource_concluded(self)
                    if self.segment_index == self.total_segments:
                        # If all segments were processed, we'll
                        # signal that the resource sending concluded
                        if self.callback != None:
                            try:
                                self.callback(self)
                            except Exception as e:
                                RNS.log("Error while executing resource concluded callback from "+str(self)+". The contained exception was: "+str(e), RNS.LOG_ERROR)
                    else:
                        # Otherwise we'll recursively create the
                        # next segment of the resource
                        Resource(self.input_file, self.link, callback = self.callback, segment_index = self.segment_index+1, original_hash=self.original_hash, progress_callback = self.__progress_callback)
                else:
                    pass
            else:
                pass


    def receive_part(self, packet):
        while self.receiving_part:
            sleep(0.001)

        self.receiving_part = True
        self.last_activity = time.time()
        self.retries_left = self.max_retries

        if self.req_resp == None:
            self.req_resp = self.last_activity
            rtt = self.req_resp-self.req_sent
            
            self.part_timeout_factor = Resource.PART_TIMEOUT_FACTOR_AFTER_RTT
            if self.rtt == None:
                self.rtt = self.link.rtt
                self.watchdog_job()
            elif rtt < self.rtt:
                self.rtt = max(self.rtt - self.rtt*0.05, rtt)
            elif rtt > self.rtt:
                self.rtt = min(self.rtt + self.rtt*0.05, rtt)

            if rtt > 0:
                req_resp_cost = len(packet.raw)+self.req_sent_bytes
                self.req_resp_rtt_rate = req_resp_cost / rtt

                if self.req_resp_rtt_rate > Resource.RATE_FAST and self.fast_rate_rounds < Resource.FAST_RATE_THRESHOLD:
                    self.fast_rate_rounds += 1

                    if self.fast_rate_rounds == Resource.FAST_RATE_THRESHOLD:
                        self.window_max = Resource.WINDOW_MAX_FAST

        if not self.status == Resource.FAILED:
            self.status = Resource.TRANSFERRING
            part_data = packet.data
            part_hash = self.get_map_hash(part_data)

            i = self.consecutive_completed_height
            for map_hash in self.hashmap[self.consecutive_completed_height:self.consecutive_completed_height+self.window]:
                if map_hash == part_hash:
                    if self.parts[i] == None:
                        # Insert data into parts list
                        self.parts[i] = part_data
                        self.rtt_rxd_bytes += len(part_data)
                        self.received_count += 1
                        self.outstanding_parts -= 1

                        # Update consecutive completed pointer
                        if i == self.consecutive_completed_height + 1:
                            self.consecutive_completed_height = i
                        
                        cp = self.consecutive_completed_height + 1
                        while cp < len(self.parts) and self.parts[cp] != None:
                            self.consecutive_completed_height = cp
                            cp += 1

                        if self.__progress_callback != None:
                            try:
                                self.__progress_callback(self)
                            except Exception as e:
                                RNS.log("Error while executing progress callback from "+str(self)+". The contained exception was: "+str(e), RNS.LOG_ERROR)

                i += 1

            self.receiving_part = False

            if self.received_count == self.total_parts and not self.assembly_lock:
                self.assembly_lock = True
                self.assemble()
            elif self.outstanding_parts == 0:
                # TODO: Figure out if there is a mathematically
                # optimal way to adjust windows
                if self.window < self.window_max:
                    self.window += 1
                    if (self.window - self.window_min) > (self.window_flexibility-1):
                        self.window_min += 1

                if self.req_sent != 0:
                    rtt = time.time()-self.req_sent
                    req_transferred = self.rtt_rxd_bytes - self.rtt_rxd_bytes_at_part_req

                    if rtt != 0:
                        self.req_data_rtt_rate = req_transferred/rtt
                        self.rtt_rxd_bytes_at_part_req = self.rtt_rxd_bytes

                        if self.req_data_rtt_rate > Resource.RATE_FAST and self.fast_rate_rounds < Resource.FAST_RATE_THRESHOLD:
                            self.fast_rate_rounds += 1

                            if self.fast_rate_rounds == Resource.FAST_RATE_THRESHOLD:
                                self.window_max = Resource.WINDOW_MAX_FAST

                self.request_next()
        else:
            self.receiving_part = False

    # Called on incoming resource to send a request for more data
    def request_next(self):
        while self.receiving_part:
            sleep(0.001)

        if not self.status == Resource.FAILED:
            if not self.waiting_for_hmu:
                self.outstanding_parts = 0
                hashmap_exhausted = Resource.HASHMAP_IS_NOT_EXHAUSTED
                requested_hashes = b""

                offset = (1 if self.consecutive_completed_height > 0 else 0)
                i = 0; pn = self.consecutive_completed_height+offset
                search_start = pn

                for part in self.parts[search_start:search_start+self.window]:
                    if part == None:
                        part_hash = self.hashmap[pn]
                        if part_hash != None:
                            requested_hashes += part_hash
                            self.outstanding_parts += 1
                            i += 1
                        else:
                            hashmap_exhausted = Resource.HASHMAP_IS_EXHAUSTED

                    pn += 1
                    if i >= self.window or hashmap_exhausted == Resource.HASHMAP_IS_EXHAUSTED:
                        break

                hmu_part = bytes([hashmap_exhausted])
                if hashmap_exhausted == Resource.HASHMAP_IS_EXHAUSTED:
                    last_map_hash = self.hashmap[self.hashmap_height-1]
                    hmu_part += last_map_hash
                    self.waiting_for_hmu = True

                requested_data = b""
                request_data = hmu_part + self.hash + requested_hashes
                request_packet = RNS.Packet(self.link, request_data, context = RNS.Packet.RESOURCE_REQ)

                try:
                    request_packet.send()
                    self.last_activity = time.time()
                    self.req_sent = self.last_activity
                    self.req_sent_bytes = len(request_packet.raw)
                    self.req_resp = None
                except Exception as e:
                    RNS.log("Could not send resource request packet, cancelling resource", RNS.LOG_DEBUG)
                    RNS.log("The contained exception was: "+str(e), RNS.LOG_DEBUG)
                    self.cancel()

    # Called on outgoing resource to make it send more data
    def request(self, request_data):
        if not self.status == Resource.FAILED:
            rtt = time.time() - self.adv_sent
            if self.rtt == None:
                self.rtt = rtt

            if self.status != Resource.TRANSFERRING:
                self.status = Resource.TRANSFERRING
                self.watchdog_job()

            self.retries_left = self.max_retries

            wants_more_hashmap = True if request_data[0] == Resource.HASHMAP_IS_EXHAUSTED else False
            pad = 1+Resource.MAPHASH_LEN if wants_more_hashmap else 1

            requested_hashes = request_data[pad+RNS.Identity.HASHLENGTH//8:]

            # Define the search scope
            search_start = self.receiver_min_consecutive_height
            search_end   = self.receiver_min_consecutive_height+ResourceAdvertisement.COLLISION_GUARD_SIZE

            map_hashes = []
            for i in range(0,len(requested_hashes)//Resource.MAPHASH_LEN):
                map_hash = requested_hashes[i*Resource.MAPHASH_LEN:(i+1)*Resource.MAPHASH_LEN]
                map_hashes.append(map_hash)

            search_scope = self.parts[search_start:search_end]
            requested_parts = list(filter(lambda part: part.map_hash in map_hashes, search_scope))

            for part in requested_parts:
                try:
                    if not part.sent:
                        part.send()
                        self.sent_parts += 1
                    else:
                        part.resend()

                    self.last_activity = time.time()
                    self.last_part_sent = self.last_activity

                except Exception as e:
                    RNS.log("Resource could not send parts, cancelling transfer!", RNS.LOG_DEBUG)
                    RNS.log("The contained exception was: "+str(e), RNS.LOG_DEBUG)
                    self.cancel()
            
            if wants_more_hashmap:
                last_map_hash = request_data[1:Resource.MAPHASH_LEN+1]
                
                part_index   = self.receiver_min_consecutive_height
                search_start = part_index
                search_end   = self.receiver_min_consecutive_height+ResourceAdvertisement.COLLISION_GUARD_SIZE
                for part in self.parts[search_start:search_end]:
                    part_index += 1
                    if part.map_hash == last_map_hash:
                        break

                self.receiver_min_consecutive_height = max(part_index-1-Resource.WINDOW_MAX, 0)

                if part_index % ResourceAdvertisement.HASHMAP_MAX_LEN != 0:
                    RNS.log("Resource sequencing error, cancelling transfer!", RNS.LOG_ERROR)
                    self.cancel()
                    return
                else:
                    segment = part_index // ResourceAdvertisement.HASHMAP_MAX_LEN

                
                hashmap_start = segment*ResourceAdvertisement.HASHMAP_MAX_LEN
                hashmap_end   = min((segment+1)*ResourceAdvertisement.HASHMAP_MAX_LEN, len(self.parts))

                hashmap = b""
                for i in range(hashmap_start,hashmap_end):
                    hashmap += self.hashmap[i*Resource.MAPHASH_LEN:(i+1)*Resource.MAPHASH_LEN]

                hmu = self.hash+umsgpack.packb([segment, hashmap])
                hmu_packet = RNS.Packet(self.link, hmu, context = RNS.Packet.RESOURCE_HMU)

                try:
                    hmu_packet.send()
                    self.last_activity = time.time()
                except Exception as e:
                    RNS.log("Could not send resource HMU packet, cancelling resource", RNS.LOG_DEBUG)
                    RNS.log("The contained exception was: "+str(e), RNS.LOG_DEBUG)
                    self.cancel()

            if self.sent_parts == len(self.parts):
                self.status = Resource.AWAITING_PROOF

            if self.__progress_callback != None:
                try:
                    self.__progress_callback(self)
                except Exception as e:
                    RNS.log("Error while executing progress callback from "+str(self)+". The contained exception was: "+str(e), RNS.LOG_ERROR)

    def cancel(self):
        """
        Cancels transferring the resource.
        """
        if self.status < Resource.COMPLETE:
            self.status = Resource.FAILED
            if self.initiator:
                if self.link.status == RNS.Link.ACTIVE:
                    try:
                        cancel_packet = RNS.Packet(self.link, self.hash, context=RNS.Packet.RESOURCE_ICL)
                        cancel_packet.send()
                    except Exception as e:
                        RNS.log("Could not send resource cancel packet, the contained exception was: "+str(e), RNS.LOG_ERROR)
                self.link.cancel_outgoing_resource(self)
            else:
                self.link.cancel_incoming_resource(self)
            
            if self.callback != None:
                try:
                    self.link.resource_concluded(self)
                    self.callback(self)
                except Exception as e:
                    RNS.log("Error while executing callbacks on resource cancel from "+str(self)+". The contained exception was: "+str(e), RNS.LOG_ERROR)

    def set_callback(self, callback):
        self.callback = callback

    def progress_callback(self, callback):
        self.__progress_callback = callback

    def get_progress(self):
        """
        :returns: The current progress of the resource transfer as a *float* between 0.0 and 1.0.
        """
        if self.initiator:
            self.processed_parts  = (self.segment_index-1)*math.ceil(Resource.MAX_EFFICIENT_SIZE/Resource.SDU)
            self.processed_parts += self.sent_parts
            self.progress_total_parts = float(self.grand_total_parts)
        else:
            self.processed_parts  = (self.segment_index-1)*math.ceil(Resource.MAX_EFFICIENT_SIZE/Resource.SDU)            
            self.processed_parts += self.received_count
            if self.split:
                self.progress_total_parts = float(math.ceil(self.total_size/Resource.SDU))
            else:
                self.progress_total_parts = float(self.total_parts)

        
        progress = self.processed_parts / self.progress_total_parts
        return progress

    def get_transfer_size(self):
        """
        :returns: The number of bytes needed to transfer the resource.
        """
        return self.size

    def get_data_size(self):
        """
        :returns: The total data size of the resource.
        """
        return self.total_size

    def get_parts(self):
        """
        :returns: The number of parts the resource will be transferred in.
        """
        return self.total_parts

    def get_segments(self):
        """
        :returns: The number of segments the resource is divided into.
        """
        return self.total_segments

    def get_hash(self):
        """
        :returns: The hash of the resource.
        """
        return self.hash

    def is_compressed(self):
        """
        :returns: Whether the resource is compressed.
        """
        return self.compressed

    def __str__(self):
        return "<"+RNS.hexrep(self.hash,delimit=False)+"/"+RNS.hexrep(self.link.link_id,delimit=False)+">"


class ResourceAdvertisement:
    OVERHEAD             = 134
    HASHMAP_MAX_LEN      = math.floor((RNS.Link.MDU-OVERHEAD)/Resource.MAPHASH_LEN)
    COLLISION_GUARD_SIZE = 2*Resource.WINDOW_MAX+HASHMAP_MAX_LEN

    assert HASHMAP_MAX_LEN > 0, "The configured MTU is too small to include any map hashes in resource advertisments"

    @staticmethod
    def is_request(advertisement_packet):
        adv = ResourceAdvertisement.unpack(advertisement_packet.plaintext)
        if adv.q != None and adv.u:
            return True
        else:
            return False


    @staticmethod
    def is_response(advertisement_packet):
        adv = ResourceAdvertisement.unpack(advertisement_packet.plaintext)

        if adv.q != None and adv.p:
            return True
        else:
            return False


    @staticmethod
    def read_request_id(advertisement_packet):
        adv = ResourceAdvertisement.unpack(advertisement_packet.plaintext)
        return adv.q


    @staticmethod
    def read_transfer_size(advertisement_packet):
        adv = ResourceAdvertisement.unpack(advertisement_packet.plaintext)
        return adv.t


    @staticmethod
    def read_size(advertisement_packet):
        adv = ResourceAdvertisement.unpack(advertisement_packet.plaintext)
        return adv.d


    def __init__(self, resource=None, request_id=None, is_response=False):
        if resource != None:
            self.t = resource.size              # Transfer size
            self.d = resource.total_size        # Total uncompressed data size
            self.n = len(resource.parts)        # Number of parts
            self.h = resource.hash              # Resource hash
            self.r = resource.random_hash       # Resource random hash
            self.o = resource.original_hash     # First-segment hash
            self.m = resource.hashmap           # Resource hashmap
            self.c = resource.compressed        # Compression flag
            self.e = resource.encrypted         # Encryption flag
            self.s = resource.split             # Split flag
            self.i = resource.segment_index     # Segment index
            self.l = resource.total_segments    # Total segments
            self.q = resource.request_id        # ID of associated request
            self.u = False                      # Is request flag
            self.p = False                      # Is response flag

            if self.q != None:
                if not resource.is_response:
                    self.u = True
                    self.p = False
                else:
                    self.u = False
                    self.p = True

            # Flags
            self.f = 0x00 | self.p << 4 | self.u << 3 | self.s << 2 | self.c << 1 | self.e

    def get_transfer_size(self):
        return self.t

    def get_data_size(self):
        return self.d

    def get_parts(self):
        return self.n

    def get_segments(self):
        return self.l

    def get_hash(self):
        return self.h

    def is_compressed(self):
        return self.c

    def pack(self, segment=0):
        hashmap_start = segment*ResourceAdvertisement.HASHMAP_MAX_LEN
        hashmap_end   = min((segment+1)*(ResourceAdvertisement.HASHMAP_MAX_LEN), self.n)

        hashmap = b""
        for i in range(hashmap_start,hashmap_end):
            hashmap += self.m[i*Resource.MAPHASH_LEN:(i+1)*Resource.MAPHASH_LEN]

        dictionary = {
            "t": self.t,    # Transfer size
            "d": self.d,    # Data size
            "n": self.n,    # Number of parts
            "h": self.h,    # Resource hash
            "r": self.r,    # Resource random hash
            "o": self.o,    # Original hash
            "i": self.i,    # Segment index
            "l": self.l,    # Total segments
            "q": self.q,    # Request ID
            "f": self.f,    # Resource flags
            "m": hashmap
        }

        return umsgpack.packb(dictionary)


    @staticmethod
    def unpack(data):
        dictionary = umsgpack.unpackb(data)
        
        adv   = ResourceAdvertisement()
        adv.t = dictionary["t"]
        adv.d = dictionary["d"]
        adv.n = dictionary["n"]
        adv.h = dictionary["h"]
        adv.r = dictionary["r"]
        adv.o = dictionary["o"]
        adv.m = dictionary["m"]
        adv.f = dictionary["f"]
        adv.i = dictionary["i"]
        adv.l = dictionary["l"]
        adv.q = dictionary["q"]
        adv.e = True if (adv.f & 0x01) == 0x01 else False
        adv.c = True if ((adv.f >> 1) & 0x01) == 0x01 else False
        adv.s = True if ((adv.f >> 2) & 0x01) == 0x01 else False
        adv.u = True if ((adv.f >> 3) & 0x01) == 0x01 else False
        adv.p = True if ((adv.f >> 4) & 0x01) == 0x01 else False

        return adv