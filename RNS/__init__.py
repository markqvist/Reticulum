# Reticulum License
#
# Copyright (c) 2016-2025 Mark Qvist
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

import os
import sys
import glob
import time
import datetime
import random
import threading

from ._version import __version__

from .Reticulum import Reticulum
from .Identity import Identity
from .Link import Link, RequestReceipt
from .Channel import MessageBase
from .Buffer import Buffer, RawChannelReader, RawChannelWriter
from .Transport import Transport
from .Destination import Destination
from .Packet import Packet
from .Packet import PacketReceipt
from .Resolver import Resolver
from .Resource import Resource, ResourceAdvertisement
from .Cryptography import HKDF
from .Cryptography import Hashes

py_modules  = glob.glob(os.path.dirname(__file__)+"/*.py")
pyc_modules = glob.glob(os.path.dirname(__file__)+"/*.pyc")
modules     = py_modules+pyc_modules
__all__ = list(set([os.path.basename(f).replace(".pyc", "").replace(".py", "") for f in modules if not (f.endswith("__init__.py") or f.endswith("__init__.pyc"))]))

import importlib.util
if importlib.util.find_spec("cython"): import cython; compiled = cython.compiled
else: compiled = False

LOG_NONE     = -1
LOG_CRITICAL = 0
LOG_ERROR    = 1
LOG_WARNING  = 2
LOG_NOTICE   = 3
LOG_INFO     = 4
LOG_VERBOSE  = 5
LOG_DEBUG    = 6
LOG_EXTREME  = 7

LOG_STDOUT   = 0x91
LOG_FILE     = 0x92
LOG_CALLBACK = 0x93

LOG_MAXSIZE  = 5*1024*1024

loglevel        = LOG_NOTICE
logfile         = None
logdest         = LOG_STDOUT
logcall         = None
logtimefmt      = "%Y-%m-%d %H:%M:%S"
logtimefmt_p    = "%H:%M:%S.%f"
compact_log_fmt = False

instance_random = random.Random()
instance_random.seed(os.urandom(10))

_always_override_destination = False

logging_lock = threading.Lock()

def loglevelname(level):
    if (level == LOG_CRITICAL):
        return "[Critical]"
    if (level == LOG_ERROR):
        return "[Error]   "
    if (level == LOG_WARNING):
        return "[Warning] "
    if (level == LOG_NOTICE):
        return "[Notice]  "
    if (level == LOG_INFO):
        return "[Info]    "
    if (level == LOG_VERBOSE):
        return "[Verbose] "
    if (level == LOG_DEBUG):
        return "[Debug]   "
    if (level == LOG_EXTREME):
        return "[Extra]   "
    
    return "Unknown"

def version():
    return __version__

def host_os():
    from .vendor.platformutils import get_platform
    return get_platform()

def timestamp_str(time_s):
    timestamp = time.localtime(time_s)
    return time.strftime(logtimefmt, timestamp)

def precise_timestamp_str(time_s):
    return datetime.datetime.now().strftime(logtimefmt_p)[:-3]

def log(msg, level=3, _override_destination = False, pt=False):
    if loglevel == LOG_NONE: return
    global _always_override_destination, compact_log_fmt
    msg = str(msg)
    if loglevel >= level:
        if pt:
            logstring = "["+precise_timestamp_str(time.time())+"] "+loglevelname(level)+" "+msg
        else:
            if not compact_log_fmt:
                logstring = "["+timestamp_str(time.time())+"] "+loglevelname(level)+" "+msg
            else:
                logstring = "["+timestamp_str(time.time())+"] "+msg

        with logging_lock:
            if (logdest == LOG_STDOUT or _always_override_destination or _override_destination):
                if not threading.main_thread().is_alive(): return
                else: print(logstring)

            elif (logdest == LOG_FILE and logfile != None):
                try:
                    file = open(logfile, "a")
                    file.write(logstring+"\n")
                    file.close()
                    
                    if os.path.getsize(logfile) > LOG_MAXSIZE:
                        prevfile = logfile+".1"
                        if os.path.isfile(prevfile):
                            os.unlink(prevfile)
                        os.rename(logfile, prevfile)

                except Exception as e:
                    _always_override_destination = True
                    log("Exception occurred while writing log message to log file: "+str(e), LOG_CRITICAL)
                    log("Dumping future log events to console!", LOG_CRITICAL)
                    log(msg, level)

            elif logdest == LOG_CALLBACK:
                try:
                    logcall(logstring)
                except Exception as e:
                    _always_override_destination = True
                    log("Exception occurred while calling external log handler: "+str(e), LOG_CRITICAL)
                    log("Dumping future log events to console!", LOG_CRITICAL)
                    log(msg, level)
                

