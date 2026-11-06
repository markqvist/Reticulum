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

import RNS
import RNS.vendor.umsgpack as msgpack
from RNS.Cryptography import sha256

import os
import sys
import time
import math
import mmap
import itertools
import contextlib
import multiprocessing
from bisect import bisect_right

WORKBLOCK_EXPAND_CHUNK      = 256
WORKBLOCK_EXPAND_ROUNDS     = 3000
STAMP_SIZE                  = 32
PN_VALIDATION_POOL_MIN_SIZE = 256
USE_WORKER_MANAGER          = False
POOLING_THRESHOLD_COST      = 14
KEYSTAMP_POOLING_THRESHOLD  = 10
STOP_CHECK_INTERVAL         = 64

MODE_STAMP                  = 0x00
MODE_KEYSTAMP               = 0x01

active_jobs = {}

if sys.version_info[0] >= 3 and sys.version_info[1] >= 14:
    USE_WORKER_MANAGER = True

@contextlib.contextmanager
def worker_context(ctx, stamp_cost, workblock, message_id):
    stop_event = ctx.Event()
    result_queue = ctx.Queue(1)
    rounds_queue = ctx.Queue()

    active_jobs[message_id] = [stop_event, result_queue]
    job_procs = []

    try: yield stop_event, result_queue, rounds_queue, job_procs
    finally:
        if message_id in active_jobs: del active_jobs[message_id]
        stop_event.set()

        for p in job_procs:
            if p.is_alive(): p.terminate()
        
        for p in job_procs: p.join(timeout=0.5)
        
        result_queue.close()
        result_queue.join_thread()
        rounds_queue.close()
        rounds_queue.join_thread()
        stop_event.clear()

def stamp_workblock(material, expand_rounds=WORKBLOCK_EXPAND_ROUNDS, no_expand=False):
    if no_expand or not expand_rounds: return material
    wb_st = time.time()
    workblock = b""
    for n in range(expand_rounds):
        workblock += RNS.Cryptography.hkdf(length=WORKBLOCK_EXPAND_CHUNK, derive_from=material,
                                           salt=RNS.Identity.full_hash(material+msgpack.packb(n)),
                                           context=None)
    wb_time = time.time() - wb_st

    return workblock

def stamp_value_legacy(workblock, stamp):
    if not workblock: workblock = b""
    stamp_product = RNS.Identity.full_hash(workblock+stamp)
    return 256 - int.from_bytes(stamp_product, byteorder="big").bit_length()

def stamp_value(workblock, stamp):
    # This function is very little code, and a whole lot of
    # comments. The actual method employed here is relatively
    # simple, but without proper explanation, it is also very
    # opaque, and could induce a lot of head-scratching.

    if not workblock: workblock = b""
    stamp_product = RNS.Identity.full_hash(workblock+stamp) # Bytes representation
    hn = int.from_bytes(stamp_product, byteorder="big")     # Numerical representation
    if hn == 0: return 256                                  # Yeah, but *if* it happens, you know...
    nb = MANTISSA_BITS+1                                    # Normalized mantissa bit count
    bl = hn.bit_length()                                    # Bit length of the stamp product
    lz = 256 - bl                                           # Leading zeros of the stamp product

    ##############################################################
    #                                                            #
    #        Simplified mantissa extraction example with         #
    #        smaller numbers; 32-bit stamp product and 8         #
    #        mantissa bits. In the actual version, it is         #
    #        256-bit stamp products and 33-bit mantissa.         #
    #                                                            #
    #                    mb =  8       nb = 9 (8+1)              #
    #                    bl = 27       lz = 5 (32-27)            #
    #                                                            #
    #                    shift = bl - nb = 18                    #
    #                                                            #
    # hn = 0b00000111101101101110111010110111                    #
    # >>18 0b00000000000000000000000111101101|101110111010110111 #
    #                               |    \_____      gone        #
    #                        The leading one   |                 #
    #                             8 significand mantissa bits    #
    #                                                            #
    #      mn = 0b111101101 (normalized with the leading 1)      #
    #                                                            #
    ##############################################################

    # Normalize mantissa to the scale of TAB: Total of 34
    # bits, 33 mantissa bits. The leading one required to
    # match TAB entries is guaranteed by the construction:
    # Since we're shifting by the *difference* between the
    # normalized mantissa bit length and the stamp product
    # bit length, we always end up with a leading one, and
    # then the required number of *actual* mantissa bits.
    # See the example above for a simplified illustration.
    if bl > nb: mn = (hn >> (bl - nb))
    else:       mn = (hn << (nb - bl)) # Again, better safe than sorry. You may notice
                                       # here that in this case, we will have a more
                                       # coarse mantissa part, which is inherent to
                                       # the methodology, but in practice the best thing
                                       # we can do. Additionally, this can only happen
                                       # at absolutely extreme values, far above the
                                       # stamp cap anyway. It is only here to handle the
                                       # absurd case where a stamp product randomly lands
                                       # on an astronomically improbable leading zero count.

    # We can now construct the fixed-point value representation:
    #
    # The leading zero count is equivalent to the legacy value, an
    # integer representation. Thus, (lz+1)<<COST_FP_BITS gives us
    # the fixed-point representation of a value one greater than
    # what we currently have. Since the mantissa is normalized, the
    # real value always lies somewhere in between, at the ceiling
    # minus however far the mantissa has climbed into this range
    #
    # Right-bisecting TAB with the normalized mantissa returns the
    # number of grid points at or below it, and since the table
    # values *are* the normalized mantissas of the grid points in
    # our 256-step quantization, this count is the climb, quantized
    # in 1/256th steps. The *count* always overshoots the *actual*
    # climb (one full step on an exact match), so subtracting it
    # from the ceiling *floors* the value onto the grid, so we
    # never over-value the stamp.
    #
    # Note that for a mantissa *past* (or equal to) the last table
    # entry, there is no special case handling required, since the
    # bisect_right count returned in that case is 256 (the largest
    # it can ever return). Thus, the arithmetic itself here folds
    # correctly: The entire "added one" (lz+1) is consumed, and can
    # never over-consume. Remember: In the fixed-point representation
    # a value of 1.0 *is* 256 (and, as a side note, this is one of
    # the reasons that len(TAB)==COST_FP is asserted as invariant).

    value_fp = ((lz + 1) << COST_FP_BITS) - bisect_right(TAB, mn)

    # Then, convert to decimal representation and return it
    return cost_from_fp(value_fp)

def stamp_valid(stamp, target_cost, workblock):
    if not workblock: workblock = b""
    target = target_from_fp(cost_to_fp(target_cost))
    result = RNS.Identity.full_hash(workblock+stamp)
    if int.from_bytes(result, byteorder="big") > target: return False
    else: return True

# Synthetic stop check function used where
# worker mechanism provides no support for
# semaphore-based cancellation.
def _never(): return False

# The hash-mode loop primitive, shared
# between platform variants.
def _loop_hash(workblock, target, size, stop_check, progress=None, max_rounds=0, fh=None):
    if fh == None: fh = RNS.Identity.full_hash
    urandom = os.urandom
    rounds  = 0
    found   = False
    pstamp  = urandom(size)
    c       = 0

    while True:
        c += 1
        if c >= STOP_CHECK_INTERVAL:
            c = 0
            if stop_check(): break

        if int.from_bytes(fh(workblock+pstamp), byteorder="big") <= target:
            found = True; break
        pstamp = urandom(size); rounds += 1

        if progress != None and rounds % 250000 == 0: progress(rounds)
        if max_rounds != 0 and rounds >= max_rounds: break

    return pstamp, rounds, found

# The key-mode loop primitive, shared
# between platform variants.
def _loop_key(material, target, stop_check, max_rounds=0):
    fh       = RNS.Identity.full_hash
    generate = RNS.Cryptography.X25519PrivateKey.generate
    rounds   = 0
    found    = False
    keypair  = None

    while True:
        if stop_check(): break

        key       = generate()
        pub_bytes = key.public_key().public_bytes()
        if int.from_bytes(fh(material+pub_bytes), byteorder="big") <= target:
            keypair = (key.private_bytes(), pub_bytes)
            found   = True; break
        rounds += 1

        if max_rounds != 0 and rounds >= max_rounds: break

    return keypair, rounds, found