def rand():
    result = instance_random.random()
    return result

def trace_exception(e):
    import traceback
    exception_info = "".join(traceback.TracebackException.from_exception(e).format())
    log(f"An unhandled {str(type(e))} exception occurred: {str(e)}", LOG_ERROR)
    log(exception_info, LOG_ERROR)

def hexrep(data, delimit=True):
    try:
        iter(data)
    except TypeError:
        data = [data]
        
    delimiter = ":"
    if not delimit:
        delimiter = ""
    hexrep = delimiter.join("{:02x}".format(c) for c in data)
    return hexrep

def prettyhexrep(data):
    delimiter = ""
    hexrep = "<"+delimiter.join("{:02x}".format(c) for c in data)+">"
    return hexrep

def prettyspeed(num, suffix="b"):
    return prettysize(num/8, suffix=suffix)+"ps"

def prettysize(num, suffix='B'):
    units = ['','K','M','G','T','P','E','Z']
    last_unit = 'Y'

    if suffix == 'b':
        num *= 8
        units = ['','K','M','G','T','P','E','Z']
        last_unit = 'Y'

    for unit in units:
        if abs(num) < 1000.0:
            if unit == "":
                return "%.0f %s%s" % (num, unit, suffix)
            else:
                return "%.2f %s%s" % (num, unit, suffix)
        num /= 1000.0

    return "%.2f%s%s" % (num, last_unit, suffix)

def prettyfrequency(hz, suffix="Hz"):
    num = hz*1e6
    units = ["µ", "m", "", "K","M","G","T","P","E","Z"]
    last_unit = "Y"

    for unit in units:
        if abs(num) < 1000.0:
            return "%.2f %s%s" % (num, unit, suffix)
        num /= 1000.0

    return "%.2f%s%s" % (num, last_unit, suffix)

def prettydistance(m, suffix="m"):
    num = m*1e6
    units = ["µ", "m", "c", ""]
    last_unit = "K"

    for unit in units:
        divisor = 1000.0
        if unit == "m": divisor = 10
        if unit == "c": divisor = 100

        if abs(num) < divisor:
            return "%.2f %s%s" % (num, unit, suffix)
        num /= divisor

    return "%.2f %s%s" % (num, last_unit, suffix)