# Generates a normal, detached, hash-based stamp for any
# bytes material (message_id), which is usually a hash
# of some input material, but can be any sequence of bytes.
def generate_stamp(message_id, stamp_cost, expand_rounds=WORKBLOCK_EXPAND_ROUNDS, no_expand=False, size=STAMP_SIZE):
    if stamp_cost < 0 or stamp_cost > RNS.Transport.STAMP_COST_CAP: raise ValueError("Invalid stamp cost, cannot generate")
    workblock = stamp_workblock(message_id, expand_rounds=expand_rounds, no_expand=no_expand)

    if message_id in active_jobs: raise RuntimeError(f"Duplicate stamp generation job for {RNS.prettyhexrep(message_id)}")
    RNS.log(f"Generating stamp with cost {stamp_cost} for <{RNS.hexrep(message_id[:16], delimit=False)}{'…' if len(message_id) > 16 else ''}>", RNS.LOG_DEBUG)

    stamp_cost = cost_to_fp(stamp_cost)
    start_time = time.time()
    stamp      = None
    value      = None
    rounds     = 0

    if RNS.vendor.platformutils.is_windows() or RNS.vendor.platformutils.is_darwin():
        RNS.log(f"Multi-core stamp generation on this platform is not supported, work limited to single CPU core.", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None

    if RNS.vendor.platformutils.is_windows() or RNS.vendor.platformutils.is_darwin(): stamp, rounds = job_simple(stamp_cost, workblock, message_id, size)
    elif RNS.vendor.platformutils.is_android(): stamp, rounds = job_android(stamp_cost, workblock, message_id, size)
    else:
        if USE_WORKER_MANAGER: stamp, rounds = job_linux_managed(stamp_cost, workblock, message_id, size) if stamp_cost >= POOLING_THRESHOLD_COST_FP else job_simple(stamp_cost, workblock, message_id, size)
        else:                  stamp, rounds = job_linux(stamp_cost, workblock, message_id, size) if stamp_cost >= POOLING_THRESHOLD_COST_FP else job_simple(stamp_cost, workblock, message_id, size)
    
    duration = max(time.time()-start_time, 1E-6)
    speed = rounds/duration
    if stamp != None: value = stamp_value(workblock, stamp)

    if value != None: RNS.log(f"Stamp with value {value} generated in {RNS.prettytime(duration)}, {rounds} rounds, {RNS.prettysize(speed, suffix='rps')}", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
    else: RNS.log(f"Stamp generation aborted or failed after {RNS.prettytime(duration)}, {rounds} rounds", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None

    return stamp, value

# Generates a new, internally stamped X25519 keypair. The
# public key carries the stamp value itself, so no detached
# stamp is created. Unlike the detached stamp generator, this
# method returns the private+public X25519 keypair, and the
# private key can be loaded normally to create a full, stamped
# Reticulum Identity. The stamp value is verifiable to anyone
# knowing the public key (and the optional input material).
#
# For a transparently verifiable stamped identity, you should
# generally always use the provided `RNS.Identity(value=n)`
# primitive, and not generate raw stamped keys manually. Using
# the API primitive correctly binds the full identity keyset
# together with the stamped portion of the key. Situations do
# exist where you may want a bare, no-material stamped key,
# but this should be considered hazardous materials territory!
#
# For custom stamped keys, where the stamped key is intended
# to be tied to a specific domain, for example a link request
# or other one-time use, the `material` argument must be the
# relevant uniquely identifying nonce of such use that the
# stamped key is bound to.
#
# Key stamp validation uses the normal validation methods,
# simply provide the public key bytes directly *as* the stamp,
# and any domain material as the workblock, for example:
#
# - stamp_valid(public_key_bytes, required_cost, material)
# - stamp_value(material, public_key_bytes)
#
# WARNING: Never attempt to use this for Ed25519 *signature* key
# creation, is NOT a valid approach. The keypairs emitted by
# this function must ONLY be used as X25519 keys.
def generate_stamped_key(material, stamp_cost):
    if material == None: material = b""
    if material in active_jobs: raise RuntimeError(f"Duplicate stamped key generation job for {RNS.prettyhexrep(material)}")
    if stamp_cost < 0 or stamp_cost > RNS.Transport.STAMP_COST_CAP: raise ValueError("Invalid stamp cost, cannot generate")
    for_str = f" for <{RNS.hexrep(material[:16], delimit=False)}{'…' if len(material) > 16 else ''}>" if material else ""
    RNS.log(f"Generating stamped key with cost {stamp_cost}{for_str}", RNS.LOG_DEBUG)

    stamp_cost = cost_to_fp(stamp_cost)
    start_time = time.time()
    keypair    = None
    value      = None
    rounds     = 0

    if RNS.vendor.platformutils.is_windows() or RNS.vendor.platformutils.is_darwin():
        RNS.log(f"Multi-core stamp generation on this platform is not supported, work limited to single CPU core.", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None

    if RNS.vendor.platformutils.is_windows() or RNS.vendor.platformutils.is_darwin(): keypair, rounds = job_simple(stamp_cost, material, material, 0, MODE_KEYSTAMP)
    elif RNS.vendor.platformutils.is_android(): keypair, rounds = job_android(stamp_cost, material, material, 0, MODE_KEYSTAMP)
    else:
        if USE_WORKER_MANAGER: keypair, rounds = job_linux_managed(stamp_cost, material, material, 0, MODE_KEYSTAMP) if stamp_cost >= KEYSTAMP_POOLING_THRESHOLD_FP else job_simple(stamp_cost, material, material, 0, MODE_KEYSTAMP)
        else:                  keypair, rounds = job_linux(stamp_cost, material, material, 0, MODE_KEYSTAMP) if stamp_cost >= KEYSTAMP_POOLING_THRESHOLD_FP else job_simple(stamp_cost, material, material, 0, MODE_KEYSTAMP)

    duration = max(time.time()-start_time, 1E-6)
    speed = rounds/duration
    if keypair != None: value = stamp_value(material, keypair[1])

    if value != None: RNS.log(f"Stamped key with value {value} generated in {RNS.prettyshorttime(duration)}, {rounds} rounds, {RNS.prettysize(speed, suffix='rps')}", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
    else: RNS.log(f"Stamp generation aborted or failed after {RNS.prettytime(duration)}, {rounds} rounds", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None

    return keypair, value

def cancel_work(message_id):
    if RNS.vendor.platformutils.is_windows() or RNS.vendor.platformutils.is_darwin():
        try:
            if message_id in active_jobs: active_jobs[message_id] = True
            else: return False

        except Exception as e:
            RNS.log("Error while terminating stamp generation workers: {e}", RNS.LOG_ERROR)
            RNS.trace_exception(e)
            return False

    elif RNS.vendor.platformutils.is_android():
        try:
            if message_id in active_jobs: active_jobs[message_id] = True
            else: return False

        except Exception as e:
            RNS.log("Error while terminating stamp generation workers: {e}", RNS.LOG_ERROR)
            RNS.trace_exception(e)
            return False

    else:
        try:
            job_entry = active_jobs.get(message_id, None)
            if job_entry != None:
                if type(job_entry) != list: active_jobs[message_id] = True
                else:
                    stop_event = job_entry[0]
                    result_queue = job_entry[1]
                    stop_event.set()
                    result_queue.put(None)
                    active_jobs.pop(message_id)
            else: return False

        except Exception as e:
            RNS.log("Error while terminating stamp generation workers: {e}", RNS.LOG_ERROR)
            RNS.trace_exception(e)
            return False

    return True

def job_simple(stamp_cost, workblock, message_id, size, mode=MODE_STAMP):
    # A simple, single-process stamp generator.
    # should work on any platform, and is used
    # as a fall-back, in case of limited multi-
    # processing and/or acceleration support.
    #
    # In key mode, the workblock argument is
    # used for the stamp material, and the
    # size argument is ignored.

    st = time.time()
    target = target_from_fp(stamp_cost)

    active_jobs[message_id] = False

    def stop_check(): return active_jobs[message_id]
    def progress(r):
        speed = r / max(time.time()-st, 1E-6)
        RNS.log(f"Stamp generation running. {r} rounds completed so far, {RNS.prettysize(speed, suffix='')} rounds per second", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None

    if mode == MODE_STAMP:    result, rounds, _ = _loop_hash(workblock, target, size, stop_check, progress)
    else:                     result, rounds, _ = _loop_key(workblock, target, stop_check)

    cancelled = (active_jobs[message_id] == True)
    active_jobs.pop(message_id)
    return (None if cancelled else result), rounds

def job_linux_managed(stamp_cost, workblock, message_id, size, mode=MODE_STAMP):
    ctx = multiprocessing.get_context("fork")
    cores = multiprocessing.cpu_count()
    jobs = cores if cores <= 12 else int(cores/2)
    
    allow_kill = True
    stamp = None
    total_rounds = 0
    
    with worker_context(ctx, stamp_cost, workblock, message_id) as (stop_event, result_queue, rounds_queue, job_procs):
        RNS.log(f"Starting {jobs} stamp generation workers", RNS.LOG_DEBUG)
        
        def job(stop_event, sc, wb, pn, mode):
            target = target_from_fp(sc)

            if mode == MODE_STAMP: result, rounds, _ = _loop_hash(wb, target, size, stop_event.is_set)
            else:                  result, rounds, _ = _loop_key(wb, target, stop_event.is_set)

            if not stop_event.is_set():
                stop_event.set()
                try: result_queue.put_nowait(result)
                except: pass
            
            try: rounds_queue.put_nowait(rounds)
            except: pass

        for jpn in range(jobs):
            p = ctx.Process(target=job, args=(stop_event, stamp_cost, workblock, jpn, mode), daemon=True)
            job_procs.append(p)
            p.start()
        
        try: stamp = result_queue.get(timeout=None)
        except Exception as e:
            RNS.log(f"Failed to get result from workers: {e}", RNS.LOG_ERROR)
            stamp = None
        
        # Collect any potential spurious
        # results from worker queue.
        try:
            while True: result_queue.get_nowait()
        except: pass

        for j in range(jobs):
            nrounds = 0
            try:
                nrounds = rounds_queue.get(timeout=2)
            except Exception as e:
                RNS.log(f"Failed to get round stats part {j}: {e}", RNS.LOG_ERROR)
            total_rounds += nrounds

        all_exited = False
        exit_timeout = time.time() + 5
        while time.time() < exit_timeout:
            if not any(p.is_alive() for p in job_procs):
                all_exited = True
                break
            time.sleep(0.005)

        if not all_exited:
            RNS.log("Stamp generation IPC timeout, possible worker deadlock. Terminating remaining processes.", RNS.LOG_ERROR)
            if allow_kill:
                for j in range(jobs):
                    process = job_procs[j]
                    process.kill()
            else:
                return None

        else:
            for j in range(jobs):
                process = job_procs[j]
                process.join()
                # RNS.log(f"Joined {j} / {process}", RNS.LOG_DEBUG) # TODO: Remove

    return stamp, total_rounds

def job_linux(stamp_cost, workblock, message_id, size, mode=MODE_STAMP):
    allow_kill = True
    stamp = None
    total_rounds = 0
    cores = multiprocessing.cpu_count()
    jobs = cores if cores <= 12 else int(cores/2)
    stop_event   = multiprocessing.Event()
    result_queue = multiprocessing.Queue(1)
    rounds_queue = multiprocessing.Queue()

    def job(stop_event, pn, sc, wb, mode):
        target = target_from_fp(sc)

        if mode == MODE_STAMP: result, rounds, _ = _loop_hash(wb, target, size, stop_event.is_set)
        else:                  result, rounds, _ = _loop_key(wb, target, stop_event.is_set)

        if not stop_event.is_set():
            stop_event.set()
            result_queue.put(result)

        rounds_queue.put(rounds)
    
    job_procs = []
    RNS.log(f"Starting {jobs} stamp generation workers", RNS.LOG_DEBUG)
    for jpn in range(jobs):
        process = multiprocessing.get_context("fork").Process(target=job, kwargs={"stop_event": stop_event, "pn": jpn, "sc": stamp_cost, "wb": workblock, "mode": mode}, daemon=True)
        job_procs.append(process)
        process.start()

    active_jobs[message_id] = [stop_event, result_queue]

    try:
        stamp = result_queue.get()

        # Collect any potential spurious
        # results from worker queue.
        try:
            while True: result_queue.get_nowait()
        except: pass

        for j in range(jobs):
            nrounds = 0
            try:
                nrounds = rounds_queue.get(timeout=2)
            except Exception as e:
                RNS.log(f"Failed to get round stats part {j}: {e}", RNS.LOG_ERROR)
            total_rounds += nrounds

        all_exited = False
        exit_timeout = time.time() + 5
        while time.time() < exit_timeout:
            if not any(p.is_alive() for p in job_procs):
                all_exited = True
                break
            time.sleep(0.005)

        if not all_exited:
            RNS.log("Stamp generation IPC timeout, possible worker deadlock. Terminating remaining processes.", RNS.LOG_ERROR)
            if allow_kill:
                for j in range(jobs):
                    process = job_procs[j]
                    process.kill()
            else:
                return None

        else:
            for j in range(jobs):
                process = job_procs[j]
                process.join()

    except Exception as e: RNS.log(f"Error while getting stamp generation result: {e}", RNS.LOG_ERROR)
    finally: active_jobs.pop(message_id, None)

    return stamp, total_rounds

ANDROID_PREFER_NACL                = True
ANDROID_USE_PERSISTENT             = True
ANDROID_LOW_DIFFICULTY_JOBS        = 1
ANDROID_NO_POOL_WB_EXPAND_MAX      = 4
ANDROID_POOLING_THRESHOLD_COST     = 8
ANDROID_KEYSTAMP_POOLING_THRESHOLD = 6
def job_android(stamp_cost, workblock, message_id, size, mode=MODE_STAMP):
    if ANDROID_USE_PERSISTENT: return job_android_persistent(stamp_cost, workblock, message_id, size, mode)
    else:                      return job_android_legacy(stamp_cost, workblock, message_id, size, mode)

def job_android_legacy(stamp_cost, workblock, message_id, size, mode=MODE_STAMP):
    # Semaphore support is flaky to non-existent on
    # Android, so we need to manually dispatch and
    # manage workloads here, while periodically
    # checking in on the progress.
    
    stamp = None
    start_time = time.time()
    total_rounds = 0
    rounds_per_worker = 1000
    
    use_nacl = False
    try:
        if ANDROID_PREFER_NACL:
            import nacl.encoding
            import nacl.hash
            use_nacl = True
    except: pass

    if use_nacl:
        def full_hash(m): return nacl.hash.sha256(m, encoder=nacl.encoding.RawEncoder)
    else:
        def full_hash(m): return RNS.Identity.full_hash(m)

    wm = multiprocessing.Manager()
    jobs = multiprocessing.cpu_count()

    def job(procnum=None, results_dict=None, wb=None, sc=None, jr=None, mode=MODE_STAMP):
        try:
            found_result = None
            target = target_from_fp(sc)

            if mode == MODE_STAMP: result, rounds, found = _loop_hash(wb, target, size, _never, None, jr, full_hash)
            else:                  result, rounds, found = _loop_key(wb, target, _never, jr)

            if found: found_result = result
            results_dict[procnum] = [found_result, rounds]

        except Exception as e:
            RNS.log(f"Stamp generation worker error: {e}", RNS.LOG_ERROR)
            RNS.trace_exception(e)

    active_jobs[message_id] = False;

    RNS.log(f"Dispatching {jobs} workers for stamp generation...", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None

    results_dict = wm.dict()
    while stamp == None and active_jobs[message_id] == False:
        job_procs = []
        try:
            for pnum in range(jobs):
                pargs = {"procnum":pnum, "results_dict": results_dict, "wb": workblock, "sc":stamp_cost, "jr":rounds_per_worker, "mode":mode}
                process = multiprocessing.Process(target=job, kwargs=pargs)
                job_procs.append(process)
                process.start()

            for process in job_procs:
                process.join()

            for j in results_dict:
                r = results_dict[j]
                total_rounds += r[1]
                if r[0] != None:
                    stamp = r[0]

            if stamp == None:
                elapsed = max(time.time()-start_time, 1E-6)
                speed = total_rounds/elapsed
                RNS.log(f"Stamp generation running. {total_rounds} rounds completed so far, {RNS.prettysize(speed, suffix='rps')}", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
        
        except Exception as e:
            RNS.log(f"Stamp generation job error: {e}", RNS.LOG_ERROR)
            RNS.trace_exception(e)

    active_jobs.pop(message_id)

    return stamp, total_rounds

def job_android_persistent(stamp_cost, workblock, message_id, size, mode=MODE_STAMP):
    stamp = None
    start_time = time.time()
    total_rounds = 0

    use_nacl = False
    try:
        if ANDROID_PREFER_NACL:
            import nacl.encoding
            import nacl.hash
            use_nacl = True
    except: pass

    if use_nacl:
        def full_hash(m): return nacl.hash.sha256(m, encoder=nacl.encoding.RawEncoder)
    else:
        def full_hash(m): return RNS.Identity.full_hash(m)

    ctx = multiprocessing.get_context("fork")
    wm = ctx.Manager()
    try: jobs = len(os.sched_getaffinity(0))
    except Exception: jobs = multiprocessing.cpu_count()

    no_pool = False
    if len(workblock) <= WORKBLOCK_EXPAND_CHUNK*ANDROID_NO_POOL_WB_EXPAND_MAX:
        if   mode == MODE_STAMP    and stamp_cost < ANDROID_POOLING_THRESHOLD_COST_FP:     no_pool = True
        elif mode == MODE_KEYSTAMP and stamp_cost < ANDROID_KEYSTAMP_POOLING_THRESHOLD_FP: no_pool = True

    if no_pool:
        RNS.log(f"Low stamp difficulty, using {ANDROID_LOW_DIFFICULTY_JOBS} worker{'s' if ANDROID_LOW_DIFFICULTY_JOBS != 1 else ''} instead of {jobs}", RNS.LOG_DEBUG)
        jobs = ANDROID_LOW_DIFFICULTY_JOBS

    results_dict = wm.dict()
    stop_flag = mmap.mmap(-1, 1, flags=mmap.MAP_SHARED | getattr(mmap, "MAP_ANONYMOUS", 0))
    active_jobs[message_id] = False

    RNS.log(f"Dispatching {jobs} worker{'s' if jobs != 1 else ''} for stamp generation...", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None

    def job(worker_id):
        rounds = 0
        found_result = None
        try:
            target = target_from_fp(stamp_cost)
            stop_check = lambda: stop_flag[0] != 0

            if mode == MODE_STAMP: result, rounds, found = _loop_hash(workblock, target, size, stop_check, None, 0, full_hash)
            else:                  result, rounds, found = _loop_key(workblock, target, stop_check, 0)

            if found:
                found_result = result
                results_dict["found"] = [found_result, rounds]
                stop_flag[0] = 1

            results_dict[worker_id] = [found_result, rounds]

        except Exception as e:
            RNS.log(f"Stamp generation worker error: {e}", RNS.LOG_ERROR)
            RNS.trace_exception(e)
            try: results_dict[worker_id] = [None, rounds]
            except Exception: pass

    job_procs = []
    try:
        for pnum in range(jobs):
            process = ctx.Process(target=job, kwargs={"worker_id": pnum}, daemon=True)
            job_procs.append(process)
            process.start()

        last_progress = time.time()
        while stamp == None and active_jobs.get(message_id) == False:
            if "found" in results_dict: stamp = results_dict["found"][0]
            if stamp == None:
                if not any(p.is_alive() for p in job_procs): break

                if time.time()-last_progress > 10:
                    elapsed = max(time.time()-start_time, 1E-6)
                    RNS.log(f"Stamp ({cost_from_fp(stamp_cost)}) generation running, {RNS.prettyshorttime(elapsed)} elapsed", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
                    last_progress = time.time()

                if message_id in active_jobs and active_jobs[message_id] == True: stop_flag[0] = 1

                time.sleep(0.05)

    finally:
        stop_flag[0] = 1

        for process in job_procs:
            try: process.join(timeout=2)
            except Exception: pass

        for worker_id in list(results_dict.keys()):
            try:
                if worker_id == "found": continue
                r = results_dict[worker_id]
                if r != None: total_rounds += r[1]
            except Exception: pass

        active_jobs.pop(message_id, None)
        try: wm.shutdown()
        except Exception: pass

    return stamp, total_rounds

#######################
# Fixed-point Helpers #
#######################

# Fixed-point stamp target mantissa table
# TAB[f] = floor(2^33 * 2^(f/256)), f = 0..255
TAB_DIGEST    = "55ba3ce1df224895b0dfdc102eb4359fc2f5a7efefee68df0cc90c8a8ac24f48"
PRM_DIGEST    = "21436fc98e76a12cad7c52ebeb6ab76c2ae93b4cd768949df7fdd4e2f98c378d"
MANTISSA_BITS = 33
COST_FP_BITS  = 8
COST_FP       = 1 << COST_FP_BITS

# These values are authoritative. DO NOT attempt to
# invent your own, calculate them at load time, or
# generate them on the fly. You have been warned.
TAB = (
    0x200000000, 0x201635f4b, 0x202c7b53f, 0x2042d0287, 0x2059347ce, 0x206fa85c2,
    0x20862bd0d, 0x209cbee5e, 0x20b361a62, 0x20ca141c7, 0x20e0d653b, 0x20f7a856e,
    0x210e8a30e, 0x21257becc, 0x213c7d958, 0x21538f363, 0x216ab0d9f, 0x2181e28bc,
    0x21992456e, 0x21b076467, 0x21c7d865a, 0x21df4abfb, 0x21f6cd5ff, 0x220e6051a,
    0x222603a02, 0x223db756b, 0x22557b80d, 0x226d5029e, 0x2285355d5, 0x229d2b269,
    0x22b531914, 0x22cd48a8e, 0x22e57078f, 0x22fda90d2, 0x2315f2711, 0x232e4cb06,
    0x2346b7d6d, 0x235f33f02, 0x2377c1080, 0x23905f2a5, 0x23a90e62d, 0x23c1cebd6,
    0x23daa045f, 0x23f383087, 0x240c7710c, 0x24257c6af, 0x243e9322f, 0x2457bb44f,
    0x2470f4dce, 0x248a3ff70, 0x24a39c9f6, 0x24bd0ae23, 0x24d68acbc, 0x24f01c683,
    0x2509bfc3e, 0x252374eb2, 0x253d3bea3, 0x255714cda, 0x2570ffa1b, 0x258afc72e,
    0x25a50b4dc, 0x25bf2c3ec, 0x25d95f527, 0x25f3a4957, 0x260dfc146, 0x262865dbd,
    0x2642e1f89, 0x265d70775, 0x26781164c, 0x2692c4cdc, 0x26ad8abf2, 0x26c86345b,
    0x26e34e6e7, 0x26fe4c463, 0x27195cda0, 0x27348036e, 0x274fb669c, 0x276aff7fd,
    0x27865b862, 0x27a1ca89d, 0x27bd4c982, 0x27d8e1be3, 0x27f48a095, 0x28104586c,
    0x282c1443e, 0x2847f64e1, 0x2863ebb2a, 0x287ff47f0, 0x289c10c0c, 0x28b840854,
    0x28d483da3, 0x28f0dacd1, 0x290d456b8, 0x2929c3c32, 0x294655e1a, 0x2962fbd4d,
    0x297fb5aa6, 0x299c83702, 0x29b96533f, 0x29d65b03b, 0x29f364ed3, 0x2a1082fe8,
    0x2a2db5459, 0x2a4afbd07, 0x2a6856ad3, 0x2a85c5e9e, 0x2aa34994b, 0x2ac0e1bbd,
    0x2ade8e6d6, 0x2afc4fb7c, 0x2b1a25a92, 0x2b38104ff, 0x2b560fba9, 0x2b7423f75,
    0x2b924d14b, 0x2bb08b213, 0x2bcede2b5, 0x2bed4641b, 0x2c0bc372e, 0x2c2a55cd9,
    0x2c48fd607, 0x2c67ba3a3, 0x2c868c699, 0x2ca573fd7, 0x2cc47104a, 0x2ce3838e1,
    0x2d02aba89, 0x2d21e9633, 0x2d413cccf, 0x2d60a5f4e, 0x2d8024ea1, 0x2d9fb9bba,
    0x2dbf6478c, 0x2ddf2530b, 0x2dfefbf2a, 0x2e1ee8cde, 0x2e3eebd1d, 0x2e5f050dd,
    0x2e7f34914, 0x2e9f7a6ba, 0x2ebfd6ac8, 0x2ee049635, 0x2f00d29fb, 0x2f2172715,
    0x2f4228e7d, 0x2f62f612e, 0x2f83da026, 0x2fa4d4c5f, 0x2fc5e66d9, 0x2fe70f092,
    0x30084ea87, 0x3029a55ba, 0x304b13329, 0x306c983d7, 0x308e348c4, 0x30afe82f3,
    0x30d1b3368, 0x30f395b26, 0x31158fb31, 0x3137a148f, 0x3159ca845, 0x317c0b75a,
    0x319e642d6, 0x31c0d4bc1, 0x31e35d322, 0x3205fda05, 0x3228b6172, 0x324b86a75,
    0x326e6f619, 0x32917056b, 0x32b489979, 0x32d7bb34e, 0x32fb053fb, 0x331e67c8f,
    0x3341e2e19, 0x3365769aa, 0x338923054, 0x33ace8329, 0x33d0c633c, 0x33f4bd1a0,
    0x3418ccf6b, 0x343cf5db1, 0x346137d89, 0x348593008, 0x34aa07647, 0x34ce9515e,
    0x34f33c266, 0x3517fca78, 0x353cd6aaf, 0x3561ca426, 0x3586d77fa, 0x35abfe747,
    0x35d13f32b, 0x35f699cc4, 0x361c0e531, 0x36419cd93, 0x366745709, 0x368d082b6,
    0x36b2e51bc, 0x36d8dc53e, 0x36feede5f, 0x372519e44, 0x374b60614, 0x3771c16f3,
    0x37983d209, 0x37bed387e, 0x37e584b7a, 0x380c50c28, 0x383337bb0, 0x385a39b3f,
    0x388156bff, 0x38a88ef1f, 0x38cfe25ca, 0x38f751131, 0x391edb280, 0x394680aea,
    0x396e41b9d, 0x39961e5cd, 0x39be16aab, 0x39e62ab6b, 0x3a0e5a940, 0x3a36a6561,
    0x3a5f0e101, 0x3a8791d59, 0x3ab031b9f, 0x3ad8edd0c, 0x3b01c62d9, 0x3b2abae3f,
    0x3b53cc07b, 0x3b7cf9ac7, 0x3ba643e60, 0x3bcfaac83, 0x3bf92e66f, 0x3c22ced63,
    0x3c4c8c29e, 0x3c7666762, 0x3ca05dcf1, 0x3cca7248c, 0x3cf4a3f78, 0x3d1ef2ef9,
    0x3d495f454, 0x3d73e90cf, 0x3d9e905b1, 0x3dc955443, 0x3df437dcc, 0x3e1f38396,
    0x3e4a566ed, 0x3e759291b, 0x3ea0ecb6d, 0x3ecc64f31, 0x3ef7fb5b3, 0x3f23b0044,
    0x3f4f83033, 0x3f7b746d2, 0x3fa784571, 0x3fd3b2d65 )

assert len(TAB) == COST_FP
assert TAB[0] == 1 << MANTISSA_BITS
assert all(b > a for a, b in zip(TAB, TAB[1:]))
assert sha256(",".join(str(v) for v in TAB).encode("ascii")) == bytes.fromhex(TAB_DIGEST)
assert sha256(f"master|{TAB_DIGEST}|{MANTISSA_BITS}|{len(TAB)}|{COST_FP_BITS}|{COST_FP}|".encode("utf-8")) == bytes.fromhex(PRM_DIGEST)

def cost_to_fp(cost):
    v = math.floor(float(cost) * COST_FP + 0.5)
    return max(0, min(v, RNS.Transport.STAMP_COST_CAP * COST_FP))

def fp_to_bytes(fp):
    return bytes(((fp >> COST_FP_BITS) & 0xFF, fp & 0xFF))

def cost_to_bytes(cost):
    return fp_to_bytes(cost_to_fp(cost))

def fp_from_bytes(b):
    return (b[0] << COST_FP_BITS) | b[1]

def cost_from_fp(fp):
    return fp/COST_FP

def cost_from_bytes(b):
    return cost_from_fp(fp_from_bytes(b))

def quantize_cost(cost):
    return cost_from_fp(cost_to_fp(cost))

def target_from_fp(fp):
    assert 0 <= fp <= RNS.Transport.STAMP_COST_CAP * COST_FP
    # Extract the integer and fractional parts
    # by modular division, here equivalent to:
    # ((256*COST_FP) // COST_FP, (256*COST_FP) % COST_FP)
    #       i = quotient              f = remainder
    i, f = divmod(256*COST_FP - fp, COST_FP)

    # Then, construct the numerical representation
    # by getting the quantized fractional mantissa
    # from TAB, and raising it to i (the exponent)
    # and right-shifting it by MANTISSA_BITS.
    return (TAB[f] << i) >> MANTISSA_BITS

def target_from_cost(cost):
    return target_from_fp(cost_to_fp(cost))

def cost_int(fp): return fp >> COST_FP_BITS  # Legacy integer display representation
def cost_str(fp): return f"{fp / COST_FP:g}" # Display only, remember, the floats are only in your head

###########################
# Persistence and loading #
###########################

DESTINATION_STAMP_EXTENSION = ".dstamp"
STAMP_FILE_VERSION          = 1

def stamps_dir(create=False):
    storagepath = RNS.Reticulum.storagepath
    if not storagepath: return None
    path = os.path.join(storagepath, "stamps")
    if create and not os.path.isdir(path):
        try: os.makedirs(path, exist_ok=True)
        except Exception as e:
            RNS.log(f"An error occurred while creating destination stamp storage path: {e}", RNS.LOG_WARNING)
            return None
    return path

def destination_stamp_file(destination_hash, create=False):
    dir_path = stamps_dir(create=create)
    if dir_path == None: return None
    return os.path.join(dir_path, RNS.hexrep(destination_hash, delimit=False)+DESTINATION_STAMP_EXTENSION)

def store_destination_stamp(destination_hash, stamp, stamp_value):
    file_path = destination_stamp_file(destination_hash, create=True)
    if file_path == None:
        RNS.log("No storage path available, destination stamp not persisted", RNS.LOG_WARNING)
        return False

    try:
        data = msgpack.packb({"v": STAMP_FILE_VERSION, "stamp":   stamp,
                              "value":   stamp_value, "generated": time.time()})

        temp_path = file_path+f".{os.getpid()}.tmp"
        with open(temp_path, "wb") as temp_file: temp_file.write(data)
        os.replace(temp_path, file_path)
        return True

    except Exception as e:
        RNS.log(f"An error occurred while persisting destination stamp: {e}", RNS.LOG_WARNING)
        return False

def load_destination_stamp(destination_hash, material, required_value):
    file_path = destination_stamp_file(destination_hash)
    if file_path == None or not os.path.isfile(file_path): return None

    try:
        with open(file_path, "rb") as stamp_file: entry = msgpack.unpackb(stamp_file.read())
        if entry.get("v") != STAMP_FILE_VERSION: return None
        workblock = stamp_workblock(material, expand_rounds=0)

        stamp = entry["stamp"]
        if not isinstance(stamp, bytes) or len(stamp) != RNS.Identity.STAMPLENGTH:
            RNS.log(f"Stored stamp for {RNS.prettyhexrep(destination_hash)} has invalid format. Regenerating on next announce.", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
            return None

        value = stamp_value(workblock, stamp)
        if not stamp_valid(stamp, required_value, workblock):
            RNS.log(f"Stored stamp for {RNS.prettyhexrep(destination_hash)} has value {value}, below required {required_value}. Regenerating on next announce.", RNS.LOG_DEBUG) if RNS.sl(RNS.LOG_DEBUG) else None
            return None

        return (stamp, value)

    except Exception as e:
        RNS.log(f"Ignoring unreadable destination stamp file for {RNS.prettyhexrep(destination_hash)}: {e}", RNS.LOG_WARNING)
        return None

#########################
# Pooling Configuration #
#########################

POOLING_THRESHOLD_COST_FP             = POOLING_THRESHOLD_COST*COST_FP
KEYSTAMP_POOLING_THRESHOLD_FP         = KEYSTAMP_POOLING_THRESHOLD*COST_FP
ANDROID_POOLING_THRESHOLD_COST_FP     = ANDROID_POOLING_THRESHOLD_COST*COST_FP
ANDROID_KEYSTAMP_POOLING_THRESHOLD_FP = ANDROID_KEYSTAMP_POOLING_THRESHOLD*COST_FP