def prettytime(time, verbose=False, compact=False):
    neg = False
    if time < 0:
        time = abs(time)
        neg = True

    days = int(time // (24 * 3600))
    time = time % (24 * 3600)
    hours = int(time // 3600)
    time %= 3600
    minutes = int(time // 60)
    time %= 60
    if compact:
        seconds = int(time)
    else:
        seconds = round(time, 2)
    
    ss = "" if seconds == 1 else "s"
    sm = "" if minutes == 1 else "s"
    sh = "" if hours == 1 else "s"
    sd = "" if days == 1 else "s"

    displayed = 0
    components = []
    if days > 0 and ((not compact) or displayed < 2):
        components.append(str(days)+" day"+sd if verbose else str(days)+"d")
        displayed += 1

    if hours > 0 and ((not compact) or displayed < 2):
        components.append(str(hours)+" hour"+sh if verbose else str(hours)+"h")
        displayed += 1

    if minutes > 0 and ((not compact) or displayed < 2):
        components.append(str(minutes)+" minute"+sm if verbose else str(minutes)+"m")
        displayed += 1

    if seconds > 0 and ((not compact) or displayed < 2):
        components.append(str(seconds)+" second"+ss if verbose else str(seconds)+"s")
        displayed += 1

    i = 0
    tstr = ""
    for c in components:
        i += 1
        if i == 1:
            pass
        elif i < len(components):
            tstr += ", "
        elif i == len(components):
            tstr += " and "

        tstr += c

    if tstr == "":
        return "0s"
    else:
        if not neg:
            return tstr
        else:
            return f"-{tstr}"

def prettyshorttime(time, verbose=False, compact=False):
    neg = False
    time = time*1e6
    if time < 0:
        time = abs(time)
        neg = True
    
    seconds = int(time // 1e6); time %= 1e6
    milliseconds = int(time // 1e3); time %= 1e3

    if compact:
        microseconds = int(time)
    else:
        microseconds = round(time, 2)
    
    ss = "" if seconds == 1 else "s"
    sms = "" if milliseconds == 1 else "s"
    sus = "" if microseconds == 1 else "s"

    displayed = 0
    components = []
    if seconds > 0 and ((not compact) or displayed < 2):
        components.append(str(seconds)+" second"+ss if verbose else str(seconds)+"s")
        displayed += 1

    if milliseconds > 0 and ((not compact) or displayed < 2):
        components.append(str(milliseconds)+" millisecond"+sms if verbose else str(milliseconds)+"ms")
        displayed += 1

    if microseconds > 0 and ((not compact) or displayed < 2):
        components.append(str(microseconds)+" microsecond"+sus if verbose else str(microseconds)+"µs")
        displayed += 1

    i = 0
    tstr = ""
    for c in components:
        i += 1
        if i == 1:
            pass
        elif i < len(components):
            tstr += ", "
        elif i == len(components):
            tstr += " and "

        tstr += c

    if tstr == "":
        return "0us"
    else:
        if not neg:
            return tstr
        else:
            return f"-{tstr}"

def phyparams():
    print("Required Physical Layer MTU : "+str(Reticulum.MTU)+" bytes")
    print("Plaintext Packet MDU        : "+str(Packet.PLAIN_MDU)+" bytes")
    print("Encrypted Packet MDU        : "+str(Packet.ENCRYPTED_MDU)+" bytes")
    print("Link Curve                  : "+str(Link.CURVE))
    print("Link Packet MDU             : "+str(Link.MDU)+" bytes")
    print("Link Public Key Size        : "+str(Link.ECPUBSIZE*8)+" bits")
    print("Link Private Key Size       : "+str(Link.KEYSIZE*8)+" bits")

def panic():
    os._exit(255)

exit_called = False
def exit(code=0):
    global exit_called
    if not exit_called:
        exit_called = True
        Reticulum.exit_handler()
        os._exit(code)

class Profiler:
    _ran = False
    profilers = {}
    tags = {}

    @staticmethod
    def get_profiler(tag=None, super_tag=None):
        if tag in Profiler.profilers:
            return Profiler.profilers[tag]
        else:
            profiler = Profiler(tag, super_tag)
            Profiler.profilers[tag] = profiler
            return profiler

    def __init__(self, tag=None, super_tag=None):
        self.paused = False
        self.pause_time = 0
        self.pause_started = None
        self.tag = tag
        self.super_tag = super_tag
        if self.super_tag in Profiler.profilers:
            self.super_profiler = Profiler.profilers[self.super_tag]
            self.pause_super = self.super_profiler.pause
            self.resume_super = self.super_profiler.resume
        else:
            def noop(self=None):
                pass
            self.super_profiler = None
            self.pause_super = noop
            self.resume_super = noop

    def __enter__(self):
        self.pause_super()
        tag = self.tag
        super_tag = self.super_tag
        thread_ident = threading.get_ident()
        if not tag in Profiler.tags:
            Profiler.tags[tag] = {"threads": {}, "super": super_tag}
        if not thread_ident in Profiler.tags[tag]["threads"]:
            Profiler.tags[tag]["threads"][thread_ident] = {"current_start": None, "captures": []}

        Profiler.tags[tag]["threads"][thread_ident]["current_start"] = time.perf_counter()
        self.resume_super()

    def __exit__(self, exc_type, exc_value, traceback):
        self.pause_super()
        tag = self.tag
        super_tag = self.super_tag
        end = time.perf_counter() - self.pause_time
        self.pause_time = 0
        thread_ident = threading.get_ident()
        if tag in Profiler.tags and thread_ident in Profiler.tags[tag]["threads"]:
            if Profiler.tags[tag]["threads"][thread_ident]["current_start"] != None:
                begin = Profiler.tags[tag]["threads"][thread_ident]["current_start"]
                Profiler.tags[tag]["threads"][thread_ident]["current_start"] = None
                Profiler.tags[tag]["threads"][thread_ident]["captures"].append(end-begin)
                if not Profiler._ran:
                    Profiler._ran = True
        self.resume_super()

    def pause(self, pause_started=None):
        if not self.paused:
            self.paused = True
            self.pause_started = pause_started or time.perf_counter()
            self.pause_super(self.pause_started)

    def resume(self):
        if self.paused:
            self.pause_time += time.perf_counter() - self.pause_started
            self.paused = False
            self.resume_super()

    @staticmethod
    def ran():
        return Profiler._ran

    @staticmethod
    def results():
        from statistics import mean, median, stdev
        results = {}
        
        for tag in Profiler.tags:
            tag_captures = []
            tag_entry = Profiler.tags[tag]
            
            for thread_ident in tag_entry["threads"]:
                thread_entry = tag_entry["threads"][thread_ident]
                thread_captures = thread_entry["captures"]
                sample_count = len(thread_captures)
                
                if sample_count > 1:
                    thread_results = {
                        "count": sample_count,
                        "mean": mean(thread_captures),
                        "median": median(thread_captures),
                        "stdev": stdev(thread_captures)
                    }
                elif sample_count == 1:
                    thread_results = {
                        "count": sample_count,
                        "mean": mean(thread_captures),
                        "median": median(thread_captures),
                        "stdev": None
                    }

                tag_captures.extend(thread_captures)

            sample_count = len(tag_captures)
            if sample_count > 1:
                tag_results = {
                    "name": tag,
                    "super": tag_entry["super"],
                    "count": len(tag_captures),
                    "mean": mean(tag_captures),
                    "median": median(tag_captures),
                    "stdev": stdev(tag_captures)
                }
            elif sample_count == 1:
                tag_results = {
                    "name": tag,
                    "super": tag_entry["super"],
                    "count": len(tag_captures),
                    "mean": mean(tag_captures),
                    "median": median(tag_captures),
                    "stdev": None
                }

            results[tag] = tag_results

        def print_results_recursive(tag, results, level=0):
            print_tag_results(tag, level+1)

            for tag_name in results:
                sub_tag = results[tag_name]
                if sub_tag["super"] == tag["name"]:
                    print_results_recursive(sub_tag, results, level=level+1)


        def print_tag_results(tag, level):
            ind = "  "*level
            name = tag["name"]; count = tag["count"]
            mean = tag["mean"]; median = tag["median"]; stdev = tag["stdev"]
            print(    f"{ind}{name}")
            print(    f"{ind}  Samples  : {count}")
            if stdev != None:
                print(f"{ind}  Mean     : {prettyshorttime(mean)}")
                print(f"{ind}  Median   : {prettyshorttime(median)}")
                print(f"{ind}  St.dev.  : {prettyshorttime(stdev)}")
            print(    f"{ind}  Total    : {prettyshorttime(mean*count)}")
            print("")

        print("\nProfiler results:\n")
        for tag_name in results:
            tag = results[tag_name]
            if tag["super"] == None:
                print_results_recursive(tag, results)

profile = Profiler.get_profiler